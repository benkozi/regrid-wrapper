import numpy as np
import pytest

from regrid_wrapper.context.comm import COMM, reconcile_bounds
from test.conftest import TEST_LOGGER


@pytest.mark.mpi
def test_reconcile_bounds() -> None:
    offset = 100
    local_bounds = (0, COMM.rank + offset + np.random.randint(1, 100))
    reconciled_bounds = reconcile_bounds(local_bounds)
    TEST_LOGGER.debug(f"{reconciled_bounds=}")
    all_reconciled_bounds = COMM.allgather(reconciled_bounds)
    TEST_LOGGER.debug(f"{all_reconciled_bounds=}")
    basis = np.arange(all_reconciled_bounds[-1][1])
    expected = np.sum(basis)
    actual = 0
    for bounds in all_reconciled_bounds:
        actual += np.sum(basis[bounds[0] : bounds[1]])
    print(actual, expected)
    assert actual == expected
