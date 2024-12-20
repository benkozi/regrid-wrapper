import esmpy
import numpy as np
import xarray as xr

from regrid_wrapper.model.spec import GenerateWeightFileSpec
from regrid_wrapper.strategy.operation import AbstractRegridOperation


class RaveToRrfs(AbstractRegridOperation):
    def run(self) -> None:
        assert isinstance(self._spec, GenerateWeightFileSpec)

        ds_in = xr.open_dataset(self._spec.src_path)
        ds_out = xr.open_dataset(self._spec.dst_path)

        self._logger.info("extract coordinate data")
        src_latt = np.swapaxes(ds_in["grid_latt"].values, 0, 1)
        src_lont = np.swapaxes(ds_in["grid_lont"].values, 0, 1)
        tgt_latt = np.swapaxes(ds_out["grid_latt"].values, 0, 1)
        tgt_lont = np.swapaxes(ds_out["grid_lont"].values, 0, 1)

        self._logger.info("unwrap coordinates if necessary")
        src_lont2 = np.where(src_lont > 0, src_lont, src_lont + 360)

        self._logger.info("create esmf grids")
        x, y = 0, 1
        src_shape = src_latt.shape
        tgt_shape = tgt_latt.shape
        src_grid = esmpy.Grid(
            np.array(src_shape),
            staggerloc=esmpy.StaggerLoc.CENTER,
            coord_sys=esmpy.CoordSys.SPH_DEG,
        )
        src_grid.add_coords([esmpy.StaggerLoc.CORNER])
        tgt_grid = esmpy.Grid(
            np.array(tgt_shape),
            staggerloc=esmpy.StaggerLoc.CENTER,
            coord_sys=esmpy.CoordSys.SPH_DEG,
        )
        tgt_grid.add_coords([esmpy.StaggerLoc.CORNER])

        self._logger.info("get local bounds for setting coordinates")
        src_x_lb, src_x_ub = (
            src_grid.lower_bounds[esmpy.StaggerLoc.CENTER][x],
            src_grid.upper_bounds[esmpy.StaggerLoc.CENTER][x],
        )
        src_y_lb, src_y_ub = (
            src_grid.lower_bounds[esmpy.StaggerLoc.CENTER][y],
            src_grid.upper_bounds[esmpy.StaggerLoc.CENTER][y],
        )
        tgt_x_lb, tgt_x_ub = (
            tgt_grid.lower_bounds[esmpy.StaggerLoc.CENTER][x],
            tgt_grid.upper_bounds[esmpy.StaggerLoc.CENTER][x],
        )
        tgt_y_lb, tgt_y_ub = (
            tgt_grid.lower_bounds[esmpy.StaggerLoc.CENTER][y],
            tgt_grid.upper_bounds[esmpy.StaggerLoc.CENTER][y],
        )

        self._logger.info("set coordinates within the local extents of each grid")
        src_cen_lon = src_grid.get_coords(x)
        src_cen_lat = src_grid.get_coords(y)
        src_cen_lon[:] = src_lont2[src_x_lb:src_x_ub, src_y_lb:src_y_ub]
        src_cen_lat[:] = src_latt[src_x_lb:src_x_ub, src_y_lb:src_y_ub]

        tgt_cen_lon = tgt_grid.get_coords(x)
        tgt_cen_lat = tgt_grid.get_coords(y)
        tgt_cen_lon[:] = tgt_lont[tgt_x_lb:tgt_x_ub, tgt_y_lb:tgt_y_ub]
        tgt_cen_lat[:] = tgt_latt[
            tgt_x_lb:tgt_x_ub,
            tgt_y_lb:tgt_y_ub,
        ]

        self._logger.info("set corner coordinates")
        src_x_lb_c, src_x_ub_c = (
            src_grid.lower_bounds[esmpy.StaggerLoc.CORNER][x],
            src_grid.upper_bounds[esmpy.StaggerLoc.CORNER][x],
        )
        src_y_lb_c, src_y_ub_c = (
            src_grid.lower_bounds[esmpy.StaggerLoc.CORNER][y],
            src_grid.upper_bounds[esmpy.StaggerLoc.CORNER][y],
        )
        tgt_x_lb_c, tgt_x_ub_c = (
            tgt_grid.lower_bounds[esmpy.StaggerLoc.CORNER][x],
            tgt_grid.upper_bounds[esmpy.StaggerLoc.CORNER][x],
        )
        tgt_y_lb_c, tgt_y_ub_c = (
            tgt_grid.lower_bounds[esmpy.StaggerLoc.CORNER][y],
            tgt_grid.upper_bounds[esmpy.StaggerLoc.CORNER][y],
        )

        src_cen_lon_c = src_grid.get_coords(x, staggerloc=esmpy.StaggerLoc.CORNER)
        src_cen_lat_c = src_grid.get_coords(y, staggerloc=esmpy.StaggerLoc.CORNER)
        src_lon_c = np.swapaxes(ds_in["grid_lon"].values, 0, 1)
        src_lat_c = np.swapaxes(ds_in["grid_lat"].values, 0, 1)
        src_cen_lon_c[:] = src_lon_c[src_x_lb_c:src_x_ub_c, src_y_lb_c:src_y_ub_c]
        src_cen_lat_c[:] = src_lat_c[src_x_lb_c:src_x_ub_c, src_y_lb_c:src_y_ub_c]

        tgt_cen_lon_c = tgt_grid.get_coords(x, staggerloc=esmpy.StaggerLoc.CORNER)
        tgt_cen_lat_c = tgt_grid.get_coords(y, staggerloc=esmpy.StaggerLoc.CORNER)
        tgt_lon_c = np.swapaxes(ds_out["grid_lon"].values, 0, 1)
        tgt_lat_c = np.swapaxes(ds_out["grid_lat"].values, 0, 1)
        tgt_cen_lon_c[:] = tgt_lon_c[tgt_x_lb_c:tgt_x_ub_c, tgt_y_lb_c:tgt_y_ub_c]
        tgt_cen_lat_c[:] = tgt_lat_c[tgt_x_lb_c:tgt_x_ub_c, tgt_y_lb_c:tgt_y_ub_c]

        self._logger.info("prepare fields on the grids")
        # area = ds_in["area"]
        srcfield = esmpy.Field(src_grid, name="src")
        # srcfield.data[...] = area[:, :][src_y_lb:src_y_ub, src_x_lb:src_x_ub]
        tgtfield = esmpy.Field(tgt_grid, name="dst")

        ds_in.close()
        ds_out.close()

        self._logger.info("starting weight file generation")
        regrid_method = esmpy.RegridMethod.CONSERVE
        regridder = esmpy.Regrid(
            srcfield,
            tgtfield,
            regrid_method=regrid_method,
            filename=str(self._spec.output_weight_filename),
            unmapped_action=esmpy.UnmappedAction.IGNORE,
            ignore_degenerate=True,
        )
