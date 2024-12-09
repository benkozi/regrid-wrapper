from pathlib import Path

import pytest

from dec_regridding.model.regrid_operation import (
    GenerateWeightFileSpec,
    AbstractRegridSpec,
)


@pytest.mark.mpi
class TestGenerateWeightFileSpec:
    def test_sad_path(self) -> None:
        with pytest.raises(IOError):
            spec = GenerateWeightFileSpec(
                name="name",
                src_path="foo.nc",
                dst_path="bar.nc",
                output_weight_filename="baz.nc",
            )

    def test_happy_path(
        self, tmp_path_shared: Path, fake_spec: AbstractRegridSpec
    ) -> None:
        assert fake_spec is not None
