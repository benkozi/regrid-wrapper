from pathlib import Path

import numpy as np

from regrid_wrapper.concrete.rrfs_dust_data import RRFS_DUST_DATA_ENV
from regrid_wrapper.esmpy.field_wrapper import (
    FieldWrapper,
    NcToGrid,
    NcToField,
    FieldWrapperCollection,
)
from test.conftest import tmp_path_shared, create_dust_data_file
from regrid_wrapper.context.comm import COMM
import pytest


@pytest.fixture
def fake_field_wrapper_collection(tmp_path_shared: Path) -> FieldWrapperCollection:
    path = tmp_path_shared / "data.nc"

    if COMM.rank == 0:
        _ = create_dust_data_file(path)
    COMM.barrier()

    nc2grid = NcToGrid(
        path=path, x_center="geolon", y_center="geolat", x_dim="lon", y_dim="lat"
    )
    gwrap = nc2grid.create_grid_wrapper()

    fwraps = []
    for name in RRFS_DUST_DATA_ENV.fields:
        nc2field = NcToField(path=path, name=name, gwrap=gwrap, dim_time="time")
        fwrap = nc2field.create_field_wrapper()
        fwraps.append(fwrap)
    return FieldWrapperCollection(value=fwraps)


class TestFieldWrapperCollection:

    def test(self, fake_field_wrapper_collection: FieldWrapperCollection) -> None:
        for fwrap in fake_field_wrapper_collection.value:
            assert fwrap.value.data.sum() > 0
            assert len(fwrap.dims.value) == 3
            assert fwrap.dims.value[2].name == "time"
