import subprocess
from abc import ABC
from pathlib import Path
from typing import Any, Callable, TypeVar

import yaml
from pydantic import BaseModel


def ncdump(path: Path, header_only: bool = True) -> Any:
    args = ["ncdump"]
    if header_only:
        args.append("-h")
    args.append(str(path))
    ret = subprocess.check_output(args)
    print(ret.decode(), flush=True)
    return ret


T = TypeVar("T", bound="RwBaseModel")


class RwBaseModel(ABC, BaseModel):
    model_config = {"frozen": True}

    @classmethod
    def from_yaml(cls: type[T], data: dict) -> T:
        return cls.model_validate(data)

    @classmethod
    def from_yaml_file(cls: type[T], path: Path, retriever: Callable[[dict], dict] | None = None) -> T:
        yaml_data = cls.read_raw_yaml(path)
        if retriever is not None:
            yaml_data = retriever(yaml_data)
        return cls.from_yaml(yaml_data)

    @staticmethod
    def read_raw_yaml(path: Path) -> dict:
        string_data = path.read_text()
        return yaml.safe_load(string_data)
