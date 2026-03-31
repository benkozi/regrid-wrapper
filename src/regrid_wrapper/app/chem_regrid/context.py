from abc import ABC
from pathlib import Path

import yaml
from pydantic import BaseModel


class RwBaseModel(ABC, BaseModel):
    model_config = {"frozen": True}

    @classmethod
    def from_yaml(cls, data: dict) -> "RwBaseModel":
        return cls.model_validate(data)

    @classmethod
    def from_yaml_file(cls, path: Path) -> "RwBaseModel":
        string_data = path.read_text()
        yaml_data = yaml.safe_load(string_data)
        return cls.from_yaml(yaml_data)


class ChemRegridContext(RwBaseModel):
    path: Path
