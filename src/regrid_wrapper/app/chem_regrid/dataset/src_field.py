from abc import ABC, abstractmethod
from functools import cached_property
from typing import Any

import esmpy
import numpy as np
from pydantic import BaseModel

from regrid_wrapper.esmpy.field_wrapper import Dimension, DimensionCollection


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
