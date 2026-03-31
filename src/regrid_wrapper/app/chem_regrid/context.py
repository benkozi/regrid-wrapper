from abc import ABC
from enum import unique, StrEnum
from functools import cached_property
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, computed_field


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


@unique
class DatasetName(StrEnum):
    RAVE = "rave"


class ChemRegridContext(RwBaseModel):
    dataset_name: DatasetName
    workdir: Path
    input_dir: Path
    output_dir: Path
    weight_dir: Path
    cycle: str = Field(pattern=r"^\d{10}$")  # Validates YYYYMMDDHH format
    mesh_name: str
    scrip_path: Path | None
    dst_path: Path | None
    ebb_dcycle: int

    def finalize_paths(self):
        """Replicates the path logic from your original script."""
        if str(self.scrip_path) == ".":  # Path("") often resolves to "."
            self.scrip_path = self.workdir / f"mpas_{self.dataset_name}-{self.mesh_name}_scrip.nc"

        if str(self.dst_path) == ".":
            self.dst_path = self.workdir / "init.nc"

    @cached_property
    def rw_scrip_path(self) -> Path:
        if self.scrip_path is None:
            return self.workdir / f"mpas_{self.dataset_name.value}-{self.mesh_name}_scrip.nc"
        return self.scrip_path

    @cached_property
    def rw_dst_path(self) -> Path:
        if self.dst_path is None:
            return self.workdir / "init.nc"
        return self.dst_path

    @cached_property
    def rw_desc_stats_out(self) -> Path:
        return self.workdir / f"desc_stats-{self.cycle}.csv"
