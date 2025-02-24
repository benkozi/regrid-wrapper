from pathlib import Path

import esmpy
import numpy as np
from pydantic import BaseModel
from pyremap import MpasCellMeshDescriptor

from regrid_wrapper.context.comm import COMM
from regrid_wrapper.context.logging import LOGGER
from regrid_wrapper.esmpy.field_wrapper import GridSpec, NcToGrid, NcToField

_LOGGER = LOGGER.getChild("mpas-regrid")


class Context(BaseModel):
    src_path: Path
    dst_path: Path
    tmp_path: Path
    rank: int = COMM.rank


class RegridProcessor(BaseModel):
    context: Context

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
        src_gwrap = NcToGrid(
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

        _LOGGER.info("create destination mesh")
        dst_mesh = esmpy.Mesh(filename=str(scrip_path), filetype=esmpy.FileFormat.SCRIP)

        _LOGGER.info("create source field")
        src_fwrap = NcToField(
            path=self.context.src_path, name="FRE", gwrap=src_gwrap, dim_time=("time",)
        ).create_field_wrapper()
        src_data = src_fwrap.value.data
        src_data[:] = np.where(src_data < 0.0, 0.0, src_data)
        stats = [
            [src_data.shape],
            [src_data.min(), src_data.mean(), src_data.max()],
            [np.nanmin(src_data), np.nanmean(src_data), np.nanmax(src_data)],
        ]
        _LOGGER.info(f"src_data stats: {stats=}")

        _LOGGER.info("create destination field")
        dst_field = esmpy.Field(dst_mesh, name="dst", meshloc=esmpy.MeshLoc.ELEMENT)

        _LOGGER.info("create regridder")
        regridder = esmpy.Regrid(
            srcfield=src_fwrap.value,
            dstfield=dst_field,
            regrid_method=esmpy.RegridMethod.CONSERVE,
            unmapped_action=esmpy.UnmappedAction.ERROR,
            ignore_degenerate=False,
        )

        _LOGGER.info("apply regridding")
        regridder(src_fwrap.value, dst_field)

        dst_data = dst_field.data
        stats = [
            [dst_data.shape],
            [dst_data.min(), dst_data.mean(), dst_data.max()],
            [np.nanmin(dst_data), np.nanmean(dst_data), np.nanmax(dst_data)],
        ]
        _LOGGER.info(f"dst_data stats: {stats=}")


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
    # processor.run()
    # processor.finalize()


if __name__ == "__main__":
    main()
