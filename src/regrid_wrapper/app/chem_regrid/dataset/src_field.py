from functools import cached_property
from typing import Any

import esmpy
from pydantic import BaseModel

from regrid_wrapper.esmpy.field_wrapper import Dimension, DimensionCollection


class SrcField(BaseModel):
    """Represents a source field with its metadata and dimensions for regridding."""

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
        """Returns the time dimension for the field."""
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
        """Returns the vertical level dimension for the field."""
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
        """Creates the cells dimension with specified bounds."""
        return Dimension(
            name=("nCells",),
            size=self.num_cells,
            lower=bounds[0],
            upper=bounds[1],
            staggerloc=esmpy.MeshLoc.ELEMENT,
            coordinate_type="cell",
        )

    def create_dimension_collection(self, ncells_bounds: tuple[int, int]) -> DimensionCollection:
        """Creates a collection of dimensions based on the field's shape."""

        ncells_dim = self.create_ncells_dimension(ncells_bounds)
        dims = []
        if self.level_out_size == 0:
            if self.time_size > 0:
                dims.append(self.time_dimension)
            dims.append(ncells_dim)
        else:
            if self.time_size > 0:
                dims.append(self.time_dimension)
            dims.append(ncells_dim)
            dims.append(self.nklevel_dimension)
        return DimensionCollection(value=tuple(dims))
