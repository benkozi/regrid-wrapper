from regrid_wrapper.concrete.rave_to_rrfs import RaveToRrfs
from regrid_wrapper.model.spec import (
    GenerateWeightFileSpec,
)

from regrid_wrapper.strategy.core import RegridProcessor


def main() -> None:
    spec = GenerateWeightFileSpec(
        src_path="/scratch1/BMC/acomp/Johana/input_files/fix_files_Feb23/CONUS/grid_in.nc",
        dst_path="/scratch1/BMC/acomp/Johana/input_files/fix_files_Feb23/CONUS/ds_out_base.nc",
        output_weight_filename="/scratch2/NAGAPE/epic/Ben.Koziol/output-data/weights-RAVE-to-RRFS_CONUS_3km.nc`",
        esmpy_debug=True,
        name="weights-RAVE-to-RRFS_CONUS_3km",
    )
    op = RaveToRrfs(spec=spec)
    processor = RegridProcessor(operation=op)
    processor.execute()


if __name__ == "__main__":
    main()
