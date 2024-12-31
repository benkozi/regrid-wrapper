from pathlib import Path

from regrid_wrapper.esmpy.field_wrapper import FieldWrapper, NcDatasetToGrid
from test.conftest import tmp_path_shared, create_dust_data_file
from regrid_wrapper.context.comm import COMM


def test(tmp_path_shared: Path) -> None:
    path = tmp_path_shared / "data.nc"

    if COMM.rank == 0:
        _ = create_dust_data_file(path)
    COMM.barrier()

    nc2grid = NcDatasetToGrid(
        path=path, x_center="geolon", y_center="geolat", x_dim="lon", y_dim="lat"
    )
    gwrap = nc2grid.create()
    return
    fwrap = FieldWrapper(path=path, name="ssm")
