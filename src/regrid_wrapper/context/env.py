import logging
import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from mpi4py import MPI

from regrid_wrapper.context.common import PathType


load_dotenv()


class Environment(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REGRID_WRAPPER_")

    LOG_DIR: PathType
    LOG_PREFIX: str = "Regrid-Wrapper"
    LOG_LEVEL: int = logging.DEBUG

    def create_log_file_path(self) -> Path:
        comm = MPI.COMM_WORLD
        print(self)
        return (
            Path(self.LOG_DIR)
            / f"{self.LOG_PREFIX}-{str(comm.Get_rank()).zfill(4)}.log"
        )


ENV = Environment()  # type: ignore[call-arg]
