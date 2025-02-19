from pathlib import Path

from regrid_wrapper.geom.grid import Grid
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import cartopy.crs as ccrs


def main() -> None:
    path = Path(
        r"C:\Users\bkozi\Dropbox\rlps\rsandbox\regrid-wrapper\RRFS_CONUS_25km\ds_out_base.nc"
    )
    grid = Grid(path=path, lat_name="grid_latt", lon_name="grid_lont")
    print(grid.describe())

    # Create a figure and set the projection
    fig, ax = plt.subplots(
        figsize=(8, 6), subplot_kw={"projection": ccrs.PlateCarree()}
    )

    # Add map features
    ax.add_feature(cfeature.LAND)
    ax.add_feature(cfeature.OCEAN)
    ax.add_feature(cfeature.COASTLINE)
    ax.add_feature(cfeature.BORDERS, linestyle=":")
    ax.add_feature(cfeature.STATES)
    ax.gridlines(draw_labels=True)

    lon_grid = grid.get(grid.lon_name)
    lat_grid = grid.get(grid.lat_name)
    ax.scatter(
        lon_grid,
        lat_grid,
        color="red",
        s=1,
        marker="o",
        edgecolor="red",
        label="Points",
        transform=ccrs.PlateCarree(),
    )

    lon_grid_corners = grid.get("grid_lon")
    lat_grid_corners = grid.get("grid_lat")
    ax.scatter(
        lon_grid_corners,
        lat_grid_corners,
        color="black",
        s=1,
        marker="x",
        edgecolor="black",
        label="Points",
        transform=ccrs.PlateCarree(),
    )

    # ax.set_extent(grid.get_bounding_box().get_padded_extent(5))
    ax.set_extent(
        [lon_grid[0, 0] - 1, lon_grid[0, 0] + 1, lat_grid[0, 0] - 1, lat_grid[0, 0] + 1]
    )

    plt.title(grid.path.name)

    plt.show()


if __name__ == "__main__":
    main()
