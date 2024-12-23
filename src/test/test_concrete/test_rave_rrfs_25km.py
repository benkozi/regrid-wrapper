from pathlib import Path

import numpy as np
import pytest
from pip._internal import resolution

from regrid_wrapper.concrete.rave_to_rrfs import RaveToRrfs
from regrid_wrapper.context.comm import COMM
from regrid_wrapper.model.spec import (
    GenerateWeightFileSpec,
)

from regrid_wrapper.strategy.core import RegridProcessor
import xarray as xr


@pytest.mark.skip("dev only")
def test_dev(bin_dir: Path, tmp_path_shared: Path) -> None:
    spec = GenerateWeightFileSpec(
        src_path=bin_dir / "RAVE/grid_in.nc",
        dst_path=bin_dir / "RRFS_CONUS_25km/ds_out_base.nc",
        output_weight_filename=tmp_path_shared / "weights.nc",
        esmpy_debug=True,
        name="tester",
        machine="hera",
    )
    op = RaveToRrfs(spec=spec)
    processor = RegridProcessor(operation=op)
    processor.execute()


@pytest.mark.mpi
def test(tmp_path_shared: Path) -> None:
    src_grid = tmp_path_shared / "src_grid.nc"
    dst_grid = tmp_path_shared / "dst_grid.nc"
    weights = tmp_path_shared / "weights.nc"

    if COMM.rank == 0:
        lon = np.linspace(230, 300, 71)
        lonc = np.hstack((lon - 0.5, [lon[-1] + 0.5]))
        lat = np.linspace(25, 50, 26)
        latc = np.hstack((lat - 0.5, [lat[-1] + 0.5]))

        lon, lat = np.meshgrid(lon, lat)
        lonc, latc = np.meshgrid(lonc, latc)

        ds = xr.Dataset()
        ds["grid_lont"] = xr.DataArray(lon, dims=["lat", "lon"])
        ds["grid_latt"] = xr.DataArray(lat, dims=["lat", "lon"])
        ds["grid_lon"] = xr.DataArray(lonc, dims=["latc", "lonc"])
        ds["grid_lat"] = xr.DataArray(latc, dims=["latc", "lonc"])

        ds.to_netcdf(src_grid)
        ds.to_netcdf(dst_grid)

    spec = GenerateWeightFileSpec(
        src_path=src_grid,
        dst_path=dst_grid,
        output_weight_filename=weights,
        esmpy_debug=True,
        name="tester",
        machine="hera",
    )
    op = RaveToRrfs(spec=spec)
    processor = RegridProcessor(operation=op)
    processor.execute()

    assert Path(weights).exists()
