import pytest

from regrid_wrapper.app.chem_regrid.context import ChemRegridContext
from regrid_wrapper.app.chem_regrid.dataset.model import ChemRegridDataset, DatasetName


@pytest.mark.parametrize("dataset_name", DatasetName)
def test_from_key(dataset_name: DatasetName) -> None:
    yaml_path = ChemRegridContext.model_fields["datasets_yml_path"].default
    ds = ChemRegridDataset.from_key(yaml_path, dataset_name)
    assert ds.key == dataset_name
