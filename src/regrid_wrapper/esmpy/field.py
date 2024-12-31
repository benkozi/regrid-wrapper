from pathlib import Path
from typing import Tuple

from pydantic import BaseModel, Field
import esmpy
import xarray as xr


class FieldWrapper(BaseModel):
    path: Path
    name: str
    grid: esmpy.Grid
    dims_esmpy_grid: Tuple[str, ...]
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
