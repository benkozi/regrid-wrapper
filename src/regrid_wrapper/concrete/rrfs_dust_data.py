from copy import copy
from typing import Tuple

import esmpy
import numpy as np
import xarray as xr
from netCDF4 import Dataset
from pydantic import BaseModel, ConfigDict

from regrid_wrapper.common import ncdump
from regrid_wrapper.concrete.rave_to_rrfs import DatasetToGrid
from regrid_wrapper.context.comm import COMM
from regrid_wrapper.esmpy.field_wrapper import NcToGrid, GridSpec, NcToField, resize_nc
from regrid_wrapper.model.spec import GenerateWeightFileAndRegridFields
from regrid_wrapper.strategy.operation import AbstractRegridOperation
from mpi4py import MPI


class RrfsDustDataEnv(BaseModel):
    model_config = ConfigDict(frozen=True)
    fields: Tuple[str, ...] = ["uthr", "sand", "clay", "rdrag", "ssm"]


RRFS_DUST_DATA_ENV = RrfsDustDataEnv()


class RrfsDustData(AbstractRegridOperation):

    def run(self) -> None:
        assert isinstance(self._spec, GenerateWeightFileAndRegridFields)

        src_grid_def = NcToGrid(
            path=self._spec.src_path,
            spec=GridSpec(
                x_center="geolon",
                y_center="geolat",
                x_dim="lon",
                y_dim="lat",
                x_corner=None,
                y_corner=None,
            ),
        )
        src_gwrap = src_grid_def.create_grid_wrapper()

        dst_grid_def = NcToGrid(
            path=self._spec.dst_path,
            spec=GridSpec(
                x_center="grid_lont",
                y_center="grid_latt",
                x_dim="grid_xt",
                y_dim="grid_yt",
            ),
        )
        dst_gwrap = dst_grid_def.create_grid_wrapper()

        src_nc2field = NcToField(
            path=self._spec.src_path,
            name=RRFS_DUST_DATA_ENV.fields[0],
            dim_time="time",
            gwrap=src_gwrap,
        )
        src_fwrap = src_nc2field.create_field_wrapper()

        new_sizes = {
            src_nc2field.dim_time: src_fwrap.dims.get(src_nc2field.dim_time).size,
            src_grid_def.spec.x_dim: dst_gwrap.dims.get(dst_grid_def.spec.x_dim).size,
            src_grid_def.spec.y_dim: dst_gwrap.dims.get(dst_grid_def.spec.y_dim).size,
        }
        self._logger.info(f"resizing netcdf. new_sizes={new_sizes}")
        resize_nc(self._spec.src_path, self._spec.output_filename, new_sizes)

        dst_gwrap_output = copy(dst_gwrap)
        dst_gwrap_output.spec = src_gwrap.spec
        dst_gwrap_output.dims = src_gwrap.dims
        dst_gwrap_output.fill_nc_variables(self._spec.output_filename)

        # dump = ncdump(self._spec.output_filename)  # tdk:rm

        # dst_grid_output_def = NcToGrid(
        #     path=self._spec.output_filename,
        #     spec=GridSpec(
        #         x_center="geolon",
        #         y_center="geolat",
        #         x_dim="lon",
        #         y_dim="lat",
        #     ),
        # )
        # dst_output_gwrap = dst_grid_output_def.create_grid_wrapper()

        dst_nc2field = NcToField(
            path=self._spec.output_filename,
            name=RRFS_DUST_DATA_ENV.fields[0],
            dim_time="time",
            gwrap=dst_gwrap_output,
        )
        dst_fwrap = dst_nc2field.create_field_wrapper()

        # src_field = list(
        #     src_grid_def.iter_esmpy_fields(
        #         src_grid, ndbounds=(12,), esmpy_dims=("geolat", "geolon", "time")
        #     )
        # )[0]
        # dst_field = dst_grid_def.create_empty_esmpy_field(
        #     dst_grid, "emiss_factor", ndbounds=(12,)
        # )

        self._logger.info("starting weight file generation")
        # tdk: need to regrid multiple fields
        # tdk: need to test with actual dust fields
        # tdk: need to make sure the regridding methods are correct
        # tdk: remove fields from spec - just hard code them
        regrid_method = esmpy.RegridMethod.BILINEAR
        regridder = esmpy.Regrid(
            src_fwrap.value,
            dst_fwrap.value,
            regrid_method=regrid_method,
            filename=str(self._spec.output_weight_filename),
            unmapped_action=esmpy.UnmappedAction.ERROR,
            # ignore_degenerate=True,
        )

        for field_to_regrid in RRFS_DUST_DATA_ENV.fields:
            self._logger.info(f"regridding field: {field_to_regrid}")
            src_nc2field = NcToField(
                path=self._spec.src_path,
                name=field_to_regrid,
                dim_time="time",
                gwrap=src_gwrap,
            )
            src_fwrap = src_nc2field.create_field_wrapper()

            dst_nc2field = NcToField(
                path=self._spec.output_filename,
                name=field_to_regrid,
                dim_time="time",
                gwrap=dst_gwrap_output,
            )
            dst_fwrap = dst_nc2field.create_field_wrapper()
            regridder(src_fwrap.value, dst_fwrap.value, zero_region=esmpy.Region.SELECT)
            dst_fwrap.fill_nc_variable(self._spec.output_filename)

        # self._logger.info("filling destination array")
        # ds_in = xr.open_dataset(self._spec.src_path)
        # ds_out = xr.open_dataset(self._spec.dst_path)
        #
        # ds = Dataset(
        #     self._spec.output_filename,
        #     mode="w",
        #     parallel=True,
        #     comm=MPI.COMM_WORLD,
        #     info=MPI.Info(),
        # )
        # ds.setncatts(ds_in.attrs)
        # dlat = ds.createDimension("lat", ds_out.sizes["grid_yt"])
        # dlon = ds.createDimension("lon", ds_out.sizes["grid_xt"])
        # dgeolat = ds.createDimension("geolat", ds_out.sizes["grid_yt"])
        # dgeolon = ds.createDimension("geolon", ds_out.sizes["grid_xt"])
        # geolon = ds.createVariable("geolon", np.float_, ["lat", "lon"])
        # geolon.setncatts(ds_in["geolon"].attrs)
        # geolat = ds.createVariable("geolat", np.float_, ["lat", "lon"])
        # geolat.setncatts(ds_in["geolat"].attrs)
        # geolat[:] = ds_out[dst_grid_def.y_center]
        # geolon[:] = ds_out[dst_grid_def.x_center]
        # emiss_factor = ds.createVariable(
        #     "emiss_factor", np.float_, ["geolat", "geolon"]
        # )
        # emiss_factor.setncatts(ds_in["emiss_factor"].attrs)
        #
        # ds_in.close()
        # ds_out.close()
        #
        # dst_grid_def.fill_array(
        #     dst_grid, emiss_factor, dst_field.data, slice_side="lhs"
        # )
        #
        # ds.close()
