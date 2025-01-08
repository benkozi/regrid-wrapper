from enum import StrEnum, unique
from typing import Tuple, Dict

from pydantic import BaseModel, Field

from regrid_wrapper.context.common import PathType


@unique
class AbstractEnum(StrEnum): ...


class RrfsGridKey(AbstractEnum):
    RRFS_NA_13KM = "RRFS_NA_13KM"
    RRFS_CONUS_13KM = "RRFS_CONUS_13KM"
    RRFS_CONUS_25KM = "RRFS_CONUS_25KM"


class ComponentKey(AbstractEnum):
    VEG_MAP = "VEG_MAP"
    RAVE_GRID = "RAVE_GRID"
    DUST = "DUST"


InputPathType = PathType


class RrfsGrid(BaseModel):
    grid: InputPathType
    nodes: int
    tasks_per_node: int = 24
    wall_time: str = "04:00:00"


class Component(BaseModel):
    grid: InputPathType


class SourceDefinition(BaseModel):
    components: Dict[ComponentKey, Component] = Field(min_length=3)
    rrfs_grids: Dict[RrfsGridKey, RrfsGrid] = Field(min_length=3)


class SmokeDustRegridConfig(BaseModel):
    target_grids: Tuple[RrfsGridKey, ...] = Field(min_length=1)
    target_components: Tuple[ComponentKey, ...] = Field(min_length=1)
    root_output_directory: PathType
    source_definition: SourceDefinition

    def output_directory(self, target_grid: RrfsGridKey) -> PathType:
        return self.root_output_directory / f"{target_grid.value}/output"

    @property
    def log_directory(self) -> PathType:
        return self.root_output_directory / "logs"

    @property
    def main_job_path(self) -> PathType:
        return self.root_output_directory / "main-job.sh"

    def model_grid_path(self, target_grid: RrfsGridKey) -> PathType:
        return self.output_directory(target_grid) / "ds_out_base.nc"

    def rave_grid_path(self, target_grid: RrfsGridKey) -> PathType:
        return self.output_directory(target_grid) / "grid_in.nc"
