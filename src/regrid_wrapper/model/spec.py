import abc
import os
from pathlib import Path
from typing import List, Literal, Tuple

from pydantic import BaseModel, model_validator, field_validator

from regrid_wrapper.context.common import PathType
from regrid_wrapper.context.logging import LOGGER
import xarray as xr


class AbstractRegridSpec(BaseModel, abc.ABC):
    name: str
    nproc: int = 1
    esmpy_debug: bool = False


class GenerateWeightFileSpec(AbstractRegridSpec):
    src_path: PathType
    dst_path: PathType
    output_weight_filename: PathType

    def is_complete(self) -> bool:
        return self.output_weight_filename.exists()

    @model_validator(mode="after")
    def _validate_model_(self) -> "GenerateWeightFileSpec":
        errors = []
        errors += self._validate_input_file_path_(self.src_path)
        errors += self._validate_input_file_path_(self.dst_path)
        errors += self._validate_output_file_(self.output_weight_filename)
        if errors:
            LOGGER.error(errors)
            raise IOError(errors)
        return self

    @staticmethod
    def _validate_input_file_path_(path: Path) -> List[str]:
        errors = []
        if not path.exists():
            errors.append(f"path does not exist: {path}")
        if not path.is_file():
            errors.append(f"path is not a file: {path}")
        if not os.access(path, os.R_OK):
            errors.append(f"path is not readable: {path}")
        return errors

    @staticmethod
    def _validate_output_file_(path: Path) -> List[str]:
        errors = []
        parent = path.parent
        if not parent.exists():
            errors.append(f"parent directory does not exist: {path.parent}")
        if not os.access(parent, os.W_OK):
            errors.append(f"parent directory is not writable: {path.parent}")
        return errors


class GenerateWeightFileAndRegridFields(GenerateWeightFileSpec):
    output_filename: PathType
    fields: Tuple[str, ...]

    @model_validator(mode="after")
    def _validate_fields_(self) -> "GenerateWeightFileAndRegridFields":
        missing = []
        with xr.open_dataset(self.src_path) as ds:
            for field in self.fields:
                if field not in ds:
                    missing.append(field)
        if missing:
            raise ValueError(f"missing fields: {missing}")
        return self

    @field_validator("output_filename")
    @classmethod
    def _validate_output_filename_(cls, path: PathType) -> PathType:
        errors = cls._validate_output_file_(path)
        if errors:
            LOGGER.error(errors)
            raise IOError(errors)
        return path
