import logging
from enum import StrEnum, unique
from pathlib import Path

from mpi4py import MPI
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


@unique
class Platform(StrEnum):
    URSA = "ursa"
    GAEAC6 = "gaeac6"


class Environment(BaseSettings):
    model_config = SettingsConfigDict(frozen=True)

    REGRID_WRAPPER_LOG_DIR: Path = Path(".")
    REGRID_WRAPPER_LOG_PREFIX: str = "Regrid-Wrapper"
    REGRID_WRAPPER_LOG_LEVEL: int = logging.INFO
    REGRID_WRAPPER_PLATFORM: Platform = Platform.URSA
    REGRID_WRAPPER_TEST_TMPDIR: Path | None = None

    def create_log_file_path(self) -> Path:
        comm = MPI.COMM_WORLD
        return Path(self.REGRID_WRAPPER_LOG_DIR) / f"{self.REGRID_WRAPPER_LOG_PREFIX}-{str(comm.Get_rank()).zfill(4)}.log"

    @field_validator("REGRID_WRAPPER_PLATFORM", mode="before")
    @classmethod
    def _validate_platform_(cls, v: str) -> Platform:
        return Platform(v.lower())

    @field_validator("REGRID_WRAPPER_LOG_DIR", mode="before")
    @classmethod
    def _validate_log_dir_(cls, v: str | None) -> Path:
        if v is None:
            p = Path(".")
        else:
            p = Path(v)
        p = p.resolve()
        return p

    @field_validator("REGRID_WRAPPER_TEST_TMPDIR", mode="before")
    @classmethod
    def _validate_test_tmpdir_(cls, v: str | None) -> Path | None:
        p = None
        if v is not None:
            p = Path(v).resolve()
            assert p.exists()
            assert p.is_dir()
        return p


ENV = Environment()
