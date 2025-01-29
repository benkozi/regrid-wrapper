from pathlib import Path

from regrid_wrapper.describe import DescribeParams, describe
from test.conftest import create_dust_data_file


def test(tmp_path_shared: Path) -> None:
    data = tmp_path_shared / "data.nc"
    _ = create_dust_data_file(data)

    params = DescribeParams(
        files=[data],
        varnames=["uthr", "sand", "clay", "rdrag", "ssm"],
        namespace="dust",
        csv_out=tmp_path_shared / "summary.csv",
    )
    df = describe(params)
    assert df is not None
