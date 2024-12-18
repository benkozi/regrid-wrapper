from pathlib import Path

from regrid_wrapper.concrete.rrfs_smoke_dust_veg_map import RrfsSmokeDustVegetationMap
from regrid_wrapper.model.spec import GenerateWeightFileAndRegridFields
from regrid_wrapper.strategy.core import RegridProcessor


def test(bin_dir: Path, tmp_path_shared: Path) -> None:
    weight_filename = "weights-veg_map-NA_3km-to-CONUS_25km"
    spec = GenerateWeightFileAndRegridFields(
        src_path=bin_dir / "RRFS_NA_3km/veg_map.nc",
        dst_path=bin_dir / "RRFS_CONUS_25km/ds_out_base.nc",
        output_weight_filename=tmp_path_shared / weight_filename,
        output_filename=tmp_path_shared / "veg_map.nc",
        fields=["emiss_factor"],
        esmpy_debug=True,
        name=weight_filename,
        machine="hera",
    )
    op = RrfsSmokeDustVegetationMap(spec=spec)
    processor = RegridProcessor(operation=op)
    processor.execute()
