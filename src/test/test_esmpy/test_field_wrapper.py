from pathlib import Path

import esmpy
import numpy as np

from regrid_wrapper.concrete.rrfs_dust_data import RRFS_DUST_DATA_ENV
from regrid_wrapper.esmpy.field_wrapper import (
    FieldWrapper,
    NcToGrid,
    NcToField,
    FieldWrapperCollection,
    resize_nc,
    open_nc,
    load_variable_data,
    GridSpec,
)
from test.conftest import tmp_path_shared, create_dust_data_file, ncdump
from regrid_wrapper.context.comm import COMM
import pytest


DUST_FILENAME = "data.nc"


def create_dust_file(dst_dir: Path) -> Path:
    path = dst_dir / DUST_FILENAME
    if COMM.rank == 0:
        _ = create_dust_data_file(path)
    COMM.barrier()
    return path


@pytest.fixture
def fake_field_wrapper_collection(tmp_path_shared: Path) -> FieldWrapperCollection:
    path = create_dust_file(tmp_path_shared)

    spec = GridSpec(x_center="geolon", y_center="geolat", x_dim="lon", y_dim="lat")
    nc2grid = NcToGrid(path=path, spec=spec)
    gwrap = nc2grid.create_grid_wrapper()

    fwraps = []
    for name in RRFS_DUST_DATA_ENV.fields:
        nc2field = NcToField(path=path, name=name, gwrap=gwrap, dim_time="time")
        fwrap = nc2field.create_field_wrapper()
        fwraps.append(fwrap)
    return FieldWrapperCollection(value=fwraps)


class TestGridWrapper:

    @pytest.mark.mpi
    def test_fill_nc_variables(
        self,
        tmp_path_shared: Path,
        fake_field_wrapper_collection: FieldWrapperCollection,
    ):
        gwrap = fake_field_wrapper_collection.value[0].gwrap
        expected = COMM.rank + 1
        staggerloc = esmpy.StaggerLoc.CENTER
        gwrap.spec.get_x_data(gwrap.value, staggerloc)[:] = expected
        gwrap.spec.get_y_data(gwrap.value, staggerloc)[:] = expected

        path = tmp_path_shared / DUST_FILENAME
        gwrap.fill_nc_variables(path)

        with open_nc(path) as ds:
            for varname in [gwrap.spec.x_center, gwrap.spec.y_center]:
                var = ds.variables[varname]
                actual = load_variable_data(var, gwrap.dims)
                assert (expected - actual).sum() == 0


class TestFieldWrapper:

    @pytest.mark.mpi
    def test_fill_nc_variable(
        self,
        tmp_path_shared: Path,
        fake_field_wrapper_collection: FieldWrapperCollection,
    ):
        fwrap = fake_field_wrapper_collection.value[0]
        expected = COMM.rank + 1
        fwrap.value.data.fill(expected)
        # print(fwrap.value.data)
        path = tmp_path_shared / DUST_FILENAME
        fwrap.fill_nc_variable(path)
        with open_nc(path, "r") as ds:
            var = ds.variables[fwrap.value.name]
            actual = load_variable_data(var, fwrap.dims)
            assert (actual - expected).sum() == 0


class TestFieldWrapperCollection:

    @pytest.mark.mpi
    def test(self, fake_field_wrapper_collection: FieldWrapperCollection) -> None:
        assert len(fake_field_wrapper_collection.value) > 1
        for fwrap in fake_field_wrapper_collection.value:
            assert fwrap.value.data.sum() > 0
            assert len(fwrap.dims.value) == 3
            assert fwrap.dims.value[2].name == "time"


def test_resize_nc(tmp_path_shared: Path) -> None:
    src_path = create_dust_file(tmp_path_shared)
    dst_path = tmp_path_shared / "data_resized.nc"
    new_sizes = {"time": 12, "lat": 1, "lon": 2}
    resize_nc(src_path, dst_path, new_sizes)
    # ncdump(src_path)
    # ncdump(dst_path)
    with open_nc(dst_path, "r") as ds:
        for dim in ds.dimensions:
            assert ds.dimensions[dim].size == new_sizes[dim]
