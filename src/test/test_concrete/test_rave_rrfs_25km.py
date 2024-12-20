from pathlib import Path

from regrid_wrapper.concrete.rave_to_rrfs import RaveToRrfs
from regrid_wrapper.model.spec import (
    GenerateWeightFileSpec,
)

from regrid_wrapper.strategy.core import RegridProcessor


def test(bin_dir: Path, tmp_path_shared: Path) -> None:
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
