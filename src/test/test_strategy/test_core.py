from dec_regridding.model.regrid_operation import (
    AbstractRegridOperation,
    GenerateWeightFileSpec,
)
from dec_regridding.strategy.core import RegridProcessor


class MockRegridOperation(AbstractRegridOperation):

    def run(self) -> None: ...


class TestRegridProcessor:

    def test_happy_path_mock(self, fake_spec: GenerateWeightFileSpec) -> None:
        op = MockRegridOperation(fake_spec)
        processor = RegridProcessor(op)
        processor.execute()
