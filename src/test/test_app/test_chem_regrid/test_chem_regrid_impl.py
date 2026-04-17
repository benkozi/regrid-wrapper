from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from regrid_wrapper.app.chem_regrid.chem_regrid_impl import main
from regrid_wrapper.app.chem_regrid.context import ChemRegridContext, DatasetName
from test.test_app.test_chem_regrid.conftest import DatasetTestContext


@pytest.mark.mpi
def test_mock_chem_regrid_impl_rave_integration(chem_regrid_context: ChemRegridContext) -> None:
    if chem_regrid_context.dataset_name != DatasetName.RAVE:
        pytest.skip("test only for RAVE dataset")
    # Mock RaveToMpasRegridProcessor to avoid actual regridding
    with (
        patch("regrid_wrapper.app.chem_regrid.chem_regrid_impl.RaveToMpasRegridProcessor") as mock_processor_class,
        patch("regrid_wrapper.app.chem_regrid.chem_regrid_impl.RaveToMpasRegridContext") as _,
    ):
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor

        # Run main
        main(chem_regrid_context)

        # Verify the loop ran 25 times
        # processor is initialized once (processor is None for the first pass)
        # then updated 24 times
        assert mock_processor_class.call_count == 1
        assert mock_processor.run.call_count == 25


@pytest.mark.mpi
def test_chem_regrid_impl_rave_integration(
    tmp_path_shared: Path, chem_regrid_context: ChemRegridContext, dataset_test_ctx: DatasetTestContext
) -> None:
    main(chem_regrid_context)
    dataset_test_ctx.verify_output_data_files()
    dataset_test_ctx.verify_weight_files()
