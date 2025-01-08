import pandas as pd

from regrid_wrapper.geom.grid import Grid
from regrid_wrapper.geom.plot_spec import PlotSpec
from regrid_wrapper.plotting.bounding_box import plot_bounding_boxes


def main() -> None:
    # bbox = BoundingBox(min_lon=-120, max_lon=-110, min_lat=30, max_lat=40)
    # Hera
    # ncdump - h / scratch1 / BMC / acomp / Johana / rrfs - sd_v1 / AGU2024_2019_persistance / stmp / 2019080100 / fcst_fv3lam / grid_spec.nc
    grids = [
        # Grid(
        #     path=r"C:\Users\bkozi\sandbox\BenKoziol-NOAA\data-root\RRFS_CONUS_3km\ds_out_base.nc",
        #     lat_name="grid_latt",
        #     lon_name="grid_lont",
        # ),
        # Grid(
        #     path=r"C:\Users\bkozi\sandbox\BenKoziol-NOAA\data-root\RRFS_CONUS_3km\C3359_oro_data_ls.tile7.halo0.nc",
        #     lat_name="geolat",
        #     lon_name="geolon",
        #     plot_spec=PlotSpec(edgecolor="blue", linewidth=1),
        # ),
        # Grid(
        #     path=r"C:\Users\bkozi\sandbox\BenKoziol-NOAA\data-root\RRFS_CONUS_3km\grid_in.nc",
        #     lat_name="grid_latt",
        #     lon_name="grid_lont",
        # ),
        # Grid(
        #     path=r"C:\Users\bkozi\sandbox\BenKoziol-NOAA\data-root\RRFS_CONUS_13km\ds_out_base.nc",
        #     lat_name="grid_latt",
        #     lon_name="grid_lont",
        # ),
        Grid(
            path=r"C:\Users\bkozi\sandbox\BenKoziol-NOAA\data-root\RRFS_NA_3km\veg_map.nc",
            lat_name="geolat",
            lon_name="geolon",
        ),
    ]
    bboxes = []
    descriptions = []
    for grid in grids:
        descriptions.append(grid.describe())
        bbox = grid.get_bounding_box()
        bboxes.append(bbox)
    plot_bounding_boxes(bboxes)
    grid_descriptions = pd.concat(descriptions, axis=0)
    grid_descriptions.to_csv("grid_descriptions.csv", index=False)


if __name__ == "__main__":
    main()
