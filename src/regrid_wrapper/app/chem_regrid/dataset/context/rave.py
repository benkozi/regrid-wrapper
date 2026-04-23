from datetime import datetime, timedelta
from functools import cached_property
from pathlib import Path
from typing import Any, Iterator, Union

import esmpy
import numpy as np
from pydantic import PrivateAttr

from regrid_wrapper.app.chem_regrid import CR_LOGGER
from regrid_wrapper.app.chem_regrid.dataset.context.base import (
    AbstractDatasetRegridContext,
    RegridFilePair,
)
from regrid_wrapper.app.chem_regrid.dataset.src_field import SrcField
from regrid_wrapper.esmpy.field_wrapper import (
    DimensionCollection,
    FieldWrapper,
    NcToField,
    load_variable_data,
    open_nc,
    set_variable_data,
)


class RAVE_DatasetRegridContext(AbstractDatasetRegridContext):
    """Regrid context for RAVE (Regional Real-time Biomass Burning Emissions) data."""

    var_names_to_copy_to_output_file: tuple[str, ...] = ("latCell", "lonCell", "areaCell", "xtime")
    _area_data: np.ndarray | None = PrivateAttr(default=None)

    def get_area_data(self, raw_src_fwrap: FieldWrapper) -> np.ndarray:
        """Loads and returns area information from the RAVE source file."""
        if self._area_data is None:
            area_fwrap = NcToField(
                path=self.src_path,
                name="area",
                gwrap=raw_src_fwrap.gwrap,
                dim_time=None,
            ).create_field_wrapper()
            self._area_data = area_fwrap.data
        return self._area_data

    def update_src_field_wrapper(self, raw_src_fwrap: FieldWrapper) -> None:
        field_name = raw_src_fwrap.value.name
        src_data = raw_src_fwrap.data

        # RAVE methane, convert from kg/hr to mol/m2/s
        if field_name == "CH4":
            conv_aer = (1.0 / 16.0) * 1000.0
        elif field_name == "CO":
            conv_aer = (1.0 / 28.0) * 1000.0
        elif field_name == "NH3":
            conv_aer = (1.0 / 17.0) * 1000.0
        elif field_name == "NOx":
            conv_aer = ((1.0 / 30.0) + (1.0 / 46.0)) / 2.0 * 1000.0
        else:
            conv_aer = 1.0

        if field_name in ("PM25", "TPM"):
            # If RAVE aerosol emissions, convert from kg/hr to ug/m2/s
            src_data[:] = np.where(
                src_data < 0.0, 0.0, src_data * 1.0e3 / self.get_area_data(raw_src_fwrap)[:, :, np.newaxis] / 3600.0
            )
        elif field_name in ("CH4", "NH3", "SO2", "CO", "NOx"):
            # If RAVE gas emissions, convert from kg/hr to mol/m2/s
            src_data[:] = np.where(
                src_data < 0.0, 0.0, conv_aer * src_data / self.get_area_data(raw_src_fwrap)[:, :, np.newaxis] / 3600.0
            )
        elif field_name in ("FRE", "FRP_MEAN"):
            # For FRE, FRP, don't multiply area by 1.e6, cancelled out by MW to W conversion
            src_data[:] = np.where(src_data < 0.0, 0.0, src_data / (self.get_area_data(raw_src_fwrap)[:, :, np.newaxis]))
        else:
            src_data[:] = np.where(src_data < 0.0, 0.0, conv_aer * src_data)

        src_data[:] = np.where(np.isnan(src_data), 0.0, src_data)

    def _get_src_search_path(self, this_time: datetime) -> str:
        this_str = this_time.strftime(self.search_time_format)
        return str(self.input_dir / ("RAVE-HrlyEmiss-3km_v2r0_blend_s" + this_str + "*"))

    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        for date_to_process in self.dates_needed:
            CR_LOGGER.info(f"RAVE processing {date_to_process=}")
            src_paths = self.find_latest_src_file(date_to_process, max_lookback_hours=24)
            if not src_paths:
                CR_LOGGER.warn(f"No matching files found for {date_to_process} (even after lookback).")
                continue

            CR_LOGGER.info(f"Reading RAVE file: {src_paths=}")
            src_path = src_paths[0]
            new_dst_path = self.output_dir / (self.mesh_name + "-RAVE-" + date_to_process + ".nc")

            yield RegridFilePair(
                src_path=Path(src_path),
                dst_path=new_dst_path,
            )

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
                x = self.dt_spec.datetime + timedelta(hours=i)

            y = x.strftime("%Y%m%d%H")
            dates_needed.append(y)
        return dates_needed

    def transform_regridded_data(
        self,
        src_field: SrcField,
        dst_field: FieldWrapper,
        ds: Any,
        dims: DimensionCollection,
    ) -> np.ndarray:
        if src_field.name in ("FRP_MEAN", "FRE"):
            # Multiply FRE/FRP by output area so it is back to W or J*s
            area_dims = DimensionCollection(value=(dims.get("nCells"),))
            area_subset = load_variable_data(ds.variables["areaCell"], area_dims)
            area_subset = area_subset.reshape(dst_field.dims.shape_local)
            dst_field_data = dst_field.data * area_subset
            return dst_field_data
        return dst_field.data

    def post_regrid_processing(
        self,
        src_field: SrcField,
        regridder: Union[esmpy.Regrid, esmpy.RegridFromFile],
        processor: Any,
        dims: DimensionCollection,
    ) -> None:
        if src_field.name == "TPM":
            with open_nc(self.new_dst_path, mode="a") as ds:
                CR_LOGGER.info("calculating PM10 as TPM - PM25")
                src_fwrap_ttl = processor.create_src_field_wrapper(field_name="TPM")
                src_fwrap_p25 = processor.create_src_field_wrapper(field_name="PM25")

                dst_field_ttl = processor.get_dst_fwrap()
                dst_field_ttl.data.fill(0.0)
                regridder(src_fwrap_ttl.value, dst_field_ttl.value)

                dst_field_p25 = processor.get_dst_fwrap()
                dst_field_p25.data.fill(0.0)
                regridder(src_fwrap_p25.value, dst_field_p25.value)

                # use the same src_field metadata for PM10
                var = ds.createVariable(
                    "PM10",
                    src_field.dtype,
                    [dim.name[0] for dim in dims.value],
                    fill_value=src_field.fill_value,
                )
                for k, v in src_field.attrs.items():
                    setattr(var, k, v)

                data3 = dst_field_ttl.data - dst_field_p25.data
                set_variable_data(
                    var,
                    dst_field_ttl.dims,
                    data3,
                    collective=True,
                )
            src_fwrap_ttl.value.destroy()
            src_fwrap_p25.value.destroy()
