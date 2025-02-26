from functools import cached_property
from pathlib import Path
from typing import Literal, Iterable, Any

import esmpy
import numpy as np
import pandas as pd
from pydantic import BaseModel, computed_field
from pyremap import MpasCellMeshDescriptor

from regrid_wrapper.context.comm import COMM, reconcile_bounds
from regrid_wrapper.context.logging import LOGGER
from regrid_wrapper.esmpy.field_wrapper import (
    GridSpec,
    NcToGrid,
    NcToField,
    FieldWrapper,
    GridWrapper,
    open_nc,
    Dimension,
    DimensionCollection,
    set_variable_data,
    HasNcAttrsType,
)

_LOGGER = LOGGER.getChild("mpas-regrid")


class RaveField(BaseModel):
    name: str
    attrs: dict[str, Any]
    fill_value: float
    dtype: int
    dim_names: tuple[str, ...]


class RaveField2d(RaveField):
    dim_names: tuple[str, ...] = ("Time", "nCells")


class RaveField3d(RaveField):
    dim_names: tuple[str, ...] = ("Time", "nCells", "nkfire")


class RaveToMpasRegridContext(BaseModel):
    src_path: Path
    dst_path: Path
    new_dst_path: Path
    desc_stats_out: Path
    tmp_path: Path
    # fields: tuple[RaveField, ...] = ("FRE", "FRP_MEAN", "PM25", "NH3", "SO2") #tdk:rm
    rank: int = COMM.rank

    @computed_field
    def scrip_path(self) -> Path:
        return self.tmp_path / "mpas_scrip.nc"

    @computed_field
    @cached_property
    def rave_fields(self) -> tuple[RaveField, ...]:
        field_names = ("FRE", "FRP_MEAN", "PM25", "NH3", "SO2")
        rave_fields = []
        with open_nc(self.src_path, mode="r") as ds:
            for field_name in field_names:
                var = ds.variables[field_name]
                init_data = {
                    "name": field_name,
                    "attrs": self._get_nc_attrs_(var),
                    "fill_value": var.fill_value,
                    "dtype": var.dtype,
                }
                if field_name in ("FRE", "FRP_MEAN"):
                    app = RaveField2d.model_validate(init_data)
                elif field_name in ("PM25", "NH3", "SO2"):
                    app = RaveField3d.model_validate(init_data)
                rave_fields.append(app)
        _LOGGER.debug(f"{rave_fields=}")
        return tuple(rave_fields)

    @staticmethod
    def _get_nc_attrs_(src: HasNcAttrsType) -> dict[str, Any]:
        exclude = ("coordinates",)
        return {
            ii: getattr(src, ii)
            for ii in src.ncattrs()
            if not ii.startswith("_") or ii in exclude
        }


class FileDesc(BaseModel):
    path: Path
    origin: Literal["src", "dst"]
    field_names: tuple[str, ...]


class RaveToMpasRegridProcessor:

    def __init__(self, context: RaveToMpasRegridContext) -> None:
        self.context = context

        self._regridder: esmpy.Regrid | None = None
        self._dst_field: esmpy.Field | None = None
        self._src_gwrap: GridWrapper | None = None

    def initialize(self) -> None:
        esmpy.Manager(debug=True)

        if self.context.rank == 0:
            _LOGGER.info("writing mpas scrip grid")
            mpas_desc = MpasCellMeshDescriptor(
                str(self.context.dst_path), "na15km.init"
            )
            mpas_desc.to_scrip(str(self.context.scrip_path))

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
        src_fwrap = self.create_src_field_wrapper(self.context.field_names[0])

        _LOGGER.info("create destination mesh")
        dst_mesh = esmpy.Mesh(
            filename=str(self.context.scrip_path), filetype=esmpy.FileFormat.SCRIP
        )

        _LOGGER.info("create destination field")
        self._dst_field = esmpy.Field(
            dst_mesh, name="dst", meshloc=esmpy.MeshLoc.ELEMENT
        )

        _LOGGER.info("create regridder")
        self._regridder = esmpy.Regrid(
            srcfield=src_fwrap.value,
            dstfield=self._dst_field,
            regrid_method=esmpy.RegridMethod.CONSERVE,
            unmapped_action=esmpy.UnmappedAction.ERROR,
            ignore_degenerate=False,
        )

    def run(self) -> None:
        _LOGGER.info("apply regridding")

        _LOGGER.info("create output file")
        ncells_size = 130333
        with open_nc(self.context.new_dst_path, mode="w") as ds:
            ds.createDimension("nCells", ncells_size)

        regridder = self.get_regridder()
        for rave_field in self.context.rave_fields:
            _LOGGER.info(f"regridding {rave_field.name=}")
            src_fwrap = self.create_src_field_wrapper(field_name=rave_field.name)
            dst_field = self.get_dst_field()
            # tdk: any more qa stuff? minimum threshold?
            dst_field.data.fill(0.0)
            regridder(src_fwrap.value, dst_field)

            # tdk: support NcToMesh
            local_bounds = (dst_field.lower_bounds[0], dst_field.upper_bounds[0])
            reconciled_bounds = reconcile_bounds(local_bounds)
            dim_ncells = Dimension(
                name=("nCells",),
                size=ncells_size,  # tdk: pull from origin
                lower=reconciled_bounds[0],
                upper=reconciled_bounds[1],
                staggerloc=esmpy.MeshLoc.ELEMENT,
                coordinate_type="cell",
            )
            dims = DimensionCollection(value=(dim_ncells,))
            _LOGGER.info(f"{dims=}")
            _LOGGER.info(f"writing field to netcdf")
            with open_nc(self.context.new_dst_path, mode="a") as ds:
                # tdk: copy variable attributes
                var = ds.createVariable(
                    rave_field.name, float, ("nCells",), fill_value=-1.0
                )
                set_variable_data(
                    var,
                    dims,
                    dst_field.data,
                )

            src_fwrap.value.destroy()
            del src_fwrap

        if self.context.rank == 0:
            targets = [
                FileDesc(
                    path=self.context.new_dst_path,
                    origin="dst",
                    field_names=self.context.field_names,
                ),
                FileDesc(
                    path=self.context.src_path,
                    origin="src",
                    field_names=self.context.field_names,
                ),
            ]
            data_frame = self.create_desc_stuff(targets)
            data_frame.to_csv(self.context.desc_stats_out, index=False)

    def finalize(self) -> None:
        _LOGGER.info("finalizing")

    def create_desc_stuff(self, targets: Iterable[FileDesc]) -> pd.DataFrame:
        _LOGGER.info("entering create_desc_stuff")
        if self.context.rank > 0:
            raise ValueError

        to_concat = []
        for target in targets:
            with open_nc(target.path, mode="r", parallel=False) as ds:
                for varname in target.field_names:
                    data = ds.variables[varname][:].filled(np.nan).ravel()
                    data_frame = pd.DataFrame.from_dict({varname: data})
                    desc = data_frame.describe()
                    adds = {
                        varname: [
                            data_frame[varname].sum(),
                            data_frame[varname].isnull().sum(),
                            target.origin,
                            target.path,
                        ]
                    }
                    desc = pd.concat(
                        [
                            desc,
                            pd.DataFrame(
                                data=adds, index=["sum", "count_null", "origin", "path"]
                            ),
                        ]
                    )
                    to_concat.append(desc)
        ret = pd.concat([ii.transpose() for ii in to_concat])
        ret.index.name = "field_name"
        ret.reset_index(inplace=True)
        _LOGGER.info("exiting create_desc_stuff")
        return ret

    def create_src_field_wrapper(self, field_name: str) -> FieldWrapper:
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
    new_dst_path = tmp_path / "na15km_with_fields.nc"
    desc_stats_out = tmp_path / "desc_stats.csv"

    context = RaveToMpasRegridContext(
        src_path=src_path,
        dst_path=dst_path,
        new_dst_path=new_dst_path,
        desc_stats_out=desc_stats_out,
        tmp_path=tmp_path,
    )
    processor = RaveToMpasRegridProcessor(context=context)
    processor.initialize()
    processor.run()
    processor.finalize()


if __name__ == "__main__":
    main()
