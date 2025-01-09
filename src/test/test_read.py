from pathlib import Path

import esmpy
import numpy as np

import netCDF4 as nc

esmpy.Manager(debug=True)


# def _create_grid_wrapper_(path: Path) -> GridWrapper:
#     nc2grid = NcToGrid(
#         path=path,
#         spec=GridSpec(
#             x_center="grid_lont",
#             y_center="grid_latt",
#             x_dim=("grid_xt",),
#             y_dim=("grid_yt",),
#             x_corner="grid_lon",
#             y_corner="grid_lat",
#             x_corner_dim=("grid_x",),
#             y_corner_dim=("grid_y",),
#         ),
#     )
#     gwrap = nc2grid.create_grid_wrapper()
#     return gwrap


def copy_nc(
    src_path: Path,
    dst_path: Path,
) -> None:
    with nc.Dataset(src_path, mode="r") as src:
        with nc.Dataset(dst_path, mode="w", clobber=True) as dst:
            for dim in src.dimensions:
                dst.createDimension(dim, size=src.dimensions[dim].size)
            for varname, var in src.variables.items():
                new_var = dst.createVariable(varname, var.dtype, var.dimensions)
                new_var[:] = var[:]


def run() -> None:

    # src_gwrap = _create_grid_wrapper_(
    #     "/scratch2/NAGAPE/epic/SRW-AQM_DATA/fix_smoke/RRFS_NA_3km/grid_in.nc"
    # )
    # dst_gwrap = _create_grid_wrapper_(
    #     "/scratch2/NAGAPE/epic/Ben.Koziol/tmp-smoke-fix-dir/RRFS_NA_13km/ds_out_base.nc"
    # )
    weight_file = (
        "/scratch2/NAGAPE/epic/Ben.Koziol/tmp-smoke-fix-dir/RRFS_NA_13km/weight_file.nc"
    )
    new_weights = "/home/Benjamin.Koziol/new_weights.nc"
    copy_nc(weight_file, new_weights)

    grid = esmpy.Grid(np.array([2, 2]))

    src_field = esmpy.Field(grid, name="src")
    dst_field = esmpy.Field(grid, name="dst")

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
        new_weights,
        # str("/scratch2/NAGAPE/epic/SRW-AQM_DATA/fix_smoke/RRFS_NA_3km/grid_in.nc"),
    )


if __name__ == "__main__":
    run()
