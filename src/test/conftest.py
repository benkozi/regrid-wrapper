import shutil

# import sys
# print(f"{sys.path=}")
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, List

import numpy as np
import pytest
import xarray as xr

from regrid_wrapper.context.comm import COMM
from regrid_wrapper.context.env import ENV
from regrid_wrapper.context.logging import LOGGER

TEST_LOGGER = LOGGER.getChild("test")


@pytest.fixture
def bin_dir() -> Path:
    return Path(__file__).parent.joinpath("bin").resolve().expanduser()


@pytest.fixture
def tmp_path_shared(tmp_path: Path) -> Path:
    if ENV.REGRID_WRAPPER_TEST_TMPDIR is None:
        tmp_target = tmp_path
    else:
        tmp_target = ENV.REGRID_WRAPPER_TEST_TMPDIR / tmp_path.name
        if COMM.rank == 0:
            if tmp_target.exists():
                shutil.rmtree(tmp_target)
            tmp_target.mkdir(exist_ok=False, parents=False)
    return Path(COMM.bcast({"path": str(tmp_target)}, root=0)["path"])


@contextmanager
def custom_env(**kwargs: Any) -> Iterator[None]:
    orig = {}
    for k, v in kwargs.items():
        orig[k] = getattr(ENV, k)
        setattr(ENV, k, v)
    try:
        yield
    finally:
        for k, v in orig.items():
            setattr(ENV, k, v)


def create_analytic_data_array(
    dims: List[str],
    lon_mesh: np.ndarray,
    lat_mesh: np.ndarray,
    ntime: int | None = None,
    nlevel: int | None = None,
) -> xr.DataArray:
    deg_to_rad = 3.141592653589793 / 180.0
    analytic_data = 2.0 + np.cos(deg_to_rad * lon_mesh) ** 2 * np.cos(2.0 * deg_to_rad * (90.0 - lat_mesh))
    if ntime is not None:
        time_modifier = np.arange(1, ntime + 1).reshape(ntime, 1, 1)
        analytic_data = analytic_data.reshape([1] + list(analytic_data.shape))
        analytic_data = np.repeat(analytic_data, ntime, axis=0)
        analytic_data = time_modifier * analytic_data
    if nlevel is not None:
        level_modifier = np.arange(1, nlevel + 1).reshape(nlevel, 1, 1)
        analytic_data = np.expand_dims(analytic_data, axis=1)
        analytic_data = np.repeat(analytic_data, nlevel, axis=1)
        analytic_data = level_modifier * analytic_data
    return xr.DataArray(
        analytic_data,
        dims=dims,
    )


def create_rrfs_grid_file(
    path: Path,
    with_corners: bool = True,
    fields: List[str] | None = None,
    min_lon: float = 230,
    max_lon: float = 300,
    min_lat: float = 25,
    max_lat: float = 50,
    nlon: int = 71,
    nlat: int = 26,
    ntime: int | None = None,
) -> xr.Dataset:
    if path.exists():
        raise ValueError(f"path exists: {path}")
    lon = np.linspace(min_lon, max_lon, nlon)
    lat = np.linspace(min_lat, max_lat, nlat)
    lon_mesh, lat_mesh = np.meshgrid(lon, lat)
    ds = xr.Dataset()
    dims = ["grid_yt", "grid_xt"]
    ds["grid_lont"] = xr.DataArray(lon_mesh, dims=dims)
    ds["grid_latt"] = xr.DataArray(lat_mesh, dims=dims)
    ds["area"] = xr.full_like(ds["grid_lont"], fill_value=1.0)
    if with_corners:
        lonc = np.hstack((lon - 0.5, [lon[-1] + 0.5]))
        latc = np.hstack((lat - 0.5, [lat[-1] + 0.5]))
        lonc_mesh, latc_mesh = np.meshgrid(lonc, latc)
        ds["grid_lon"] = xr.DataArray(lonc_mesh, dims=["grid_y", "grid_x"])
        ds["grid_lat"] = xr.DataArray(latc_mesh, dims=["grid_y", "grid_x"])
    if fields is not None:
        if ntime is None:
            dims_for_data = dims
        else:
            dims_for_data = ["time"] + dims
        for field in fields:
            ds[field] = create_analytic_data_array(dims_for_data, lon_mesh, lat_mesh, ntime=ntime)
    ds.to_netcdf(path)
    return ds


def assert_zero_sum_diff(actual: np.ndarray, expected: np.ndarray) -> None:
    assert (actual - expected).sum() == 0


@pytest.fixture
def ugrid_path(bin_dir: Path) -> Path:
    ret = Path(bin_dir) / "mesh.QU.1920km.151026.ugrid.nc"
    assert ret.exists()
    return ret


def create_data_array(name: str, dims: dict[str, int]) -> xr.DataArray:
    shape = tuple(ii for ii in dims.values())
    data = np.random.random(shape)
    return xr.DataArray(data, name=name, dims=tuple(ii for ii in dims.keys()))
