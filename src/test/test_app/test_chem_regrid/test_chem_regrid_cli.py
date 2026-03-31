import pytest
from pathlib import Path
from regrid_wrapper.app.chem_regrid.context import ChemRegridContext, DatasetName

def generate_chem_regrid_context(
    root_path: Path, use_scrip: bool = True, use_dst: bool = True
) -> ChemRegridContext:
    """
    Generate a ChemRegridContext object.
    If a field has a None type, it should generate both with the provided value and without it.
    """
    
    # Required fields with example values
    base_params = {
        "dataset_name": DatasetName.RAVE,
        "workdir": root_path / "workdir",
        "input_dir": root_path / "input_dir",
        "output_dir": root_path / "output_dir",
        "weight_dir": root_path / "weight_dir",
        "cycle": "2026033114",
        "mesh_name": "test_mesh",
        "ebb_dcycle": 1,
    }

    # Fields that can be None
    params = base_params.copy()
    params["scrip_path"] = root_path / "scrip.nc" if use_scrip else None
    params["dst_path"] = root_path / "dst.nc" if use_dst else None
    
    return ChemRegridContext(**params)

@pytest.mark.parametrize("use_scrip", [True, False], ids=["scrip_path", "no_scrip_path"])
@pytest.mark.parametrize("use_dst", [True, False], ids=["dst_path", "no_dst_path"])
def test_generate_chem_regrid_context(use_scrip: bool, use_dst: bool):
    root_path = Path("/tmp")
    context = generate_chem_regrid_context(root_path, use_scrip=use_scrip, use_dst=use_dst)
    
    assert isinstance(context, ChemRegridContext)
    
    if use_scrip:
        assert context.scrip_path == root_path / "scrip.nc"
    else:
        assert context.scrip_path is None
        
    if use_dst:
        assert context.dst_path == root_path / "dst.nc"
    else:
        assert context.dst_path is None
