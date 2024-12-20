from pydantic import BaseModel


class PlotSpec(BaseModel):
    linewidth: int = 2
    edgecolor: str = "red"
