from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

import numpy as np
import pytest
import xarray as xr
from pydantic import BaseModel

from regrid_wrapper.context.comm import COMM
from regrid_wrapper.context.env import ENV
from regrid_wrapper.context.logging import LOGGER
from regrid_wrapper.model.spec import (
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


def create_rrfs_grid_file(path: Path, with_corners: bool = True) -> xr.Dataset:
    if path.exists():
        raise ValueError(f"path exists: {path}")
    lon = np.linspace(230, 300, 71)
    lat = np.linspace(25, 50, 26)
    lon_mesh, lat_mesh = np.meshgrid(lon, lat)
    ds = xr.Dataset()
    ds["grid_lont"] = xr.DataArray(lon_mesh, dims=["lat", "lon"])
    ds["grid_latt"] = xr.DataArray(lat_mesh, dims=["lat", "lon"])
    if with_corners:
        lonc = np.hstack((lon - 0.5, [lon[-1] + 0.5]))
        latc = np.hstack((lat - 0.5, [lat[-1] + 0.5]))
        lonc_mesh, latc_mesh = np.meshgrid(lonc, latc)
        ds["grid_lon"] = xr.DataArray(lonc_mesh, dims=["latc", "lonc"])
        ds["grid_lat"] = xr.DataArray(latc_mesh, dims=["latc", "lonc"])
    deg_to_rad = 3.141592653589793 / 180.0
    ds["analytic_field"] = xr.DataArray(
        2.0
        + np.cos(deg_to_rad * lon_mesh) ** 2
        * np.cos(2.0 * deg_to_rad * (90.0 - lat_mesh)),
        dims=["lat", "lon"],
    )
    ds.to_netcdf(path)
    return ds
