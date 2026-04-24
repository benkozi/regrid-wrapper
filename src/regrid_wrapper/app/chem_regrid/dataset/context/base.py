import glob
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from enum import StrEnum, unique
from functools import cached_property
from pathlib import Path
from typing import Any, Iterator, Union

import esmpy
import numpy as np
from pydantic import BaseModel, model_validator

from regrid_wrapper.app.chem_regrid import CR_LOGGER
from regrid_wrapper.app.chem_regrid.dataset.src_field import SrcField
from regrid_wrapper.context.comm import COMM
from regrid_wrapper.esmpy.field_wrapper import (
    DimensionCollection,
    FieldWrapper,
    HasNcAttrsType,
    copy_nc_variable,
    open_nc,
)


class DateTimeSpec(BaseModel):
    """Container for datetime components used in file path formatting."""

    yyyy: str
    mm: str
    dd: str
    hh: str
    jjj: str
    dowh: int
    dows: str
    datetime: datetime


class RegridFilePair(BaseModel):
    """Pair of source and destination paths for a regridding operation."""

    src_path: Path
    dst_path: Path


@unique
class DatasetName(StrEnum):
    RAVE = "RAVE"
    GRA2PES = "GRA2PES"
    NEMO_RWC = "NEMO_RWC"
    NEMO_ANTHRO = "NEMO_ANTHRO"
    FMC = "FMC"
    PECM = "PECM"
    NARR = "NARR"
    ECOREGION = "ECOREGION"
    FENGSHA_2D = "FENGSHA_2D"
    FENGSHA_2D_Time = "FENGSHA_2D_Time"
    NGFS = "NGFS"
    GOES = "GOES"


@unique
class InterpMethod(StrEnum):
    CONSERVE = "CONSERVE"
    CONSERVE_2ND = "CONSERVE_2ND"
    BILINEAR = "BILINEAR"
    NEAREST_STOD = "NEAREST_STOD"


class AbstractDatasetRegridContext(ABC, BaseModel):
    """Abstract base class for dataset-specific regridding configurations and logic."""

    dataset_name: DatasetName
    workdir: Path
    src_path: Path
    dst_path: Path
    new_dst_path: Path
    desc_stats_out: Path
    weight_path: Path
    InterpMethod: InterpMethod
    input_mesh_path: Path
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
    level_out_size: int | None
    time_name: str | None
    time_size: int | None
    cycle: str
    ebb_dcycle: int
    input_dir: Path
    output_dir: Path
    # InterpMask: float
    write_desc_stats: bool = False
    var_names_to_copy_to_output_file: tuple[str, ...] = ("latCell", "lonCell", "xtime")
    time_format: str = "%Y%m%d%H"
    search_time_format: str = "%Y%m%d%H"

    rank: int = COMM.rank

    def get_src_grid_path(self) -> Path:
        """Returns the path to the source grid file."""
        return self.src_path

    def get_src_field_dims(self, field_name: str) -> tuple[tuple[str, ...] | None, tuple[str, ...] | None]:
        """Returns the level and time dimension names for a given field."""
        dim_level = (self.level_in_name,) if self.level_in_name else None
        dim_time = (self.time_name,) if self.time_name else None
        return dim_level, dim_time

    @abstractmethod
    def iter_file_pairs(self) -> Iterator[RegridFilePair]:
        """Yields pairs of source and destination paths to be processed."""
        ...

    def update_src_field_wrapper(self, raw_src_fwrap: FieldWrapper) -> None:
        """Applies dataset-specific data cleaning or transformations to the source field."""
        src_data = raw_src_fwrap.data
        src_data[:] = np.where(src_data < 0.0, 0.0, src_data)
        src_data[:] = np.where(np.isnan(src_data), 0.0, src_data)

    @cached_property
    def dates_needed(self) -> list[str]:
        """Returns a list of dates required for the current cycle."""
        raise NotImplementedError(self.__class__.__name__ + " does not support dates_needed")

    @cached_property
    def num_cells(self) -> int:
        """Returns the number of cells in the destination mesh."""
        with open_nc(self.dst_path, mode="r", parallel=False) as ds:
            return len(ds.variables["latCell"])

    @cached_property
    def dt_spec(self) -> DateTimeSpec:
        """Returns a DateTimeSpec based on the current cycle."""
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

    def get_read_name(self, field_name: str) -> str:
        """Returns the variable name to read from the source file for a given field."""
        return field_name

    @cached_property
    def src_fields(self) -> tuple[SrcField, ...]:
        """Initializes and returns the collection of source fields for the dataset."""
        src_fields = []
        with open_nc(self.src_path, mode="r") as ds:
            for field_name in self.field_names:
                read_name = self.get_read_name(field_name)

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
                app = SrcField.model_validate(init_data)
                src_fields.append(app)
        CR_LOGGER.debug(f"{src_fields=}")
        return tuple(src_fields)

    @staticmethod
    def _get_nc_attrs_(src: HasNcAttrsType) -> dict[str, Any]:
        """Extracts and filters netCDF attributes from a variable."""
        exclude = ("coordinates", "valid_range")
        return {ii: getattr(src, ii) for ii in src.ncattrs() if not ii.startswith("_") and ii not in exclude}

    def find_latest_src_file(self, target_time_str: str, max_lookback_hours: int = 24) -> list[str]:
        """Finds the latest available source file within a lookback window."""
        target_time = datetime.strptime(target_time_str, self.time_format)

        for h in range(max_lookback_hours + 1):
            if self.ebb_dcycle == -1 or self.ebb_dcycle == 2:
                this_time = target_time - timedelta(hours=h)
            elif self.ebb_dcycle == 1:
                this_time = target_time + timedelta(hours=h)
            else:
                CR_LOGGER.warning("unrecognized ebb_dcycle, reverting to same-day, ebb_dcycle = 1")
                this_time = target_time + timedelta(hours=h)

            search_path = self._get_src_search_path(this_time)
            paths = glob.glob(search_path)
            if paths:
                if h > 0:
                    msg = (
                        f"Missing {self.dataset_name} file for {target_time_str}, using "
                        f"{this_time.strftime(self.search_time_format)} instead"
                    )
                    CR_LOGGER.warning(msg)
                return paths
        # nothing found within lookback window
        return []

    def _get_src_search_path(self, this_time: datetime) -> str:
        """Returns the glob pattern for searching source files."""
        return str(self.src_path)

    def transform_regridded_data(
        self,
        src_field: SrcField,
        dst_fwrap: FieldWrapper,
        ds: Any,
        dims: DimensionCollection,
    ) -> np.ndarray:
        """Hook for dataset-specific data transformations after regridding but before writing."""
        return dst_fwrap.data

    def post_regrid_processing(
        self,
        src_field: SrcField,
        regridder: Union[esmpy.Regrid, esmpy.RegridFromFile],
        processor: Any,
        dims: DimensionCollection,
    ) -> None:
        """Hook for dataset-specific operations after a field has been regridded and written."""
        pass

    def create_output_file(self) -> None:
        if self.rank == 0:
            with open_nc(self.new_dst_path, mode="w", clobber=True, parallel=False) as dst_nc:
                dst_nc.createDimension("nCells", self.num_cells)
                if self.level_out_name is not None:
                    dst_nc.createDimension(self.level_out_name, self.level_out_size)
                dst_nc.createDimension("StrLen", 64)
                if self.time_size is not None and self.time_size > 1:
                    dst_nc.createDimension("Time", self.time_size)
                elif self.time_size == 1:
                    if "Time" not in dst_nc.dimensions:
                        dst_nc.createDimension("Time")
                    else:
                        CR_LOGGER.debug("Not creating a time dimension")
                dst_nc.setncattr("created_at", str(datetime.now(timezone.utc)))
                dst_nc.setncattr("src_path", str(self.src_path))
                dst_nc.setncattr("dst_path", str(self.dst_path))

                with open_nc(self.dst_path, mode="r", parallel=False) as src_nc:
                    for varname in self.var_names_to_copy_to_output_file:
                        copy_nc_variable(src_nc, dst_nc, varname, copy_data=True)

    @model_validator(mode="after")
    def _validate_model(self) -> "AbstractDatasetRegridContext":
        level_values = [self.level_out_name, self.level_out_size]
        if any(level_values) and not all(level_values):
            raise ValueError("level_out_name and level_out_size must be specified together")
        time_values = [self.time_name, self.time_size]
        if any(time_values) and not all(time_values):
            raise ValueError("time_name and time_size must be specified together")
        return self
