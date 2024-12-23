from pathlib import Path

import pytest

from regrid_wrapper.concrete.rave_to_rrfs import RaveToRrfs
from regrid_wrapper.context.comm import COMM
from regrid_wrapper.model.spec import (
    GenerateWeightFileSpec,
)

from regrid_wrapper.strategy.core import RegridProcessor

from test.conftest import create_rrfs_grid_file


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
        _ = create_rrfs_grid_file(src_grid)
        _ = create_rrfs_grid_file(dst_grid)

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
