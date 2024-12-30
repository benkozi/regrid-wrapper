from regrid_wrapper.concrete.rave_to_rrfs import RaveToRrfs
from regrid_wrapper.concrete.rrfs_smoke_dust_veg_map import RrfsSmokeDustVegetationMap
from regrid_wrapper.model.spec import (
    GenerateWeightFileSpec,
    GenerateWeightFileAndRegridFields,
)

from regrid_wrapper.strategy.core import RegridProcessor


def main() -> None:
    weight_filename = "weights-veg_map-NA_3km-to-CONUS_25km"
    spec = GenerateWeightFileAndRegridFields(
        src_path="/scratch2/NAGAPE/epic/SRW-AQM_DATA/fix_smoke/RRFS_NA_3km/veg_map.nc",
        dst_path="/scratch2/NAGAPE/epic/Ben.Koziol/staged-data/RRFS_CONUS_13km/ds_out_base.nc",
        output_weight_filename="/scratch2/NAGAPE/epic/Ben.Koziol/output-data/weights-veg_map-NA_3km-to-CONUS_13km.nc",
        output_filename="/scratch2/NAGAPE/epic/Ben.Koziol/staged-data/RRFS_CONUS_13km/veg_map.nc",
        fields=["emiss_factor"],
        esmpy_debug=True,
        name=weight_filename,
    )
    op = RrfsSmokeDustVegetationMap(spec=spec)
    processor = RegridProcessor(operation=op)
    processor.execute()


if __name__ == "__main__":
    main()
