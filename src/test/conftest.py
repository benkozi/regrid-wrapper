from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

import pytest
from pydantic import BaseModel

from dec_regridding.context.comm import COMM
from dec_regridding.context.env import ENV
from dec_regridding.context.logging import LOGGER

TEST_LOGGER = LOGGER.getChild("test")


@pytest.fixture
def bin_dir() -> Path:
    return Path(__file__).parent.joinpath("bin").resolve().expanduser()


@pytest.fixture
def tmp_path_shared(tmp_path: Path) -> Path:
    return Path(COMM.bcast({"path": str(tmp_path)}, root=0)["path"])


@contextmanager
def unfreeze_pydantic_models(models: Sequence[BaseModel]) -> Iterator[None]:
    for model in models:
        model.model_config["frozen"] = False
    try:
        yield
    finally:
        for model in models:
            model.model_config["frozen"] = True


@contextmanager
def custom_env(**kwargs: Any) -> Iterator[None]:
    orig = {}
    with unfreeze_pydantic_models([ENV]):
        for k, v in kwargs.items():
            orig[k] = getattr(ENV, k)
            setattr(ENV, k, v)
    try:
        yield
    finally:
        with unfreeze_pydantic_models([ENV]):
            for k, v in orig.items():
                setattr(ENV, k, v)
