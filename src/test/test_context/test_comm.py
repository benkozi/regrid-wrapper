import numpy as np
import pytest

from regrid_wrapper.context.comm import COMM, reconcile_bounds
from test.conftest import TEST_LOGGER


@pytest.mark.mpi
def test_reconcile_bounds() -> None:
    total_elements = COMM.size * 10 + 5
    if COMM.rank <= 4:
        local_bounds = (0, 11)
    else:
        local_bounds = (0, 10)
    TEST_LOGGER.debug(f"{local_bounds=}")
    reconciled_bounds = reconcile_bounds(local_bounds)
    TEST_LOGGER.debug(f"test {reconciled_bounds=}")
    all_reconciled_bounds = COMM.allgather(reconciled_bounds)
    TEST_LOGGER.debug(f"{all_reconciled_bounds=}")
    basis = np.arange(total_elements)
    assert total_elements == all_reconciled_bounds[-1][1]
    expected = np.sum(basis)
    actual = 0
    for bounds in all_reconciled_bounds:
        actual += np.sum(basis[bounds[0] : bounds[1]])
    assert actual == expected
