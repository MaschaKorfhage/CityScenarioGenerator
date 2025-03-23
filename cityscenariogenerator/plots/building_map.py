"""
Generates a plot showing the location of different types of buildings on a map.
"""

from dataclasses import dataclass
from pathlib import Path
import geopandas as gpd  # type: ignore
import matplotlib.pyplot as plt
import contextily as ctx  # type: ignore
from shapely.geometry import Point  # type: ignore

from pylpg.lpgpythonbindings import Coordinates


@dataclass
class PointWithCategory:
    coordinates: Coordinates
    category: str | int

    def get_point(self) -> Point:
        return Point(self.coordinates.Longitude, self.coordinates.Latitude)


def pointlist_to_geodf(data: list[PointWithCategory]) -> gpd.GeoDataFrame:
    """
    Converts a list of points with a category to a GeoDataFrame

    :param data: the points to convert
    :return: the resulting GeoDataFrame
    """
    df: gpd.GeoDataFrame = gpd.GeoDataFrame(geometry=[d.get_point() for d in data])
    category_col = "category"
    df[category_col] = [d.category for d in data]
    # set the coordinate reference system to WGS 84 (EPSG:4326)
    df.set_crs("EPSG:4326", inplace=True)
    return df


def map_locations_plot(data: list[PointWithCategory], path: Path | None):
    """
    Plots each building or relevant point on a map, indicating its category by color.

    :param data: list of buildings/POIs with coordinates and a category
    :param path: directory where to save the image file, or None
    """
    category_col = "category"
    df = pointlist_to_geodf(data)

    # convert to Web Mercator
    df.to_crs("EPSG:3857", inplace=True)

    # Plot
    fig, ax = plt.subplots(figsize=(10, 8))
    df.plot(
        ax=ax,
        column=category_col,
        categorical=True,
        legend=True,
        markersize=30,
        cmap="tab20",
    )

    # Add basemap
    ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik)

    # make the plot a bit smaller to make room for the legend
    box = ax.get_position()
    ax.set_position([box.x0, box.y0, box.width * 0.7, box.height])  # type: ignore

    # move the legend to the right, outside of the plot
    legend = ax.get_legend()
    legend.set_bbox_to_anchor((1.1, 1))

    # save and show the plot
    if path is not None:
        fig.savefig(path / "map.png")
    # plt.show()


if __name__ == "__main__":
    # Example data
    data_raw: list = [
        {"x": 6.95, "y": 50.94, "category": "A"},  # Cologne
        {"x": 6.57, "y": 50.93, "category": "B"},  # Bonn
        {"x": 7.10, "y": 50.74, "category": "A"},  # Siegburg
        {"x": 7.15, "y": 50.73, "category": "C"},  # Hennef
    ]
    data = [
        PointWithCategory(Coordinates(d["y"], d["x"]), d["category"]) for d in data_raw
    ]
    map_locations_plot(data, None)
