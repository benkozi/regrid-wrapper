from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

import pytest
from pydantic import BaseModel

from dec_regridding.context.comm import COMM
from dec_regridding.context.env import ENV
from dec_regridding.context.logging import LOGGER
from dec_regridding.model.regrid_operation import (
    AbstractRegridSpec,
    GenerateWeightFileSpec,
)

TEST_LOGGER = LOGGER.getChild("test")


@pytest.fixture
def bin_dir() -> Path:
    return Path(__file__).parent.joinpath("bin").resolve().expanduser()


@pytest.fixture
def tmp_path_shared(tmp_path: Path) -> Path:
    return Path(COMM.bcast({"path": str(tmp_path)}, root=0)["path"])


@pytest.fixture
def fake_spec(tmp_path_shared: Path) -> GenerateWeightFileSpec:
    src_path = tmp_path_shared / "src.nc"
    src_path.touch()
    dst_path = tmp_path_shared / "dst.nc"
    dst_path.touch()
    output_weight_filename = tmp_path_shared / "weights.nc"
    spec = GenerateWeightFileSpec(
        name="fake",
        src_path=src_path,
        dst_path=dst_path,
        output_weight_filename=output_weight_filename,
    )
    return spec


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
