from pathlib import Path
from typing import Tuple

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
    path: Path
    x_center: str
    y_center: str
    x_corner: str
    y_corner: str
    axis_order: AxisOrder = AxisOrder()

    def _fill_array_(
        self, target: np.ndarray, source: np.ndarray, x_bounds: Bounds, y_bounds: Bounds
    ) -> None:
        if self.axis_order.x == 0:
            first = x_bounds
            second = y_bounds
        else:
            first = y_bounds
            second = x_bounds

        target[:] = source[first.lower : first.upper, second.lower : second.upper]

    def _fill_grid_coords_(
        self, grid: esmpy.Grid, dim: int, staggerloc: int, data: np.ndarray
    ) -> None:
        target = grid.get_coords(dim, staggerloc=staggerloc)
        x_bounds = self._get_bounds_(grid, staggerloc, self.axis_order.x)
        y_bounds = self._get_bounds_(grid, staggerloc, self.axis_order.y)
        self._fill_array_(target, data, x_bounds, y_bounds)

    @staticmethod
    def _get_bounds_(grid: esmpy.Grid, staggerloc: int, dim: int) -> Bounds:
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
        x_corner_data = self._get_coordinates_(ds, self.x_corner)
        y_corner_data = self._get_coordinates_(ds, self.y_corner)
        ds.close()

        grid = esmpy.Grid(
            np.array(x_center_data.shape),
            staggerloc=esmpy.StaggerLoc.CENTER,
            coord_sys=esmpy.CoordSys.SPH_DEG,
        )
        grid.add_coords([esmpy.StaggerLoc.CORNER])

        self._fill_grid_coords_(
            grid, self.axis_order.x, esmpy.StaggerLoc.CENTER, x_center_data
        )
        self._fill_grid_coords_(
            grid, self.axis_order.y, esmpy.StaggerLoc.CENTER, y_center_data
        )
        self._fill_grid_coords_(
            grid, self.axis_order.x, esmpy.StaggerLoc.CORNER, x_corner_data
        )
        self._fill_grid_coords_(
            grid, self.axis_order.y, esmpy.StaggerLoc.CORNER, y_corner_data
        )

        return grid


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
