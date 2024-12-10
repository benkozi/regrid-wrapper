from regrid_wrapper.model.regrid_operation import AbstractRegridOperation


class RegridProcessor:

    def __init__(self, operation: AbstractRegridOperation) -> None:
        self._operation = operation

    def execute(self) -> None:
        self._operation.initialize()
        self._operation.run()
        self._operation.finalize()
