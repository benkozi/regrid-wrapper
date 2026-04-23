from datetime import datetime, timedelta
from functools import cached_property
from pathlib import Path
from typing import Any, Iterator

import xarray as xr

from regrid_wrapper.app.chem_regrid import CR_LOGGER
from regrid_wrapper.app.chem_regrid.dataset.context.base import (
    AbstractDatasetRegridContext,
    RegridFilePair,
)
from regrid_wrapper.esmpy.field_wrapper import HasNcAttrsType


class GOES_DatasetRegridContext(AbstractDatasetRegridContext):
    """Regrid context for GOES (Geostationary Operational Environmental Satellite) AOD data."""

    search_time_format: str = "%Y%j%H"

    def get_src_grid_path(self) -> Path:
        return self.workdir / "goes19_abi_conus_interpolated_lat_lon.nc"

    @staticmethod
    def _get_nc_attrs_(src: HasNcAttrsType) -> dict[str, Any]:
        return {}

    def _get_src_search_path(self, this_time: datetime) -> str:
        this_str = this_time.strftime(self.search_time_format)
        return str(self.input_dir / ("OR_ABI-L2-AODC-M6_G18_s" + this_str + "*"))

    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        date_to_process = self.dates_needed[0]
        src_paths = self.find_latest_src_file(date_to_process, max_lookback_hours=2)
        files_to_cat = src_paths
        CR_LOGGER.info(f"will cat files: {files_to_cat=}")
        if self.rank == 0:
            with xr.open_mfdataset(files_to_cat, combine="nested", concat_dim="file") as ds:
                # 2. Calculate the nanmean across the new 'file' dimension
                # skipna=True (default) ensures it behaves like np.nanmean
                ds_averaged = ds["AOD"].mean(dim="file", skipna=True)
            # CR_LOGGER.debug(ds_averaged)
            ds_averaged.encoding.update({"dtype": "float32", "_FillValue": -999})
            ds_averaged.to_netcdf(self.output_dir / "test_goes_aod_merged.nc")

        if not src_paths:
            msg = f"No matching GOES files found for {date_to_process} (even after lookback)."
            CR_LOGGER.error(msg)
            raise ValueError(msg)

        CR_LOGGER.info("Reading merged GOES file: test_goes_aod_merged.nc")
        # src_path = src_paths[0]
        src_path = self.output_dir / "test_goes_aod_merged.nc"
        new_dst_path = self.output_dir / (self.mesh_name + "-GOES-" + date_to_process + ".nc")
        fp = RegridFilePair(src_path=src_path, dst_path=new_dst_path)
        for _ in range(1):
            yield fp

    @cached_property
    def dates_needed(self) -> list[str]:
        dates_needed = []
        for i in range(25):
            if self.ebb_dcycle == 1:  # Same-day emissions
                x = self.dt_spec.datetime + timedelta(hours=i)
            elif self.ebb_dcycle == -1 or self.ebb_dcycle == 2:  # Persistence (-1) or forecasted (2) needs prev 24 hours
                x = self.dt_spec.datetime - timedelta(hours=i)
            else:
                CR_LOGGER.info("EBB_DCYLE selection not recognized, reverting to same day, ebb_dcycle = 1")
                x = self.dt_spec.datetime - timedelta(hours=i)
            y = x.strftime("%Y%m%d%H")
            dates_needed.append(y)
        return dates_needed
