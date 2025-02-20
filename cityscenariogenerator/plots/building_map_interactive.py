"""
Generates an interactive html map showing the location of different types of buildings.
"""

from pathlib import Path
import folium
import folium.plugins
import geopandas as gpd  # type: ignore
import matplotlib.cm as cm
import matplotlib.colors as mcolors

from pylpg.lpgpythonbindings import Coordinates  # type: ignore

from cityscenariogenerator.plots.building_map import PointWithCategory


def map_locations_plot_html(data: list[PointWithCategory], path: Path):
    """
    Plots each building or relevant point on a map, indicating its category by color.

    :param data: list of buildings/POIs with coordinates and a category
    :param path: directory where to save the html map file
    """
    # Convert to GeoDataFrame
    df: gpd.GeoDataFrame = gpd.GeoDataFrame(geometry=[d.get_point() for d in data])
    category_col = "category"
    df[category_col] = [d.category for d in data]

    # Define a colormap for categories
    icon_color_map = {"A": "red", "B": "blue", "C": "green"}

    # Create a Folium map centered on the average coordinates
    m = folium.Map(location=[df.geometry.y.mean(), df.geometry.x.mean()], zoom_start=12)

    # all colors that can be used for markers
    marker_colors = [
        "red",
        "blue",
        "green",
        "purple",
        "orange",
        "darkred",
        "lightred",
        "beige",
        "darkblue",
        "darkgreen",
        "cadetblue",
        "darkpurple",
        "white",
        "pink",
        "lightblue",
        "lightgreen",
        "gray",
        "black",
        "lightgray",
    ]
    # additional icon colors to distinguish categories with the same marker color
    icon_colors = ["white", "black", "gray"]

    # Generate categorical colormap
    categories = df["category"].unique()
    # Use a standard discrete colormap
    # color_map = cm.get_cmap("tab10", len(categories))

    icon_color_map = {
        cat: mcolors.to_hex(icon_colors[i // len(marker_colors)])
        for i, cat in enumerate(categories)
    }
    marker_color_map = {
        cat: marker_colors[i % len(marker_colors)] for i, cat in enumerate(categories)
    }

    marker_cluster = folium.plugins.MarkerCluster().add_to(m)

    # Add markers
    for _, row in df.iterrows():
        folium.Marker(
            location=[row.geometry.y, row.geometry.x],
            popup=f"Category: {row['category']}",
            # tooltip=f"Category: {row['category']}",
            icon=folium.Icon(
                color=marker_color_map[row["category"]],
                icon_color=icon_color_map.get(row["category"], "gray"),
            ),
            # color=color_map.get(row["category"], "gray"),
            # fill=True,
            # fill_opacity=1,
        ).add_to(marker_cluster)

    # Save map to an HTML file and display
    m.save(path / "poi_map.html")
    m.show_in_browser()


if __name__ == "__main__":
    # Example data
    data_raw: list = [
        {"x": 6.95, "y": 50.94, "category": "A"},
        {"x": 6.95, "y": 50.94, "category": "C"},
        {"x": 6.57, "y": 50.93, "category": "B"},
        {"x": 7.10, "y": 50.74, "category": "A"},
        {"x": 7.15, "y": 50.73, "category": "C"},
    ]
    data = [
        PointWithCategory(Coordinates(d["y"], d["x"]), d["category"]) for d in data_raw
    ]
    map_locations_plot_html(data, Path.cwd())
