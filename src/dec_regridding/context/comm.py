from typing import Any, List

from mpi4py import MPI


class Comm:
    MPI = MPI

    def __init__(self):
        self._comm = MPI.COMM_WORLD

    @property
    def rank(self) -> int:
        return self._comm.Get_rank()

    @property
    def size(self) -> int:
        return self._comm.Get_size()

    def barrier(self) -> None:
        self._comm.barrier()

    def bcast(self, value: dict, root: int = 0) -> Any:
        return self._comm.bcast(value, root=root)


COMM = Comm()
