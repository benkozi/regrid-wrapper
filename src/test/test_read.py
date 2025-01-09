from pathlib import Path

import esmpy

from regrid_wrapper.esmpy.field_wrapper import GridWrapper, NcToGrid, GridSpec


def _create_grid_wrapper_(path: Path) -> GridWrapper:
    nc2grid = NcToGrid(
        path=path,
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
    gwrap = nc2grid.create_grid_wrapper()
    return gwrap


def run() -> None:

    src_gwrap = _create_grid_wrapper_(
        "/scratch2/NAGAPE/epic/SRW-AQM_DATA/fix_smoke/RRFS_NA_3km/grid_in.nc"
    )
    dst_gwrap = _create_grid_wrapper_(
        "/scratch2/NAGAPE/epic/Ben.Koziol/output-data/RRFS_NA_13km.nc"
    )

    src_field = esmpy.Field(src_gwrap.value, name="src")
    dst_field = esmpy.Field(dst_gwrap.value, name="dst")

    # regrid_method = esmpy.RegridMethod.CONSERVE
    # regridder = esmpy.Regrid(
    #     src_field,
    #     dst_field,
    #     regrid_method=regrid_method,
    #     filename=str(self._spec.output_weight_filename),
    #     unmapped_action=esmpy.UnmappedAction.IGNORE,
    #     ignore_degenerate=True,
    # )

    # Uncomment to test read back from file
    _ = esmpy.RegridFromFile(
        src_field,
        dst_field,
        str(
            "/scratch2/NAGAPE/epic/Ben.Koziol/tmp-smoke-fix-dir/RRFS_NA_13km/weight_file.nc"
        ),
    )


if __name__ == "__main__":
    run()
