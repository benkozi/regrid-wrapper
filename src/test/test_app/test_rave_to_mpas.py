import time
from dataclasses import dataclass, field
from pathlib import Path

import esmpy
import pytest

from regrid_wrapper.app.rave_to_mpas import RaveGridSpec
from regrid_wrapper.context.comm import COMM
from regrid_wrapper.context.env import ENV, Platform
from regrid_wrapper.esmpy.field_wrapper import (
    NcToField,
    NcToGrid,
    NcToMesh,
    open_nc,
    set_variable_data,
)
from test.conftest import TEST_LOGGER


def region_start(name: str) -> float:
    TEST_LOGGER.info(f"Starting time_region[{COMM.rank}]={name}")
    return time.perf_counter()


def region_end(name: str, start: float) -> None:
    TEST_LOGGER.info(f"Ending time_region[{COMM.rank}]={name}; time={time.perf_counter() - start} s")


@dataclass
class _TestData:
    src_path: Path
    dst_path: Path
    output_root: Path


@dataclass
class _TestDataUrsa(_TestData):
    src_path: Path = Path(
        "/scratch4/BMC/public/data/grids/nesdis/3km_fire_emissions/RAVE-HrlyEmiss-3km_v2r0_blend_s202603121200000_e202603121259590_c202603121402030.nc"
    )
    dst_path: Path = Path("/scratch4/BMC/acomp/Sudheer/Fire-nest/Shared/to_JeffDuda/scrip_files/ugrid_fwx1.25km.nc")
    output_root: Path = Path("/home/Benjamin.Koziol/htmp")


@dataclass
class _TestDataGaeaC6(_TestData):
    src_path: Path = Path(
        "/gpfs/f6/gsl-data-depot/world-shared/data/grids/nesdis/3km_fire_emissions/RAVE-HrlyEmiss-3km_v2r0_blend_s202603121200000_e202603121259590_c202603121402030.nc"
    )
    dst_path: Path = Path("/gpfs/f6/drsa-fire3/world-shared/Sudheer/MPAS/mpas-jedi/regridderBen/scrip_files/ugrid_fwx1.25km.nc")
    output_root: Path = Path("/autofs/ncrc-svm1_home2/Benjamin.Koziol/htmp")


@dataclass
class _TestDataColl:
    value: dict[Platform, _TestData] = field(
        default_factory=lambda: {
            Platform.URSA: _TestDataUrsa(),
            Platform.GAEAC6: _TestDataGaeaC6(),
        }
    )


@pytest.mark.integration
@pytest.mark.mpi
def test() -> None:
    pytest.skip("This is a platform integration test. It was used for development and left in in case it proved useful.")
    test_data = _TestDataColl().value[ENV.REGRID_WRAPPER_PLATFORM]
    weight_filename = test_data.output_root / "weights.nc"
    output_file = test_data.output_root / "rave_to_mpas.nc"

    if COMM.rank == 0:
        weight_filename.unlink(missing_ok=True)
        output_file.unlink(missing_ok=True)

    t1 = region_start("rave field")
    rave_gridspec = RaveGridSpec()
    rave_nc2grid = NcToGrid(path=test_data.src_path, spec=rave_gridspec)
    rave_gwrap = rave_nc2grid.create_grid_wrapper()
    rave_nc2field = NcToField(path=test_data.src_path, name="FRE", dim_time=("time",), gwrap=rave_gwrap)
    rave_fwrap = rave_nc2field.create_field_wrapper()
    region_end("rave field", t1)

    t1 = region_start("mpas field")
    mpas_nc2mesh = NcToMesh(path=test_data.dst_path)
    mpas_mwrap = mpas_nc2mesh.create_mesh_wrapper()
    mpas_nc2field = NcToField(
        path=test_data.dst_path,
        name="FRE",
        gwrap=mpas_mwrap,
        load_field_data_from_file=False,
        staggerloc=esmpy.MeshLoc.ELEMENT,
    )
    mpas_fwrap = mpas_nc2field.create_field_wrapper()
    region_end("mpas field", t1)

    t1 = region_start("regridder")
    regridder = esmpy.Regrid(
        srcfield=rave_fwrap.value,
        dstfield=mpas_fwrap.value,
        regrid_method=esmpy.RegridMethod.CONSERVE,
        unmapped_action=esmpy.UnmappedAction.IGNORE,
        ignore_degenerate=True,
        filename=str(weight_filename),
    )
    region_end("regridder", t1)

    t1 = region_start("create output file")
    with open_nc(output_file, mode="w") as ds:
        element_dim = mpas_mwrap.dims.value[0]
        ds.createDimension(element_dim.name[0], element_dim.size)
        ds.createVariable("FRE", float, (element_dim.name[0],))
    region_end("create output file", t1)

    t1 = region_start("regrid field")
    regridder(rave_fwrap.value, mpas_fwrap.value)
    region_end("regrid field", t1)

    t1 = region_start("write field data")
    with open_nc(output_file, mode="a") as ds:
        var = ds.variables["FRE"]
        set_variable_data(var, mpas_fwrap.dims, mpas_fwrap.value.data)
    region_end("write field data", t1)


if __name__ == "__main__":
    test()
