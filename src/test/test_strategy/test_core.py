from regrid_wrapper.model.spec import (
    GenerateWeightFileSpec,
)
from regrid_wrapper.strategy.operation import AbstractRegridOperation
from regrid_wrapper.strategy.core import RegridProcessor
from pytest_mock import MockerFixture


class MockRegridOperation(AbstractRegridOperation):

    def run(self) -> None: ...


class TestRegridProcessor:

    def test_happy_path_mock(
        self, fake_spec: GenerateWeightFileSpec, mocker: MockerFixture
    ) -> None:
        spies = [
            mocker.spy(MockRegridOperation, ii)
            for ii in ["initialize", "run", "finalize"]
        ]
        op = MockRegridOperation(fake_spec)
        processor = RegridProcessor(op)
        processor.execute()
        for spy in spies:
            spy.assert_called_once()
