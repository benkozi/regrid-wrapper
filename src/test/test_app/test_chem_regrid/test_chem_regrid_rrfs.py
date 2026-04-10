from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from regrid_wrapper.app.chem_regrid import chem_regrid_rrfs
from regrid_wrapper.app.chem_regrid.chem_regrid_rrfs import ChemRegridEnv
from regrid_wrapper.app.chem_regrid.context import DatasetName


def test_chem_regrid_env_from_env_vars() -> None:
    env_vars = {"EBB_DCYCLE": "12", "FCST_LENGTH": "48", "MESH_NAME": "test_mesh"}
    with patch.dict("os.environ", env_vars):
        env = ChemRegridEnv()  # type: ignore[call-arg]
        assert env.ebb_dcycle == 12
        assert env.fcst_length == 48
        assert env.mesh_name == "test_mesh"


def test_chem_regrid_env_missing_vars() -> None:
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValidationError):  # Pydantic ValidationError
            ChemRegridEnv()  # type: ignore[call-arg]


def test_main_calls_chem_regrid_main(tmp_path: Path) -> None:
    env_vars = {"EBB_DCYCLE": "12", "FCST_LENGTH": "48", "MESH_NAME": "test_mesh"}
    mock_argv = [
        "chem_regrid_rrfs.py",
        DatasetName.RAVE.value,
        str(tmp_path),
        str(tmp_path),
        str(tmp_path),
        str(tmp_path),
        "2026040213",
    ]

    with (
        patch.dict("os.environ", env_vars),
        patch("sys.argv", mock_argv),
        patch("regrid_wrapper.app.chem_regrid.chem_regrid_rrfs.chem_regrid_impl_main") as mock_chem_regrid_main,
    ):
        chem_regrid_rrfs.main()
        mock_chem_regrid_main.assert_called_once()
