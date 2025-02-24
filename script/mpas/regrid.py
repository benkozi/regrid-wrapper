from pathlib import Path
from typing import Literal

import esmpy
import numpy as np
import pandas as pd
from pydantic import BaseModel
from pyremap import MpasCellMeshDescriptor

from regrid_wrapper.context.comm import COMM
from regrid_wrapper.context.logging import LOGGER
from regrid_wrapper.esmpy.field_wrapper import (
    GridSpec,
    NcToGrid,
    NcToField,
    FieldWrapper,
    GridWrapper,
)

_LOGGER = LOGGER.getChild("mpas-regrid")


class Context(BaseModel):
    src_path: Path
    dst_path: Path
    tmp_path: Path
    field_names: tuple[str, ...] = ("FRE", "FRP_MEAN", "PM25", "NH3", "SO2")
    rank: int = COMM.rank


class RegridProcessor:

    def __init__(self, context: Context) -> None:
        self.context = context

        self._regridder: esmpy.Regrid | None = None
        self._dst_field: esmpy.Field | None = None
        self._src_gwrap: GridWrapper | None = None

    def initialize(self) -> None:
        esmpy.Manager(debug=True)

        scrip_path = self.context.tmp_path / "mpas_scrip.nc"
        if self.context.rank == 0:
            _LOGGER.info("writing mpas scrip grid")
            mpas_desc = MpasCellMeshDescriptor(
                str(self.context.dst_path), "na15km.init"
            )
            mpas_desc.to_scrip(str(scrip_path))

        print("create source grid")
        self._src_gwrap = NcToGrid(
            path=self.context.src_path,
            spec=GridSpec(
                x_center="grid_lont",
                y_center="grid_latt",
                x_dim=("grid_xt",),
                y_dim=("grid_yt",),
                x_corner="grid_lon",
                y_corner="grid_lat",
                x_corner_dim=("grid_x",),
                y_corner_dim=("grid_y",),
            ),
        ).create_grid_wrapper()

        _LOGGER.info("create source field")
        src_fwrap = self.create_field_wrapper(self.context.field_names[0])

        _LOGGER.info("create destination mesh")
        dst_mesh = esmpy.Mesh(filename=str(scrip_path), filetype=esmpy.FileFormat.SCRIP)

        _LOGGER.info("create destination field")
        dst_field = esmpy.Field(dst_mesh, name="dst", meshloc=esmpy.MeshLoc.ELEMENT)

        _LOGGER.info("create regridder")
        self._regridder = esmpy.Regrid(
            srcfield=src_fwrap.value,
            dstfield=dst_field,
            regrid_method=esmpy.RegridMethod.CONSERVE,
            unmapped_action=esmpy.UnmappedAction.ERROR,
            ignore_degenerate=False,
        )

    def run(self) -> None:
        _LOGGER.info("apply regridding")

        regridder = self.get_regridder()
        all_desc_stats = pd.DataFrame()
        for field_name in self.context.field_names:
            _LOGGER.info(f"regridding {field_name=}")
            src_fwrap = self.create_field_wrapper(field_name=field_name)
            dst_field = self.get_dst_field()
            dst_field.data.fill(0.0)
            regridder(src_fwrap.value, dst_field)

            src_stats = self.create_desc_stuff(
                container={field_name: src_fwrap.value.data},
                origin="src",
                path=self.src_path,
            )
            _LOGGER.info(f"{src_stats=}")

            dst_stats = self.create_desc_stuff(
                container={field_name: dst_field.data},
                origin="dst",
                path=self.dst_path,
            )
            _LOGGER.info(f"{dst_stats=}")

            src_fwrap.value.destroy()
            del src_fwrap

    def create_desc_stuff(
        self,
        container: dict[str, np.ndarray],
        origin: Literal["src", "dst"],
        path: Path | None = None,
    ) -> pd.DataFrame:
        """
        Create a standard set of descriptive statistics using `pandas`.


        Args:
            container: A dictionary mapping field names to arrays.
            origin: A tag to indicate the data origin to add to the created dataframe.
            path: Path associated with the source data.


        Returns:
            A dataframe containing descriptive statistics fields.
        """
        data_frame = pd.DataFrame.from_dict(
            {k: v.ravel() for k, v in container.items()}
        )
        desc = data_frame.describe()
        adds = {}
        for field_name in container.keys():
            adds[field_name] = [
                data_frame[field_name].sum(),
                data_frame[field_name].isnull().sum(),
                origin,
                path,
                self.context.rank,
            ]
        desc = pd.concat(
            [
                desc,
                pd.DataFrame(
                    data=adds, index=["sum", "count_null", "origin", "path", "rank"]
                ),
            ]
        )
        return desc

    def create_field_wrapper(self, field_name: str) -> FieldWrapper:
        _LOGGER.info("create source field")
        src_fwrap = NcToField(
            path=self.context.src_path,
            name=field_name,
            gwrap=self.get_src_gwrap(),
            dim_time=("time",),
        ).create_field_wrapper()
        src_data = src_fwrap.value.data
        src_data[:] = np.where(src_data < 0.0, 0.0, src_data)
        return src_fwrap

    def get_src_gwrap(self) -> GridWrapper:
        if self._src_gwrap is None:
            raise ValueError
        return self._src_gwrap

    def get_dst_field(self) -> esmpy.Field:
        if self._dst_field is None:
            raise ValueError
        return self._dst_field

    def get_regridder(self) -> esmpy.Regrid:
        if self._regridder is None:
            raise ValueError
        return self._regridder


def main() -> None:
    data_dir = Path("/scratch1/NCEPDEV/stmp2/Benjamin.Koziol/data/mpas")
    src_path = (
        data_dir
        / "RAVE-HrlyEmiss-3km_v1r3_blend_s202407240000000_e202407240059590_c202407240203140.nc"
    )
    dst_path = data_dir / "na15km.init.nc"
    tmp_path = Path("/home/Benjamin.Koziol/htmp/out")
    context = Context(src_path=src_path, dst_path=dst_path, tmp_path=tmp_path)
    processor = RegridProcessor(context=context)
    processor.initialize()
    processor.run()
    # processor.finalize()


if __name__ == "__main__":
    main()
