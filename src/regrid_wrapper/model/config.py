from enum import StrEnum, unique
from typing import Literal, Tuple, Dict

from omegaconf import DictConfig
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


class Component(BaseModel):
    grid: InputPathType


class SourceDefinition(BaseModel):
    components: Dict[ComponentKey, Component] = Field(min_length=3)
    rrfs_grids: Dict[RrfsGridKey, RrfsGrid] = Field(min_length=3)


class SmokeDustRegridConfig(BaseModel):
    target_grid: RrfsGridKey
    target_components: Tuple[ComponentKey, ...] = Field(min_length=1)
    source_definition: SourceDefinition
