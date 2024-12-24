import esmpy
import numpy as np

DEG2RAD = 3.141592653589793 / 180.0


def test() -> None:
    import esmpy

    assert esmpy is not None


def test_xy_ordering_behavior() -> None:
    x, y = [0, 1]
    lat = [33, 44, 55]
    lon = [-104, -80, -60]  # tdk: test with unwrapped

    lon_mesh, lat_mesh = np.meshgrid(lon, lat)

    grid = esmpy.Grid(
        np.array(lat_mesh.shape),
        coord_sys=esmpy.CoordSys.SPH_DEG,
        staggerloc=[esmpy.StaggerLoc.CENTER],
    )

    x_coords = grid.get_coords(x, staggerloc=esmpy.StaggerLoc.CENTER)
    x_coords[:] = lon_mesh

    y_coords = grid.get_coords(y, staggerloc=esmpy.StaggerLoc.CENTER)
    y_coords[:] = lat_mesh

    src_field = esmpy.Field(grid, name="src")
    src_field.data[:] = 2.0 + np.cos(DEG2RAD * lon_mesh) ** 2 * np.cos(
        2.0 * DEG2RAD * (90.0 - lat_mesh)
    )

    dst_field = esmpy.Field(grid, name="dst")

    regrid = esmpy.Regrid(
        src_field, dst_field, regrid_method=esmpy.RegridMethod.BILINEAR
    )

    dst_field = regrid(src_field, dst_field)

    print(src_field.data)
    print(dst_field.data)
    print(src_field.data - dst_field.data)
    print(np.mean(dst_field.data))
