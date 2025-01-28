import glob
import sys

sys.path.append("/scratch1/NCEPDEV/stmp2/Benjamin.Koziol/sandbox/regrid-wrapper/src")

from pathlib import Path

from regrid_wrapper.describe import DescribeParams, describe


def create_params() -> DescribeParams:
    root_dir = Path(
        "/scratch1/NCEPDEV/stmp2/Benjamin.Koziol/data/smoke_dust_conus_3km/nco_dirs/test_smoke/com/smoke_dust/v1.0.0"
    )
    files = glob.glob("*smoke_dust*dyn*nc", root_dir=root_dir, recursive=True)
    print(f"{files=}")
    params = DescribeParams(
        namespace="smoke_dust.dyn",
        files=files,
        varnames=(
            "coarsepm",
            "coarsepm_ave",
            "dust",
            "dust_ave",
            "smoke",
            "smoke_ave",
        ),
        csv_out=Path("/home/Benjamin.Koziol/htmp") / "smoke_dust.dyn.csv",
    )
    return params


def main() -> None:
    params = create_params()
    describe(params)


if __name__ == "__main__":
    main()
