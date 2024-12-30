from pathlib import Path
from typing import Tuple, Iterator, Literal

import esmpy
import numpy as np
import xarray as xr
from pydantic import BaseModel

from regrid_wrapper.model.spec import GenerateWeightFileSpec, AbstractRegridSpec
from regrid_wrapper.strategy.operation import AbstractRegridOperation


class AxisOrder(BaseModel):
    x: int = 1
    y: int = 0


class Bounds(BaseModel):
    lower: int
    upper: int
    staggerloc: int
    dim: int


class DatasetToGrid(BaseModel):
    # tdk: move to common location
    # tdk: rename to DatasetToEsmpy
    path: Path
    x_center: str
    y_center: str
    x_corner: str | None = None
    y_corner: str | None = None
    fields: Tuple[str, ...] | None = None
    axis_order: AxisOrder = AxisOrder()

    @property
    def has_corners(self) -> bool:
        return self.x_corner is not None

    def get_fields(self) -> Tuple[str, ...]:
        if self.fields is None:
            raise ValueError
        return self.fields

    def get_x_corner(self) -> str:
        if self.x_corner is None:
            raise ValueError
        return self.x_corner

    def get_y_corner(self) -> str:
        if self.y_corner is None:
            raise ValueError
        return self.y_corner

    def fill_array(
        self,
        grid: esmpy.Grid,
        target: np.ndarray,
        source: np.ndarray,
        staggerloc: int = esmpy.StaggerLoc.CENTER,
        slice_side: Literal["lhs", "rhs"] = "rhs",
    ) -> None:
        x_bounds = self.get_bounds(grid, staggerloc, self.axis_order.x)
        y_bounds = self.get_bounds(grid, staggerloc, self.axis_order.y)
        if self.axis_order.x == 0:
            first = x_bounds
            second = y_bounds
        else:
            first = y_bounds
            second = x_bounds

        if slice_side == "rhs":
            target[:] = source[first.lower : first.upper, second.lower : second.upper]
        elif slice_side == "lhs":
            target[first.lower : first.upper, second.lower : second.upper] = source

    def _fill_grid_coords_(
        self, grid: esmpy.Grid, dim: int, staggerloc: int, data: np.ndarray
    ) -> None:
        target = grid.get_coords(dim, staggerloc=staggerloc)
        self.fill_array(grid, target, data, staggerloc=staggerloc)

    @staticmethod
    def get_bounds(grid: esmpy.Grid, staggerloc: int, dim: int) -> Bounds:
        return Bounds(
            lower=grid.lower_bounds[staggerloc][dim],
            upper=grid.upper_bounds[staggerloc][dim],
            staggerloc=staggerloc,
            dim=dim,
        )

    def _get_coordinates_(self, ds: xr.Dataset, name: str) -> np.ndarray:
        data = ds[name].values
        if self.axis_order.x == 0:
            return np.swapaxes(data, 0, 1)
        return data

    def create_esmpy_grid(self) -> esmpy.Grid:
        ds = xr.open_dataset(self.path)
        x_center_data = self._get_coordinates_(ds, self.x_center)
        y_center_data = self._get_coordinates_(ds, self.y_center)
        if self.has_corners:
            x_corner_data = self._get_coordinates_(ds, self.get_x_corner())
            y_corner_data = self._get_coordinates_(ds, self.get_y_corner())
        ds.close()

        grid = esmpy.Grid(
            np.array(x_center_data.shape),
            staggerloc=esmpy.StaggerLoc.CENTER,
            coord_sys=esmpy.CoordSys.SPH_DEG,
        )
        if self.has_corners:
            grid.add_coords([esmpy.StaggerLoc.CORNER])

        self._fill_grid_coords_(
            grid, self.axis_order.x, esmpy.StaggerLoc.CENTER, x_center_data
        )
        self._fill_grid_coords_(
            grid, self.axis_order.y, esmpy.StaggerLoc.CENTER, y_center_data
        )
        if self.has_corners:
            self._fill_grid_coords_(
                grid, self.axis_order.x, esmpy.StaggerLoc.CORNER, x_corner_data
            )
            self._fill_grid_coords_(
                grid, self.axis_order.y, esmpy.StaggerLoc.CORNER, y_corner_data
            )

        return grid

    def iter_esmpy_fields(self, grid: esmpy.Grid) -> Iterator[esmpy.Field]:
        with xr.open_dataset(self.path) as ds:
            for field in self.get_fields():
                data = ds[field].values
                esmpy_field = self.create_empty_esmpy_field(grid, field)
                self.fill_array(
                    grid, esmpy_field.data, data, staggerloc=esmpy.StaggerLoc.CENTER
                )
                yield esmpy_field

    @staticmethod
    def create_empty_esmpy_field(grid: esmpy.Grid, name: str) -> esmpy.Field:
        return esmpy.Field(grid, name=name)


class RaveToRrfs(AbstractRegridOperation):

    def run(self) -> None:
        assert isinstance(self._spec, GenerateWeightFileSpec)

        src_grid_def = DatasetToGrid(
            path=self._spec.src_path,
            x_center="grid_lont",
            y_center="grid_latt",
            x_corner="grid_lon",
            y_corner="grid_lat",
        )
        src_grid = src_grid_def.create_esmpy_grid()

        dst_grid_def = DatasetToGrid(
            path=self._spec.dst_path,
            x_center="grid_lont",
            y_center="grid_latt",
            x_corner="grid_lon",
            y_corner="grid_lat",
        )
        dst_grid = dst_grid_def.create_esmpy_grid()

        src_field = esmpy.Field(src_grid, name="src")
        dst_field = esmpy.Field(dst_grid, name="dst")

        self._logger.info("starting weight file generation")
        regrid_method = esmpy.RegridMethod.CONSERVE
        regridder = esmpy.Regrid(
            src_field,
            dst_field,
            regrid_method=regrid_method,
            filename=str(self._spec.output_weight_filename),
            unmapped_action=esmpy.UnmappedAction.IGNORE,
            ignore_degenerate=True,
        )
