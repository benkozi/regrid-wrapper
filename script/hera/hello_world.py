from regrid_wrapper.model.spec import (
    AbstractRegridSpec,
)
from regrid_wrapper.strategy.operation import AbstractRegridOperation
from regrid_wrapper.strategy.core import RegridProcessor


class HelloWorldRegridOperation(AbstractRegridOperation):

    def run(self) -> None:
        self._logger.info("hello world!")


class HelloWorldSpec(AbstractRegridSpec):
    name: str = "hello_world"
    esmpy_debug: bool = True


def main() -> None:
    op = HelloWorldRegridOperation(HelloWorldSpec())
    processor = RegridProcessor(op)
    processor.execute()


if __name__ == "__main__":
    main()
