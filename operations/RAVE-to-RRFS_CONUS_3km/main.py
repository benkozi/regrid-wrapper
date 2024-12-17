import esmpy
import numpy as np

from regrid_wrapper.model.regrid_operation import (
    GenerateWeightFileSpec,
    AbstractRegridOperation,
)
import xarray as xr

from regrid_wrapper.strategy.core import RegridProcessor


class RaveToRrrfsConus3km(AbstractRegridOperation):
    def run(self) -> None:
        assert isinstance(self._spec, GenerateWeightFileSpec)

        ds_in = xr.open_dataset(self._spec.src_path)
        ds_out = xr.open_dataset(self._spec.dst_path)

        self._logger.info("extract coordinate data")
        src_latt = ds_in["grid_latt"].values
        src_lont = ds_in["grid_lont"].values
        tgt_latt = ds_out["grid_latt"].values
        tgt_lont = ds_out["grid_lont"].values

        self._logger.info("unwrap coordinates if necessary")
        src_lont2 = np.where(src_lont > 0, src_lont, src_lont + 360)

        self._logger.info("create esmf grids")
        src_shape = src_latt.shape
        tgt_shape = tgt_latt.shape
        src_grid = esmpy.Grid(
            np.array(src_shape),
            staggerloc=esmpy.StaggerLoc.CENTER,
            coord_sys=esmpy.CoordSys.SPH_DEG,
        )
        tgt_grid = esmpy.Grid(
            np.array(tgt_shape),
            staggerloc=esmpy.StaggerLoc.CENTER,
            coord_sys=esmpy.CoordSys.SPH_DEG,
        )

        self._logger.info("get local bounds for setting coordinates")
        src_x_lb, src_x_ub = (
            src_grid.lower_bounds[esmpy.StaggerLoc.CENTER][1],
            src_grid.upper_bounds[esmpy.StaggerLoc.CENTER][1],
        )
        src_y_lb, src_y_ub = (
            src_grid.lower_bounds[esmpy.StaggerLoc.CENTER][0],
            src_grid.upper_bounds[esmpy.StaggerLoc.CENTER][0],
        )
        tgt_x_lb, tgt_x_ub = (
            tgt_grid.lower_bounds[esmpy.StaggerLoc.CENTER][1],
            tgt_grid.upper_bounds[esmpy.StaggerLoc.CENTER][1],
        )
        tgt_y_lb, tgt_y_ub = (
            tgt_grid.lower_bounds[esmpy.StaggerLoc.CENTER][0],
            tgt_grid.upper_bounds[esmpy.StaggerLoc.CENTER][0],
        )

        self._logger.info("set coordinates within the local extents of each grid")
        src_cen_lon = src_grid.get_coords(0)
        src_cen_lat = src_grid.get_coords(1)
        src_cen_lon[...] = src_lont2[src_y_lb:src_y_ub, src_x_lb:src_x_ub]
        src_cen_lat[...] = src_latt[src_y_lb:src_y_ub, src_x_lb:src_x_ub]

        tgt_cen_lon = tgt_grid.get_coords(0)
        tgt_cen_lat = tgt_grid.get_coords(1)
        tgt_cen_lon[...] = tgt_lont[tgt_y_lb:tgt_y_ub, tgt_x_lb:tgt_x_ub]
        tgt_cen_lat[...] = tgt_latt[tgt_y_lb:tgt_y_ub, tgt_x_lb:tgt_x_ub]

        self._logger.info("prepare fields on the grids")
        area = ds_in["area"]
        srcfield = esmpy.Field(src_grid, name="src")
        srcfield.data[...] = area[:, :][src_y_lb:src_y_ub, src_x_lb:src_x_ub]
        tgtfield = esmpy.Field(tgt_grid, name="dst")

        ds_in.close()
        ds_out.close()

        self._logger.info("starting weight file generation")
        regrid_method = esmpy.RegridMethod.NEAREST_DTOS
        regridder = esmpy.Regrid(
            srcfield,
            tgtfield,
            regrid_method=regrid_method,
            filename=str(self._spec.output_weight_filename),
            unmapped_action=esmpy.UnmappedAction.IGNORE,
            ignore_degenerate=True,
        )


def main() -> None:
    spec = GenerateWeightFileSpec(
        src_path="/scratch1/BMC/acomp/Johana/input_files/fix_files_Feb23/CONUS/grid_in.nc",
        dst_path="/scratch1/BMC/acomp/Johana/input_files/fix_files_Feb23/CONUS/ds_out_base.nc",
        output_weight_filename="/scratch2/NAGAPE/epic/Ben.Koziol/output-data/RAVE-to-RRFS_CONUS_3km.nc",
        esmpy_debug=True,
        name="weights-RAVE-to-RRFS_CONUS_3km",
    )
    op = RaveToRrrfsConus3km(spec=spec)
    processor = RegridProcessor(operation=op)
    processor.execute()


if __name__ == "__main__":
    main()
