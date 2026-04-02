import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from regrid_wrapper.app.mpas_to_ugrid_cli import mpas_to_ugrid_cli


@pytest.mark.parametrize("clobber", [True, False])
def test_mpas_to_ugrid_cli(tmp_path: Path, clobber: bool) -> None:
    input = tmp_path / "input.nc"
    output = tmp_path / "output.nc"
    input.touch()
    output.touch()

    args = argparse.Namespace(input=str(input), output=str(output), clobber=clobber)

    with patch("regrid_wrapper.mpas.mpas_to_ugrid.run_conversion") as mock_run:
        try:
            mpas_to_ugrid_cli(args)
            mock_run.assert_called_once_with(input, output)
        except IOError:
            assert not clobber
            mock_run.assert_not_called()
