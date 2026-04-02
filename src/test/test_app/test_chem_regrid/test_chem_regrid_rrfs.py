from unittest.mock import patch

import pytest
from pydantic import ValidationError

from regrid_wrapper.app.chem_regrid.chem_regrid_rrfs import ChemRegridEnv


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
