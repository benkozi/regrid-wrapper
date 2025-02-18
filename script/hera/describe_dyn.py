import glob
import sys

import typer

sys.path.append("/scratch1/NCEPDEV/stmp2/Benjamin.Koziol/sandbox/regrid-wrapper/src")

from pathlib import Path

from regrid_wrapper.describe import DescribeParams, describe


def create_params(root_dir: Path, csv_out: Path) -> DescribeParams:
    files = glob.glob("**/*smoke_dust*dyn*nc", root_dir=root_dir, recursive=True)
    print(f"{files=}")
    params = DescribeParams(
        namespace="smoke_dust.dyn",
        files=tuple([root_dir / ii for ii in files]),
        varnames=(
            # "coarsepm",
            "coarsepm_ave",
            # "dust",
            "dust_ave",
            # "smoke",
            "smoke_ave",
        ),
        csv_out=csv_out,
    )
    return params


def main(root_dir: Path, csv_out: Path) -> None:
    params = create_params(root_dir, csv_out)
    describe(params)


if __name__ == "__main__":
    typer.run(main)
