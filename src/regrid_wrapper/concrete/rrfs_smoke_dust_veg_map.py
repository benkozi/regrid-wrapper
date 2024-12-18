import esmpy
import numpy as np
import xarray as xr
from netCDF4 import Dataset

from regrid_wrapper.model.spec import (
    GenerateWeightFileSpec,
    GenerateWeightFileAndRegridFields,
)
from regrid_wrapper.strategy.operation import AbstractRegridOperation
from mpi4py import MPI


class RrfsSmokeDustVegetationMap(AbstractRegridOperation):
    def run(self) -> None:
        assert isinstance(self._spec, GenerateWeightFileAndRegridFields)

        ds_in = xr.open_dataset(self._spec.src_path)
        ds_out = xr.open_dataset(self._spec.dst_path)

        self._logger.info("extract coordinate data")
        src_latt = ds_in["geolat"].values
        src_lont = ds_in["geolon"].values
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
        if len(self._spec.fields) != 1:
            self._logger.error("one field expected")
            raise ValueError
        data = ds_in[self._spec.fields[0]]
        data_local = data[src_y_lb:src_y_ub, src_x_lb:src_x_ub]
        srcfield = esmpy.Field(src_grid, name="src")
        assert srcfield.data.shape == data_local.shape
        srcfield.data[:] = data_local
        # srcfield.data[...] = data[:, :][src_y_lb:src_y_ub, src_x_lb:src_x_ub]
        tgtfield = esmpy.Field(tgt_grid, name="dst")

        # https://github.com/Unidata/netcdf4-python/blob/master/examples/mpi_example.py
        ds = Dataset(
            self._spec.output_filename,
            mode="w",
            parallel=True,
            comm=MPI.COMM_WORLD,
            info=MPI.Info(),
        )
        dlat = ds.createDimension("lat", ds_out.sizes["grid_yt"])
        dlon = ds.createDimension("lon", ds_out.sizes["grid_xt"])
        dgeolat = ds.createDimension("geolat", ds_out.sizes["grid_yt"])
        dgeolon = ds.createDimension("geolon", ds_out.sizes["grid_xt"])
        geolon = ds.createVariable("geolon", np.float_, ["lat", "lon"])
        geolon.setncatts(ds_in["geolon"].attrs)
        geolat = ds.createVariable("geolat", np.float_, ["lat", "lon"])
        geolat.setncatts(ds_in["geolat"].attrs)
        # if MPI.COMM_WORLD.Get_rank() == 0:
        #     self._logger.info("setting coordinates")
        #     geolat[0, 0] = 5
        #     geolon[0, 0] = 5
        geolat[:] = tgt_latt
        geolon[:] = tgt_lont
        emiss_factor = ds.createVariable(
            "emiss_factor", np.float_, ["geolat", "geolon"]
        )
        emiss_factor.setncatts(ds_in["emiss_factor"].attrs)

        # out_ds = xr.Dataset()
        # out_ds.attrs = ds_in.attrs
        # geolon = xr.DataArray(
        #     data=tgt_lont, dims=["geolat", "geolon"], attrs=ds_in["geolon"].attrs
        # )
        # geolat = xr.DataArray(
        #     data=tgt_latt, dims=["geolat", "geolon"], attrs=ds_in["geolat"].attrs
        # )
        # emiss_factor = xr.DataArray(
        #     data=tgtfield.data,
        #     dims=["geolat", "geolon"],
        #     coords=dict(geolat=geolat, geolon=geolon),
        #     attrs=ds_in["emiss_factor"].attrs,
        # )
        # out_ds["geolon"] = geolon
        # out_ds["geolat"] = geolat
        # out_ds["emiss_factor"] = emiss_factor
        # out_ds.to_netcdf(self._spec.output_filename)
        # tdk

        ds_in.close()
        ds_out.close()

        self._logger.info("starting weight file generation")
        regrid_method = esmpy.RegridMethod.BILINEAR
        regridder = esmpy.Regrid(
            srcfield,
            tgtfield,
            regrid_method=regrid_method,
            filename=str(self._spec.output_weight_filename),
            unmapped_action=esmpy.UnmappedAction.IGNORE,
            ignore_degenerate=True,
        )

        emiss_factor[tgt_y_lb:tgt_y_ub, tgt_x_lb:tgt_x_ub] = tgtfield.data
        ds.close()
