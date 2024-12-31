from contextlib import contextmanager
from pathlib import Path
from typing import Tuple, Literal

import numpy as np
from pydantic import BaseModel, Field, ConfigDict
import esmpy
import xarray as xr
import netCDF4 as nc

from mpi4py import MPI


@contextmanager
def open_nc(path: Path, mode: Literal["r", "w"] = "r"):
    ds = nc.Dataset(
        path,
        mode=mode,
        parallel=True,
        comm=MPI.COMM_WORLD,
        info=MPI.Info(),
    )
    try:
        yield ds
    finally:
        ds.close()


class Dimension(BaseModel):
    name: str
    size: int
    lower: int
    upper: int
    coordinate_type: Literal["y", "x", "time"]


class DimensionCollection(BaseModel):
    value: Tuple[Dimension, ...]

    def get(self, name: str) -> Dimension:
        for ii in self.value:
            if ii.name == name:
                return ii
        raise ValueError


class GridWrapper(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    grid: esmpy.Grid
    dims: DimensionCollection


class NcDatasetToGrid(BaseModel):
    path: Path
    x_center: str
    y_center: str
    x_dim: str
    y_dim: str
    x_corner: str | None = None
    y_corner: str | None = None

    @property
    def has_corners(self) -> bool:
        return self.x_corner is not None

    def get_x_corner(self) -> str:
        if self.x_corner is None:
            raise ValueError
        return self.x_corner

    def get_y_corner(self) -> str:
        if self.y_corner is None:
            raise ValueError
        return self.y_corner

    def create(self) -> GridWrapper:
        x, y = 0, 1
        with open_nc(self.path, "r") as ds:
            grid_shape = np.array(
                [ds.dimensions[self.x_dim].size, ds.dimensions[self.y_dim].size]
            )
            grid = esmpy.Grid(
                grid_shape,
                staggerloc=esmpy.StaggerLoc.CENTER,
                coord_sys=esmpy.CoordSys.SPH_DEG,
            )
            dims = DimensionCollection(
                value=[
                    Dimension(
                        name=self.x_dim,
                        size=grid_shape[0],
                        lower=grid.lower_bounds[esmpy.StaggerLoc.CENTER][x],
                        upper=grid.upper_bounds[esmpy.StaggerLoc.CENTER][x],
                        coordinate_type="x",
                    ),
                    Dimension(
                        name=self.y_dim,
                        size=grid_shape[1],
                        lower=grid.lower_bounds[esmpy.StaggerLoc.CENTER][y],
                        upper=grid.upper_bounds[esmpy.StaggerLoc.CENTER][y],
                        coordinate_type="y",
                    ),
                ]
            )
            grid_x_center_coords = grid.get_coords(
                x, staggerloc=esmpy.StaggerLoc.CENTER
            )
            grid_x_center_coords[:] = self.load_variable_data(
                ds.variables[self.x_center], dims
            )
            grid_y_center_coords = grid.get_coords(
                y, staggerloc=esmpy.StaggerLoc.CENTER
            )
            grid_y_center_coords[:] = self.load_variable_data(
                ds.variables[self.y_center], dims
            )

            gwrap = GridWrapper(grid=grid, dims=dims)
            return gwrap

    @staticmethod
    def load_variable_data(
        var: nc.Variable, target_dims: DimensionCollection
    ) -> np.ndarray:
        slices = [
            slice(target_dims.get(ii).lower, target_dims.get(ii).upper)
            for ii in var.dimensions
        ]
        raw_data = var[*slices]
        dim_map = {dim: ii for ii, dim in enumerate(var.dimensions)}
        axes = [dim_map[ii.name] for ii in target_dims.value]
        transposed_data = raw_data.transpose(axes)
        return transposed_data


class FieldWrapper(BaseModel):
    path: Path
    name: str
    grid_w: GridWrapper
    dim_time: str | None = None
    staggerloc: int = esmpy.StaggerLoc.CENTER

    def get_dims_esmpy(self) -> Tuple[str, ...]:
        if self.dim_time is None:
            return self.dims_esmpy_grid
        else:
            return tuple(list(self.dims_esmpy_grid) + [self.dim_time])

    def create_esmpy_field(self):
        with xr.open_dataset(self.path) as ds:
            da = ds[self.name]
            da = da.transpose(*self.get_dims_esmpy())
            if self.dim_time is None:
                ndbounds = None
            else:
                ndbounds = (ds.sizes[self.dim_time],)
            return esmpy.Field(
                self.grid, name=self.name, ndbounds=ndbounds, staggerloc=self.staggerloc
            )

    @staticmethod
    def create_empty_esmpy_field(
        grid: esmpy.Grid, name: str, ndbounds: Tuple[int, ...] | None = None
    ) -> esmpy.Field:
        ret = esmpy.Field(grid, name=name, ndbounds=ndbounds)
        return ret
