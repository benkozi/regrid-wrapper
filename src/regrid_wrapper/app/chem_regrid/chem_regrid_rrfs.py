import os
import sys

from regrid_wrapper.app.chem_regrid import chem_regrid
from regrid_wrapper.app.chem_regrid.context import ChemRegridContext


def main() -> None:
    data = {
        "dataset_name": sys.argv[1],  # Which dataset are we interpolating?
        "workdir": sys.argv[2],  # Directory where operations will be processed
        "input_dir": sys.argv[3],  # Top directory of input data
        "output_dir": sys.argv[4],  # Top directory of output data
        "weight_dir": sys.argv[5],  # Directory that contains the regrid weights
        "cycle": sys.argv[6],  # Cycle Time, YYYYMMDDHH
        "ebb_dcycle": int(os.getenv("EBB_DCYCLE")),
        "fcst_length": int(os.getenv("FCST_LENGTH")),
        "mesh_name": os.getenv("MESH_NAME"),
    }

    try:
        data["scrip_path"] = sys.argv[7]  # Path to the input SCRIP/UGRID domain grid file
        data["dst_path"] = sys.argv[8]  # Path to the destination grid (e.g., init.nc)
    except IndexError:
        data["scrip_path"] = None
        data["dst_path"] = None

    ctx = ChemRegridContext.model_validate(data)
    chem_regrid.main(ctx)

if __name__ == "__main__":
    main()
