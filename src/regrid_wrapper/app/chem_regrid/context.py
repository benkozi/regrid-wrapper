from abc import ABC
from pathlib import Path

from pydantic import BaseModel


class RwBaseModel(ABC, BaseModel):
    model_config = {"frozen": True}


class ChemRegridContext(RwBaseModel):
    path: Path