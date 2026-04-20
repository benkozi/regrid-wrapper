from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from functools import cached_property
from pathlib import Path
from typing import Any, Union

import esmpy
import numpy as np
from pydantic import BaseModel

from regrid_wrapper.app.chem_regrid.context import CR_LOGGER
from regrid_wrapper.app.chem_regrid.dataset.model import DatasetName, InterpMethod
from regrid_wrapper.context.comm import COMM
from regrid_wrapper.esmpy.field_wrapper import Dimension, DimensionCollection, HasNcAttrsType, open_nc


class DateTimeSpec(BaseModel):
    yyyy: str
    mm: str
    dd: str
    hh: str
    jjj: str
    dowh: int
    dows: str
    datetime: datetime


class AbstractSrcField(ABC, BaseModel):
    name: str
    attrs: dict[str, Any]
    fill_value: float
    dtype: Any
    num_cells: int
    level_out_name: str | None
    level_out_size: int
    time_size: int

    @cached_property
    def time_dimension(self) -> Dimension:
        return Dimension(
            name=("Time",),
            size=self.time_size,
            lower=0,
            upper=self.time_size,
            staggerloc=esmpy.StaggerLoc.CENTER,
            coordinate_type="time",
        )

    @cached_property
    def nklevel_dimension(self) -> Dimension:
        if self.level_out_name is None:
            raise ValueError("Level out name must be set for 3D fields")
        return Dimension(
            name=self.level_out_name,
            size=self.level_out_size,
            lower=0,
            upper=self.level_out_size,
            staggerloc=esmpy.StaggerLoc.CENTER,
            coordinate_type="level",
        )

    def create_ncells_dimension(self, bounds: tuple[int, int]) -> Dimension:
        return Dimension(
            name=("nCells",),
            size=self.num_cells,  # 225636, #130333,  # tdk: pull from origin,
            lower=bounds[0],
            upper=bounds[1],
            staggerloc=esmpy.MeshLoc.ELEMENT,
            coordinate_type="cell",
        )

    @abstractmethod
    def create_dimension_collection(self, ncells_bounds: tuple[int, int]) -> DimensionCollection: ...

    @abstractmethod
    def reshape_field_data(self, target: np.ndarray) -> np.ndarray: ...


class SrcField2d(AbstractSrcField):
    def create_dimension_collection(self, ncells_bounds: tuple[int, int]) -> DimensionCollection:
        return DimensionCollection(value=(self.create_ncells_dimension(ncells_bounds),))

    def reshape_field_data(self, target: np.ndarray) -> np.ndarray:
        return target.reshape(-1)


class SrcField2d_plusTime(AbstractSrcField):
    def create_dimension_collection(self, ncells_bounds: tuple[int, int]) -> DimensionCollection:
        return DimensionCollection(value=(self.time_dimension, self.create_ncells_dimension(ncells_bounds)))

    def reshape_field_data(self, target: np.ndarray) -> np.ndarray:
        return target.reshape(self.time_size, -1)


class SrcField3d(AbstractSrcField):
    def create_dimension_collection(self, ncells_bounds: tuple[int, int]) -> DimensionCollection:
        return DimensionCollection(
            value=(
                self.create_ncells_dimension(ncells_bounds),
                self.nklevel_dimension,
            )
        )

    def reshape_field_data(self, target: np.ndarray) -> np.ndarray:
        return target.reshape(-1, self.level_out_size)


class SrcField3d_plusTime(AbstractSrcField):
    def create_dimension_collection(self, ncells_bounds: tuple[int, int]) -> DimensionCollection:
        return DimensionCollection(
            value=(
                self.create_ncells_dimension(ncells_bounds),
                self.nklevel_dimension,
                self.time_dimension,
            )
        )

    def reshape_field_data(self, target: np.ndarray) -> np.ndarray:
        return target.reshape(-1, self.level_out_size, self.time_size)


class DatasetRegridContext(BaseModel):
    dataset_name: DatasetName
    workdir: Path
    src_path: Path
    dst_path: Path
    new_dst_path: Path
    desc_stats_out: Path
    weight_path: Path
    InterpMethod: InterpMethod
    scrip_path: Path
    num_cells: int
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
    # InterpMask: float
    write_desc_stats: bool = False

    rank: int = COMM.rank

    @cached_property
    def dates_needed(self) -> list[str]:
        dates_needed = []
        match self.dataset_name:
            case DatasetName.RAVE:
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
            case DatasetName.NGFS:
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
            case DatasetName.FMC:  # fuel moisture content
                for i in range(25):
                    x = self.dt_spec.datetime - timedelta(hours=i)
                    y = x.strftime("%Y%m%d%H")
                    dates_needed.append(y)
            case DatasetName.GOES:
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
            case _:
                raise NotImplementedError(f"Dataset {self.dataset_name} not supported")
        return dates_needed

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
