from pathlib import Path

import numpy as np

from regrid_wrapper.esmpy.field_wrapper import FieldWrapper, NcToGrid, NcToField
from test.conftest import tmp_path_shared, create_dust_data_file
from regrid_wrapper.context.comm import COMM


def test(tmp_path_shared: Path) -> None:
    path = tmp_path_shared / "data.nc"

    if COMM.rank == 0:
        _ = create_dust_data_file(path)
    COMM.barrier()

    nc2grid = NcToGrid(
        path=path, x_center="geolon", y_center="geolat", x_dim="lon", y_dim="lat"
    )
    gwrap = nc2grid.create_grid_wrapper()
    nc2field = NcToField(path=path, name="ssm", gwrap=gwrap, dim_time="time")
    fwrap = nc2field.create_field_wrapper()
    assert fwrap.value.data.sum() > 0
    assert len(fwrap.dims.value) == 3
    assert fwrap.dims.value[2].name == "time"
