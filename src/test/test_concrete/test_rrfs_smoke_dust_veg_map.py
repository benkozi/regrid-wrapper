from pathlib import Path

import esmpy

from regrid_wrapper.concrete.rrfs_smoke_dust_veg_map import RrfsSmokeDustVegetationMap
from regrid_wrapper.context.comm import COMM
from regrid_wrapper.model.spec import GenerateWeightFileAndRegridFields
from regrid_wrapper.strategy.core import RegridProcessor
import pytest

import xarray as xr
from test.conftest import (
    create_veg_map_file,
    create_rrfs_grid_file,
    assert_zero_sum_diff,
)
from regrid_wrapper.common import ncdump


@pytest.mark.skip("dev only")
def test_dev(bin_dir: Path, tmp_path_shared: Path) -> None:
    weight_filename = "weights-veg_map-NA_3km-to-CONUS_25km"
    spec = GenerateWeightFileAndRegridFields(
        src_path=bin_dir / "RRFS_NA_3km/veg_map.nc",
        dst_path=bin_dir / "RRFS_CONUS_25km/ds_out_base.nc",
        output_weight_filename=tmp_path_shared / weight_filename,
        output_filename=tmp_path_shared / "veg_map.nc",
        fields=("emiss_factor",),
        esmpy_debug=False,
        name=weight_filename,
    )
    op = RrfsSmokeDustVegetationMap(spec=spec)
    processor = RegridProcessor(operation=op)
    processor.execute()


@pytest.mark.mpi
def test(tmp_path_shared: Path) -> None:
    src_grid = tmp_path_shared / "src_grid.nc"
    dst_grid = tmp_path_shared / "dst_grid.nc"
    weights = tmp_path_shared / "weights.nc"
    veg_map = tmp_path_shared / "veg_map.nc"

    if COMM.rank == 0:
        _ = create_veg_map_file(src_grid, ["emiss_factor"])
        _ = create_rrfs_grid_file(dst_grid)
    COMM.barrier()

    spec = GenerateWeightFileAndRegridFields(
        src_path=src_grid,
        dst_path=dst_grid,
        output_weight_filename=weights,
        output_filename=veg_map,
        fields=("emiss_factor",),
        esmpy_debug=False,
        name="veg_map-3km-to-25km",
    )
    op = RrfsSmokeDustVegetationMap(spec=spec)
    processor = RegridProcessor(operation=op)
    processor.execute()

    assert weights.exists()
    assert veg_map.exists()

    if COMM.rank == 0:
        with xr.open_dataset(src_grid) as ds:
            expected = ds["emiss_factor"]
            # TEST_LOGGER.debug(expected.to_dataframe().describe())
        with xr.open_dataset(veg_map) as ds:
            actual = ds["emiss_factor"]
            # TEST_LOGGER.debug(actual.to_dataframe().describe())
        assert_zero_sum_diff(actual.values, expected.values)
        assert expected.attrs == actual.attrs
        ncdump(veg_map)

        with xr.open_dataset(weights) as ds:
            n_s = ds.sizes["n_s"]
            assert n_s > 0
            # TEST_LOGGER.debug(f"n_s={n_s}")


@pytest.mark.mpi
def test_different_shapes(tmp_path_shared: Path) -> None:
    src_grid = tmp_path_shared / "src_grid.nc"
    dst_grid = tmp_path_shared / "dst_grid.nc"
    weights = tmp_path_shared / "weights.nc"
    veg_map = tmp_path_shared / "veg_map.nc"

    if COMM.rank == 0:
        _ = create_veg_map_file(src_grid, ["emiss_factor"])
        _ = create_rrfs_grid_file(
            dst_grid,
            min_lon=220,
            max_lon=290,
            min_lat=30,
            max_lat=40,
            nlon=35,
            nlat=10,
            with_corners=False,
        )
    COMM.barrier()

    spec = GenerateWeightFileAndRegridFields(
        src_path=src_grid,
        dst_path=dst_grid,
        output_weight_filename=weights,
        output_filename=veg_map,
        fields=("emiss_factor",),
        esmpy_debug=False,
        name="veg_map-3km-to-25km",
        esmpy_unmapped_action=esmpy.UnmappedAction.IGNORE,
    )
    op = RrfsSmokeDustVegetationMap(spec=spec)
    processor = RegridProcessor(operation=op)
    processor.execute()

    assert weights.exists()
    assert veg_map.exists()
