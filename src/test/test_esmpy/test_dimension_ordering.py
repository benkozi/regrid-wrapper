from pathlib import Path

import numpy as np
import esmpy

from regrid_wrapper.common import ncdump


def test_same_index(tmp_path_shared: Path) -> None:
    x_index, y_index = 0, 1
    first = run_esmpy(tmp_path_shared, "one-same", x_index, y_index)
    x_index, y_index = 0, 1
    second = run_esmpy(tmp_path_shared, "two-same", x_index, y_index)
    diff = first - second
    assert diff.sum() == 0.0


def test_different_index(tmp_path_shared: Path) -> None:
    x_index, y_index = 0, 1
    first = run_esmpy(tmp_path_shared, "one-diff", x_index, y_index)
    x_index, y_index = 1, 0
    second = run_esmpy(tmp_path_shared, "two-diff", x_index, y_index)
    diff = first - second
    assert diff.sum() != 0.0


def run_esmpy(root_path: Path, tag: str, x_index: int, y_index: int) -> np.ndarray:
    weight_file = root_path / f"weights_{tag}_{x_index}_{y_index}.nc"
    src_lon = [230.0, 300.0]
    src_lat = [25.0, 50.0]
    src_lon_mesh, src_lat_mesh = np.meshgrid(src_lon, src_lat)
    dst_lon = [265.0]
    dst_lat = [37.5]
    dst_lon_mesh, dst_lat_mesh = np.meshgrid(dst_lon, dst_lat)

    src_grid = esmpy.Grid(
        max_index=np.array([2, 2]),
        staggerloc=esmpy.StaggerLoc.CENTER,
        coord_sys=esmpy.CoordSys.SPH_DEG,
    )
    src_grid.get_coords(x_index, staggerloc=esmpy.StaggerLoc.CENTER)[:] = src_lon_mesh
    src_grid.get_coords(y_index, staggerloc=esmpy.StaggerLoc.CENTER)[:] = src_lat_mesh
    dst_grid = esmpy.Grid(
        max_index=np.array([1, 1]),
        staggerloc=esmpy.StaggerLoc.CENTER,
        coord_sys=esmpy.CoordSys.SPH_DEG,
    )
    dst_grid.get_coords(x_index, staggerloc=esmpy.StaggerLoc.CENTER)[:] = dst_lon_mesh
    dst_grid.get_coords(y_index, staggerloc=esmpy.StaggerLoc.CENTER)[:] = dst_lat_mesh

    src_field = esmpy.Field(src_grid)
    src_field.data[:] = np.arange(1, 5, dtype=float).reshape(2, 2)
    dst_field = esmpy.Field(dst_grid)

    _ = esmpy.Regrid(src_field, dst_field, filename=str(weight_file))
    ncdump(weight_file, header_only=False)

    return dst_field.data
