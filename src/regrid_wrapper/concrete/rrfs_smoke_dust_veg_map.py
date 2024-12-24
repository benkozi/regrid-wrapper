import esmpy
import numpy as np
import xarray as xr
from netCDF4 import Dataset

from regrid_wrapper.concrete.rave_to_rrfs import DatasetToGrid
from regrid_wrapper.model.spec import GenerateWeightFileAndRegridFields
from regrid_wrapper.strategy.operation import AbstractRegridOperation
from mpi4py import MPI


class RrfsSmokeDustVegetationMap(AbstractRegridOperation):

    def run(self) -> None:
        assert isinstance(self._spec, GenerateWeightFileAndRegridFields)

        src_grid_def = DatasetToGrid(
            path=self._spec.src_path,
            x_center="geolat",
            y_center="geolon",
            x_corner=None,
            y_corner=None,
            fields=("emiss_factor",),
        )
        src_grid = src_grid_def.create_esmpy_grid()

        dst_grid_def = DatasetToGrid(
            path=self._spec.dst_path,
            x_center="grid_lont",
            y_center="grid_latt",
        )
        dst_grid = dst_grid_def.create_esmpy_grid()

        src_field = list(src_grid_def.iter_esmpy_fields(src_grid))[0]
        dst_field = dst_grid_def.create_empty_esmpy_field(dst_grid, "emiss_factor")

        ds_in = xr.open_dataset(self._spec.src_path)
        ds_out = xr.open_dataset(self._spec.dst_path)

        ds = Dataset(
            self._spec.output_filename,
            mode="w",
            parallel=True,
            comm=MPI.COMM_WORLD,
            info=MPI.Info(),
        )
        ds.setncatts(ds_in.attrs)
        dlat = ds.createDimension("lat", ds_out.sizes["grid_yt"])
        dlon = ds.createDimension("lon", ds_out.sizes["grid_xt"])
        dgeolat = ds.createDimension("geolat", ds_out.sizes["grid_yt"])
        dgeolon = ds.createDimension("geolon", ds_out.sizes["grid_xt"])
        geolon = ds.createVariable("geolon", np.float_, ["lat", "lon"])
        geolon.setncatts(ds_in["geolon"].attrs)
        geolat = ds.createVariable("geolat", np.float_, ["lat", "lon"])
        geolat.setncatts(ds_in["geolat"].attrs)
        geolat[:] = ds_out[dst_grid_def.y_center]
        geolon[:] = ds_out[dst_grid_def.x_center]
        emiss_factor = ds.createVariable(
            "emiss_factor", np.float_, ["geolat", "geolon"]
        )
        emiss_factor.setncatts(ds_in["emiss_factor"].attrs)

        ds_in.close()
        ds_out.close()

        self._logger.info("starting weight file generation")
        regrid_method = esmpy.RegridMethod.BILINEAR
        regridder = esmpy.Regrid(
            src_field,
            dst_field,
            regrid_method=regrid_method,
            filename=str(self._spec.output_weight_filename),
            unmapped_action=esmpy.UnmappedAction.IGNORE,
            ignore_degenerate=True,
        )

        dst_grid_def.fill_array(
            dst_grid, emiss_factor, dst_field.data, slice_side="lhs"
        )

        ds.close()
