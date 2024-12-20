from pathlib import Path

import pandas as pd
import xarray as xr
from pydantic import BaseModel

from regrid_wrapper.geom.plot_spec import PlotSpec
from regrid_wrapper.geom.bounding_box import BoundingBox
import numpy as np


class Grid(BaseModel):
    path: Path
    lon_name: str
    lat_name: str
    plot_spec: PlotSpec = PlotSpec()

    def describe(self) -> pd.DataFrame:
        lon = self.describe_variable(self.lon_name)
        lat = self.describe_variable(self.lat_name)
        return pd.concat([lon, lat], axis=0)

    def get_bounding_box(self) -> BoundingBox:
        with xr.open_dataset(self.path) as ds:
            lat = ds[self.lat_name]
            lon = ds[self.lon_name]
            return BoundingBox(
                min_lat=lat.min(),
                max_lat=lat.max(),
                min_lon=lon.min(),
                max_lon=lon.max(),
                plot_spec=self.plot_spec,
            )

    def get(self, name: str) -> np.ndarray:
        with xr.open_dataset(self.path) as ds:
            target = ds[name]
            return target.values

    def describe_variable(self, name: str) -> pd.DataFrame:
        with xr.open_dataset(self.path) as ds:
            da = ds[name]
            desc = da.to_dataframe().describe().transpose()
            desc["grid_name"] = self.path.name
            desc["var_name"] = name
        return desc
