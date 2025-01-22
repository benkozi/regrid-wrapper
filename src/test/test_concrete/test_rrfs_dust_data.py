from pathlib import Path
import numpy as np

from regrid_wrapper.concrete.rrfs_dust_data import (
    RrfsDustData,
    RRFS_DUST_DATA_ENV,
)
from regrid_wrapper.context.comm import COMM
from regrid_wrapper.model.spec import GenerateWeightFileAndRegridFields
from regrid_wrapper.strategy.core import RegridProcessor
import pytest

import xarray as xr
from test.conftest import (
    create_rrfs_grid_file,
    create_dust_data_file,
    assert_zero_sum_diff,
)


@pytest.mark.mpi
def test(tmp_path_shared: Path) -> None:
    src_grid = tmp_path_shared / "src_grid.nc"
    dst_grid = tmp_path_shared / "dst_grid.nc"
    weights = tmp_path_shared / "weights.nc"
    dust_data = tmp_path_shared / "dust.nc"

    if COMM.rank == 0:
        _ = create_dust_data_file(src_grid)
        _ = create_rrfs_grid_file(dst_grid)
    COMM.barrier()

    spec = GenerateWeightFileAndRegridFields(
        src_path=src_grid,
        dst_path=dst_grid,
        output_weight_filename=weights,
        output_filename=dust_data,
        esmpy_debug=False,
        name="dust-data",
        fields=RRFS_DUST_DATA_ENV.fields,
    )
    op = RrfsDustData(spec=spec)
    processor = RegridProcessor(operation=op)
    processor.execute()

    assert not weights.exists()
    assert dust_data.exists()

    if COMM.rank == 0:
        with xr.open_dataset(src_grid) as expected:
            with xr.open_dataset(dust_data) as actual:
                for field_name in RRFS_DUST_DATA_ENV.fields:
                    assert_zero_sum_diff(
                        actual[field_name].values, expected[field_name].values
                    )
                assert expected["time"].sum() == np.arange(12).sum()
                assert actual["time"].sum() == np.arange(12).sum()

            with xr.open_dataset(dst_grid) as expected_coords:
                assert_zero_sum_diff(
                    actual["geolat"].values, expected_coords["grid_latt"].values
                )
                assert_zero_sum_diff(
                    actual["geolon"].values, expected_coords["grid_lont"].values
                )
