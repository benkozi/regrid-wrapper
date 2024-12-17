from regrid_wrapper.context.logging import LOGGER
from regrid_wrapper.strategy.operation import AbstractRegridOperation


class RegridProcessor:

    def __init__(self, operation: AbstractRegridOperation) -> None:
        self._operation = operation
        self._logger = LOGGER.getChild("regrid-processor")

    def execute(self) -> None:
        self._logger.info("start: execute")
        self._operation.initialize()
        self._operation.run()
        self._operation.finalize()
        self._logger.info("end: execute")
