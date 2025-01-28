from pathlib import Path

from regrid_wrapper.describe import DescribeParams, describe


def create_params() -> DescribeParams:
    root_dir = Path(
        "/scratch1/NCEPDEV/stmp2/Benjamin.Koziol/data/smoke_dust_conus_3km/nco_dirs/test_smoke/com/smoke_dust/v1.0.0"
    )
    files = tuple(root_dir.glob("*smoke_dust*dyn*nc"))
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


def main() -> None:
    params = create_params()
    describe(params)


if __name__ == "__main__":
    main()
