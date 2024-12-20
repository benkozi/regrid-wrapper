from typing import Tuple

from pydantic import BaseModel

from regrid_wrapper.geom.plot_spec import PlotSpec


class BoundingBox(BaseModel):
    min_lon: float
    max_lon: float
    min_lat: float
    max_lat: float
    plot_spec: PlotSpec

    @property
    def width(self) -> float:
        return self.max_lon - self.min_lon

    @property
    def height(self) -> float:
        return self.max_lat - self.min_lat

    @property
    def lower_left(self) -> Tuple[float, float]:
        return self.min_lon, self.min_lat

    def get_padded_extent(self, padding: float) -> Tuple[float, float, float, float]:
        return (
            self.min_lon - padding,
            self.max_lon + padding,
            self.min_lat - padding,
            self.max_lat + padding,
        )
