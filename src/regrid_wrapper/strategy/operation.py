import abc

import esmpy

from regrid_wrapper.context.logging import LOGGER
from regrid_wrapper.model.spec import AbstractRegridSpec


class AbstractRegridOperation(abc.ABC):

    def __init__(self, spec: AbstractRegridSpec) -> None:
        self._spec = spec
        self._logger = LOGGER.getChild("operation").getChild(spec.name)
        self._esmf_manager: None | esmpy.Manager = None

    def initialize(self) -> None:
        self._logger.info(f"initializing regrid operation: {self._spec.name}")
        self._esmf_manager = esmpy.Manager(debug=self._spec.esmpy_debug)

    @abc.abstractmethod
    def run(self) -> None: ...

    def finalize(self) -> None:
        self._logger.info(f"finalizing regrid operation: {self._spec.name}")
