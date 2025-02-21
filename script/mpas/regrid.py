from pathlib import Path

import esmpy
from pydantic import BaseModel
from pyremap import MpasCellMeshDescriptor

from regrid_wrapper.esmpy.field_wrapper import GridSpec, NcToGrid


class Context(BaseModel):
    src_path: Path
    dst_path: Path
    tmp_path: Path


class RegridProcessor(BaseModel):
    context: Context

    def initialize(self) -> None:
        print("writing mpas scrip grid")
        mpas_desc = MpasCellMeshDescriptor(str(self.context.dst_path), "na15km.init")
        scrip_path = self.context.tmp_path / "mpas_scrip.nc"
        mpas_desc.to_scrip(str(scrip_path))

        print("create source grid")
        nc2grid = NcToGrid(
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
        )
        src_gwrap = nc2grid.create_grid_wrapper()

        print("create destination mesh")
        dst_mesh = esmpy.Mesh(filename=str(scrip_path), filetype=esmpy.FileFormat.SCRIP)

        print("create regridder")
        src_field = esmpy.Field(src_gwrap.value, name="src")
        dst_field = esmpy.Field(dst_mesh, name="dst")
        regridder = esmpy.Regrid(
            srcfield=src_field,
            dstfield=dst_field,
            regrid_method=esmpy.RegridMethod.CONSERVE,
            unmapped_action=esmpy.UnmappedAction.ERROR,
            ignore_degenerate=False,
        )

    def _create_regrid_(self) -> esmpy.Regrid:
        src_grid = esmpy.Grid(filename=self.scrip_path)


def main() -> None:
    data_dir = Path("/scratch1/NCEPDEV/stmp2/Benjamin.Koziol/data/mpas")
    src_path = (
        data_dir
        / "RAVE-HrlyEmiss-3km_v1r3_blend_s202407240000000_e202407240059590_c202407240203140.nc"
    )
    dst_path = data_dir / "na15km.init.nc"
    tmp_path = Path("/home/Benjamin.Koziol/htmp")
    context = Context(src_path=src_path, dst_path=dst_path, tmp_path=tmp_path)
    processor = RegridProcessor(context=context)
    processor.initialize()
    # processor.run()
    # processor.finalize()


if __name__ == "__main__":
    main()
