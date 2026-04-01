import pytest
from pathlib import Path
from pydantic import BaseModel
from regrid_wrapper.app.chem_regrid.context import ChemRegridContext, DatasetName

class ContextForTest(BaseModel):
    root_path: Path
    use_scrip: bool
    use_dst: bool

def generate_chem_regrid_context(test_context: ContextForTest) -> ChemRegridContext:
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
    }

    # Fields that can be None
    params = base_params.copy()
    params["scrip_path"] = test_context.root_path / "scrip.nc" if test_context.use_scrip else None
    params["dst_path"] = test_context.root_path / "dst.nc" if test_context.use_dst else None
    
    return ChemRegridContext(**params)

@pytest.fixture(
    params=[
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ],
    ids=[
        "scrip-dst",
        "scrip-no_dst",
        "no_scrip-dst",
        "no_scrip-no_dst",
    ]
)
def context_for_test(request) -> ContextForTest:
    use_scrip, use_dst = request.param
    return ContextForTest(
        root_path=Path("/tmp"),
        use_scrip=use_scrip,
        use_dst=use_dst
    )

def test_generate_chem_regrid_context(context_for_test: ContextForTest):
    context = generate_chem_regrid_context(context_for_test)
    
    assert isinstance(context, ChemRegridContext)
    
    if context_for_test.use_scrip:
        assert context.scrip_path == context_for_test.root_path / "scrip.nc"
    else:
        assert context.scrip_path is None
        
    if context_for_test.use_dst:
        assert context.dst_path == context_for_test.root_path / "dst.nc"
    else:
        assert context.dst_path is None
