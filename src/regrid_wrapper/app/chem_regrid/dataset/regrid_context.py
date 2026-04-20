import glob
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from functools import cached_property
from pathlib import Path
from typing import Any, Iterator, Union

import numpy as np
from dask.array.tests.test_xarray import xr
from pydantic import BaseModel, PrivateAttr

from regrid_wrapper.app.chem_regrid.context import CR_LOGGER
from regrid_wrapper.app.chem_regrid.dataset.model import DatasetName, InterpMethod
from regrid_wrapper.app.chem_regrid.dataset.src_field import (
    AbstractSrcField,
    SrcField2d,
    SrcField2d_plusTime,
    SrcField3d,
    SrcField3d_plusTime,
)
from regrid_wrapper.context.comm import COMM
from regrid_wrapper.esmpy.field_wrapper import FieldWrapper, HasNcAttrsType, NcToField, open_nc


class DateTimeSpec(BaseModel):
    yyyy: str
    mm: str
    dd: str
    hh: str
    jjj: str
    dowh: int
    dows: str
    datetime: datetime


class RegridFilePair(BaseModel):
    src_path: Path
    dst_path: Path


class AbstractDatasetRegridContext(ABC, BaseModel):
    dataset_name: DatasetName
    workdir: Path
    src_path: Path
    dst_path: Path
    new_dst_path: Path
    desc_stats_out: Path
    weight_path: Path
    InterpMethod: InterpMethod
    scrip_path: Path
    mesh_name: str
    field_names: tuple
    x_center: str
    y_center: str
    x_dim: str
    y_dim: str
    x_corner: Union[str, None]
    y_corner: Union[str, None]
    x_corner_dim: Union[str, None]
    y_corner_dim: Union[str, None]
    level_in_name: str | None
    # level_in_size: int
    level_out_name: str | None
    level_out_size: int
    time_name: str | None
    time_size: int
    cycle: str
    ebb_dcycle: int
    input_dir: Path
    output_dir: Path
    # InterpMask: float
    write_desc_stats: bool = False

    rank: int = COMM.rank

    def update_src_field_wrapper(self, raw_src_fwrap: FieldWrapper) -> None:
        src_data = raw_src_fwrap.data
        src_data[:] = np.where(src_data < 0.0, 0.0, src_data)
        src_data[:] = np.where(np.isnan(src_data), 0.0, src_data)

    @abstractmethod
    def iter_file_pairs(self) -> Iterator[RegridFilePair]: ...

    @cached_property
    def dates_needed(self) -> list[str]:
        raise NotImplementedError(self.__class__.__name__ + " does not support dates_needed")

    @cached_property
    def num_cells(self) -> int:
        with open_nc(self.dst_path, mode="r", parallel=False) as ds:
            return len(ds.variables["latCell"])

    @cached_property
    def dt_spec(self) -> DateTimeSpec:
        yyyy = self.cycle[0:4]
        mm = self.cycle[4:6]
        dd = self.cycle[6:8]
        hh = self.cycle[8:10]
        x = datetime(int(yyyy), int(mm), int(dd), int(hh), 0, 0)
        jjj = x.strftime("%j")
        dowh = int(x.strftime("%u"))
        if dowh <= 5:
            dows = "weekdy"
        elif dowh == 6:
            dows = "satdy"
        else:
            dows = "sundy"
        return DateTimeSpec(yyyy=yyyy, mm=mm, dd=dd, hh=hh, jjj=jjj, dowh=dowh, dows=dows, datetime=x)

    @cached_property
    def src_fields(self) -> tuple[AbstractSrcField, ...]:
        src_fields = []
        with open_nc(self.src_path, mode="r") as ds:
            for field_name in self.field_names:
                read_name = field_name
                if self.dataset_name == "NGFS" and field_name == "PM25":
                    read_name = "EMIS_PM25"

                if read_name not in ds.variables:
                    raise KeyError(f"Source variable '{read_name}' not found for field '{field_name}' in {self.src_path}")
                var = ds.variables[read_name]
                init_data = {
                    "name": field_name,
                    "attrs": self._get_nc_attrs_(var),
                    "fill_value": -1.0,
                    "dtype": var.dtype,
                    "level_out_name": self.level_out_name,
                    "level_out_size": self.level_out_size,
                    "time_size": self.time_size,
                    "num_cells": self.num_cells,
                }
                if self.level_out_size == 0:
                    if self.time_size == 0:
                        app: AbstractSrcField = SrcField2d.model_validate(init_data)
                    else:
                        app = SrcField2d_plusTime.model_validate(init_data)
                else:
                    if self.time_size == 0:
                        app = SrcField3d.model_validate(init_data)
                    else:
                        app = SrcField3d_plusTime.model_validate(init_data)
                src_fields.append(app)
        CR_LOGGER.debug(f"{src_fields=}")
        return tuple(src_fields)

    @staticmethod
    def _get_nc_attrs_(src: HasNcAttrsType) -> dict[str, Any]:
        exclude = ("coordinates", "valid_range")
        return {ii: getattr(src, ii) for ii in src.ncattrs() if not ii.startswith("_") and ii not in exclude}


# Try to find the latest RAVE file available up to max_lookback_hours before target_time_str
# to avoid setting zeroes when a particular hour file is missing.
def find_latest_src_file(
    input_dir: Path, target_time_str: str, ebb_dcycle: int, dataset_name: DatasetName, max_lookback_hours: int = 24
) -> list[str]:
    """Return list of files for the latest time <= target_time_str."""
    fmt = "%Y%m%d%H"  # RAVE
    fmt2 = "%Y%j%H"  # GOES
    target_time = datetime.strptime(target_time_str, fmt)

    input_dir_str = str(input_dir)

    for h in range(max_lookback_hours + 1):
        if ebb_dcycle == -1 or ebb_dcycle == 2:
            this_time = target_time - timedelta(hours=h)
        elif ebb_dcycle == 1:
            this_time = target_time + timedelta(hours=h)
        else:
            CR_LOGGER.warning("unrecognized ebb_dcycle, reverting to same-day, ebb_dcycle = 1")
            this_time = target_time + timedelta(hours=h)

        if dataset_name == "RAVE":
            this_str = this_time.strftime(fmt)
            paths = glob.glob(input_dir_str + "/RAVE-HrlyEmiss-3km_v2r0_blend_s" + this_str + "*")
        elif dataset_name == "GOES":
            this_str = this_time.strftime(fmt2)
            paths = glob.glob(input_dir_str + "/OR_ABI-L2-AODC-M6_G18_s" + this_str + "*")
        if paths:
            if h > 0:
                CR_LOGGER.warning(f"Missing {dataset_name} file for {target_time_str}, using {this_str} instead")
            return paths
    # nothing found within lookback window
    return []


class RAVE_DatasetRegridContext(AbstractDatasetRegridContext):
    _area_data: np.ndarray | None = PrivateAttr(default=None)

    def get_area_data(self, raw_src_fwrap: FieldWrapper) -> np.ndarray:
        # Get the area from the RAVE file, need to convert from /grid to /m2

        # To get the right gwrap we need to know what kind of field it is.
        # But FieldWrapper already has the gwrap it was created with.
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

    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        for date_to_process in self.dates_needed:
            CR_LOGGER.info(f"RAVE processing {date_to_process=}")
            src_paths = find_latest_src_file(
                self.input_dir, date_to_process, self.ebb_dcycle, self.dataset_name, max_lookback_hours=24
            )
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
        # JLS, TODO - NEED TO ACCOUNT FOR EBB1, MORE THAN 24, ETC.
        # Determine the cycle dates to process +%Y%m%d%H
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


class GRA2PES_DatasetRegridContext(AbstractDatasetRegridContext):
    def update_src_field_wrapper(self, raw_src_fwrap: FieldWrapper) -> None:
        field_name = raw_src_fwrap.value.name
        src_data = raw_src_fwrap.value.data

        # GRA2PES PM, convert from metric tons/km2/hr to ug/m2/s
        if field_name in ("PM25-PRI", "PM10-PRI"):
            conv_aer = 1.0e6 / 3600.0
        # GRA2PES methane, convert from moles/km2/hr to ug/m2/s
        elif field_name in ("HC01", "SO2", "CO", "NH3", "NOX"):
            conv_aer = 1.0e-6 / 3600.0
        else:
            conv_aer = 1.0

        src_data[:] = np.where(src_data < 0.0, 0.0, conv_aer * src_data)
        src_data[:] = np.where(np.isnan(src_data), 0.0, src_data)

    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        # Define the parts that change
        suffixes = ["00to11Z", "12to23Z"]

        # Common string components
        src_prefix = f"GRA2PESv1.0_total_2021{self.dt_spec.mm}_{self.dt_spec.dows}_"
        dst_prefix = f"{self.dataset_name}v1.0_total_{self.mesh_name}_"

        for suffix in suffixes:
            yield RegridFilePair(
                src_path=self.input_dir / f"{src_prefix}{suffix}.nc", dst_path=self.output_dir / f"{dst_prefix}{suffix}.nc"
            )


class FMC_DatasetRegridContext(AbstractDatasetRegridContext):
    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        for date_to_process in self.dates_needed:
            src_paths = glob.glob(str(self.input_dir / ("fmc_" + date_to_process + ".nc")))
            src_path = Path(src_paths[0])
            new_dst_path = self.output_dir / ("fmc_" + date_to_process + "_" + self.mesh_name + ".nc")
            yield RegridFilePair(src_path=src_path, dst_path=new_dst_path)

    @cached_property
    def dates_needed(self) -> list[str]:
        dates_needed = []
        for i in range(25):
            x = self.dt_spec.datetime - timedelta(hours=i)
            y = x.strftime("%Y%m%d%H")
            dates_needed.append(y)
        return dates_needed


class NEMO_RWC_DatasetRegridContext(AbstractDatasetRegridContext):
    def update_src_field_wrapper(self, raw_src_fwrap: FieldWrapper) -> None:
        field_name = raw_src_fwrap.value.name
        src_data = raw_src_fwrap.value.data

        if field_name in ("PEC", "POC", "PMOTHR", "PMC"):
            # Convert g/s/km2 (on 1km grid) to ug/m2/s -->
            conv_aer = 1.0
        else:
            conv_aer = 1.0

        src_data[:] = np.where(src_data < 0.0, 0.0, conv_aer * src_data)
        src_data[:] = np.where(np.isnan(src_data), 0.0, src_data)

    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        for _ in range(1):
            src_path = self.input_dir / "NEMO_RWC_POC_PEC_PMOTHR.annual.2017.nc"
            new_dst_path = self.output_dir / ("NEMO_RWC_ANNUAL_TOTAL_" + self.mesh_name + ".nc")
            yield RegridFilePair(src_path=src_path, dst_path=new_dst_path)


class NEMO_ANTHRO_DatasetRegridContext(AbstractDatasetRegridContext):
    def update_src_field_wrapper(self, raw_src_fwrap: FieldWrapper) -> None:
        field_name = raw_src_fwrap.value.name
        src_data = raw_src_fwrap.value.data

        if field_name in ("PEC", "POC", "PMOTHR", "PMC"):
            # Convert g/s/km2 to ug/m2/s -->
            conv_aer = 1.0
        else:
            conv_aer = 1.0

        src_data[:] = np.where(src_data < 0.0, 0.0, conv_aer * src_data)
        src_data[:] = np.where(np.isnan(src_data), 0.0, src_data)

    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        for _ in range(1):
            src_path = self.input_dir / (
                "NEMO_ANTHRO_"
                + self.mesh_name
                + "_"
                + self.dt_spec.yyyy
                + self.dt_spec.mm
                + self.dt_spec.dd
                + self.dt_spec.hh
                + "_SECTORSUM.nc"
            )
            new_dst_path = self.output_dir / ("NEMO_ANTHRO_" + self.mesh_name + ".nc")
            yield RegridFilePair(src_path=src_path, dst_path=new_dst_path)


class PECM_DatasetRegridContext(AbstractDatasetRegridContext):
    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        for _ in range(1):
            src_path = self.input_dir / ("pollen_obs_" + self.dt_spec.yyyy + "_BELD6_ef_T_" + self.dt_spec.jjj + ".nc")
            new_dst_path = self.output_dir / (
                "pollen_ef_" + self.mesh_name + "_" + self.dt_spec.yyyy + "_" + self.dt_spec.jjj + ".nc"
            )
            yield RegridFilePair(src_path=src_path, dst_path=new_dst_path)


class NARR_DatasetRegridContext(AbstractDatasetRegridContext):
    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        for _ in range(1):
            src_path = self.input_dir / "rwc_emission_denominator.2017.nc"
            new_dst_path = self.output_dir / ("NEMO_RWC_DENOMINATOR_2017_" + self.mesh_name + ".nc")
            yield RegridFilePair(src_path=src_path, dst_path=new_dst_path)


class ECOREGION_DatasetRegridContext(AbstractDatasetRegridContext):
    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        for _ in range(1):
            src_path = self.input_dir / "veg_map.nc"
            new_dst_path = self.output_dir / ("ecoregions_" + self.mesh_name + "_mpas.nc")
            yield RegridFilePair(src_path=src_path, dst_path=new_dst_path)


class FENGSHA_2D_DatasetRegridContext(AbstractDatasetRegridContext):
    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        for _ in range(1):
            src_path = self.input_dir / "FENGSHA_RRFS_NA_3km_2026_2D.nc"
            new_dst_path = self.output_dir / ("fengsha_dust_inputs.2D." + self.mesh_name + ".nc")
            yield RegridFilePair(src_path=src_path, dst_path=new_dst_path)


class FENGSHA_2D_Time_DatasetRegridContext(AbstractDatasetRegridContext):
    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        for _ in range(1):
            src_path = self.input_dir / "FENGSHA_RRFS_NA_3km_2026_2D_Time.nc"
            new_dst_path = self.output_dir / ("fengsha_dust_inputs.2D_Time." + self.mesh_name + ".nc")
            yield RegridFilePair(src_path=src_path, dst_path=new_dst_path)


class GOES_DatasetRegridContext(AbstractDatasetRegridContext):
    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        date_to_process = self.dates_needed[0]
        src_paths = find_latest_src_file(self.input_dir, date_to_process, -1, self.dataset_name, max_lookback_hours=2)
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


class NGFS_DatasetRegridContext(AbstractDatasetRegridContext):
    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        raise NotImplementedError("NGFS not yet supported")

    @cached_property
    def dates_needed(self) -> list[str]:
        dates_needed = []
        # Determine the cycle dates to process +%Y%m%d%H
        # This is for RETROS (using current datetime, not day before)
        for i in range(25):  # GAF retro current day emissions
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


def get_regrid_context_class(name: DatasetName) -> type[AbstractDatasetRegridContext]:
    klasses = {
        DatasetName.RAVE: RAVE_DatasetRegridContext,
        DatasetName.GRA2PES: GRA2PES_DatasetRegridContext,
        DatasetName.FMC: FMC_DatasetRegridContext,
        DatasetName.NEMO_RWC: NEMO_RWC_DatasetRegridContext,
        DatasetName.NEMO_ANTHRO: NEMO_ANTHRO_DatasetRegridContext,
        DatasetName.PECM: PECM_DatasetRegridContext,
        DatasetName.NARR: NARR_DatasetRegridContext,
        DatasetName.ECOREGION: ECOREGION_DatasetRegridContext,
        DatasetName.FENGSHA_2D: FENGSHA_2D_DatasetRegridContext,
        DatasetName.FENGSHA_2D_Time: FENGSHA_2D_Time_DatasetRegridContext,
        DatasetName.GOES: GOES_DatasetRegridContext,
        DatasetName.NGFS: NGFS_DatasetRegridContext,
    }
    return klasses[name]
