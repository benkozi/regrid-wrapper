from pathlib import Path

from regrid_wrapper.geom.grid import Grid
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import cartopy.crs as ccrs


def main() -> None:
    path = Path(
        r"C:\Users\bkozi\Dropbox\rlps\rsandbox\regrid-wrapper\RRFS_CONUS_25km\veg_map.nc"
    )
    grid = Grid(path=path, lat_name="geolat", lon_name="geolon")
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
    data = grid.get("emiss_factor")
    mesh = ax.pcolormesh(
        lon_grid,
        lat_grid,
        data,
        cmap="viridis",
        shading="auto",
        transform=ccrs.PlateCarree(),
    )

    ax.set_extent(grid.get_bounding_box().get_padded_extent(5))

    plt.title(grid.path.name)

    cbar = plt.colorbar(mesh, ax=ax, orientation="vertical", shrink=0.7, pad=0.05)
    cbar.set_label("Data Values")

    plt.show()


if __name__ == "__main__":
    main()
