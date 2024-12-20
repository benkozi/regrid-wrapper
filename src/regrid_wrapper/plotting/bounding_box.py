from typing import List

import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.patches as patches

from regrid_wrapper.geom.bounding_box import BoundingBox


def plot_bounding_boxes(bboxes: List[BoundingBox]) -> None:
    # Create a figure and set the projection
    fig, ax = plt.subplots(
        figsize=(8, 6), subplot_kw={"projection": ccrs.PlateCarree()}
    )

    # Add map features
    ax.add_feature(cfeature.LAND)
    ax.add_feature(cfeature.OCEAN)
    ax.add_feature(cfeature.COASTLINE)
    ax.add_feature(cfeature.BORDERS, linestyle=":")
    ax.gridlines(draw_labels=True)

    for ii in bboxes:
        # Plot the bounding box as a rectangle
        bbox_patch = patches.Rectangle(
            xy=ii.lower_left,  # Lower-left corner of the rectangle
            width=ii.width,  # Width of the rectangle (longitude span)
            height=ii.height,  # Height of the rectangle (latitude span)
            linewidth=ii.plot_spec.linewidth,
            edgecolor=ii.plot_spec.edgecolor,
            facecolor="none",
            transform=ccrs.PlateCarree(),  # Specify the coordinate reference system
        )
        ax.add_patch(bbox_patch)

        # Set the extent of the map
        ax.set_extent(ii.get_padded_extent(5))  # Adding padding

    # Add a title
    plt.title("Bounding Box on Map with Latitude and Longitude")

    # Show the plot
    plt.show()
