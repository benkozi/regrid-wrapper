import numpy as np


def test_moveaxis() -> None:
    arr = np.array([[1, 2, 3], [4, 5, 6]])
    # print(arr)
    moved = np.moveaxis(arr, 0, 1)
    # print(moved.tolist())
    assert np.array_equal(moved, np.array([[1, 4], [2, 5], [3, 6]]))
