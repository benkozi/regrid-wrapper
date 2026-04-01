from pathlib import Path

import pytest
from _pytest.fixtures import FixtureRequest
from pydantic import BaseModel

from regrid_wrapper.app.chem_regrid.context import ChemRegridContext, DatasetName
from test.conftest import TEST_LOGGER


class ContextForTest(BaseModel):
    root_path: Path
    use_scrip: bool
    use_dst: bool


def create_chem_regrid_context(test_context: ContextForTest) -> ChemRegridContext:
    """
    Generate a ChemRegridContext object.
    If a field has a None type, it should generate both with the provided value and without it.
    """

    # Required fields with example values
    base_params = {
        "dataset_name": DatasetName.RAVE,
        "workdir": test_context.root_path / "workdir",
        "input_dir": test_context.root_path / "input_dir",
        "output_dir": test_context.root_path / "output_dir",
        "weight_dir": test_context.root_path / "weight_dir",
        "cycle": "2026033114",
        "mesh_name": "test_mesh",
        "ebb_dcycle": 1,
        "fcst_length": 6,
    }

    # Fields that can be None
    params = base_params.copy()
    params["scrip_path"] = test_context.root_path / "scrip.nc" if test_context.use_scrip else None
    params["dst_path"] = test_context.root_path / "dst.nc" if test_context.use_dst else None

    return ChemRegridContext.model_validate(params)


@pytest.fixture(params=[True, False])
def use_scrip_path(request: FixtureRequest) -> bool:
    return request.param


@pytest.fixture(params=[True, False])
def use_dst_path(request: FixtureRequest) -> bool:
    return request.param


@pytest.fixture()
def context_for_test(use_scrip_path: bool, use_dst_path: bool, tmp_path_shared: Path) -> ContextForTest:
    return ContextForTest(root_path=tmp_path_shared, use_scrip=use_scrip_path, use_dst=use_dst_path)


@pytest.fixture
def chem_regrid_context(context_for_test: ContextForTest) -> ChemRegridContext:
    TEST_LOGGER.debug(f"{context_for_test=}")
    return create_chem_regrid_context(context_for_test)


def test_generate_chem_regrid_context(chem_regrid_context: ChemRegridContext, context_for_test: ContextForTest) -> None:
    TEST_LOGGER.debug(f"{chem_regrid_context=}")

    assert isinstance(chem_regrid_context, ChemRegridContext)

    if context_for_test.use_scrip:
        assert chem_regrid_context.scrip_path == context_for_test.root_path / "scrip.nc"
    else:
        assert chem_regrid_context.scrip_path is None

    if context_for_test.use_dst:
        assert chem_regrid_context.dst_path == context_for_test.root_path / "dst.nc"
    else:
        assert chem_regrid_context.dst_path is None
