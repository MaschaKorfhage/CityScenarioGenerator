import logging
from pathlib import Path
from typing import Iterable
import folium
import geopandas as gpd  # type: ignore

from builda_client.dev_client import Building  # type: ignore
from shapely import Point  # type: ignore

from cityscenariogenerator import builda_client_import
from cityscenariogenerator.plots.building_map_interactive import MARKER_COLORS
import cityscenariogenerator.plots.unmapped_building_map as buil_map
from cityscenariogenerator.poi_type_mapping import (
    BuildingWithLocationType,
    LocationType,
)
from cityscenariogenerator.overpass_import import overpass_query

#: directory with input OSM data from overpass
OVERPASS_DATA_DIR = Path("data/osm_input_data")


class DFColumns:
    BUILDA_ID = "id_builda"
    OSM_ID = "id"


def load_overpass_data(city: str):
    filepath = OVERPASS_DATA_DIR / "{location}.geojson"
    overpass_df = gpd.read_file(filepath)
    print(overpass_df.head())
    return overpass_df


def builda_to_geodf(buildings: Iterable[Building]) -> gpd.GeoDataFrame:
    # store in list to allow iterating multiple times
    building_list = list(buildings)
    # Convert to GeoDataFrame
    geometry = [
        Point(b.coordinates.longitude, b.coordinates.latitude) for b in building_list
    ]
    data = {DFColumns.BUILDA_ID: [b.id for b in building_list]}
    df = gpd.GeoDataFrame(data, geometry=geometry)
    df.set_crs("EPSG:4326", inplace=True)
    return df


def adapt_joined_df(joined_df, geometry_col: str):
    joined_df[geometry_col] = joined_df.geometry.to_crs("EPSG:4326")
    joined_df["popup"] = (
        joined_df["id_left"]
        + " - "
        + joined_df["id_right"]
        + "\n"
        + joined_df["amenity"]
        + "\n"
        + joined_df["distance"].round(1).astype(str)
        + " m"
    )


def remove_duplicate_matches(df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    After a spatial join, removes duplicate matches to the same point of
    the left dataframe. Only keeps the closest match of the right dataframe.
    The result is a 1-to-1 matching between points from left and right.

    :param df: dataframe with result of spatial join
    :return: filtered dataframe
    """
    # filter duplicate matches
    filtered = df.sort_values(by="distance").drop_duplicates(
        subset=["id_right"], keep="first"
    )
    print(f"Removed {len(df) - len(filtered)} duplicate matches")
    return filtered


def add_markers_for_df(joined_df, m, color: str, geometry_col: str):
    for _, row in joined_df.iterrows():
        folium.Marker(
            location=[row[geometry_col].y, row[geometry_col].x],
            popup=row.get("popup"),
            icon=folium.Icon(color=color),
        ).add_to(m)


def plot_map(dataframes: list[gpd.GeoDataFrame], name: str, geometry_col: str):
    first_df = dataframes[0]
    # create a Folium map centered on the average coordinates
    map_1 = folium.Map(
        location=[
            first_df[geometry_col].y.mean(),
            first_df[geometry_col].x.mean(),
        ],
        zoom_start=12,
    )
    marker_cluster = folium.plugins.MarkerCluster().add_to(map_1)
    # create markers for each dataframe
    for i, df in enumerate(dataframes):
        color = MARKER_COLORS[i % len(MARKER_COLORS)]
        add_markers_for_df(df, marker_cluster, color, geometry_col)

    # Save map to an HTML file and display
    map_1.save(name)
    map_1.show_in_browser()


def get_nonwork_location_for_node(mappings: dict[str, dict], row) -> LocationType:
    for key, mapping in mappings.items():
        # check if the key for this mapping (e.g. 'amenity') is given for this node
        if val := row.get(key):
            # check if the value for the key has a mapping entry
            if loc := mapping.get(val):
                return loc
        # otherwhise continue trying with the remaining mappings
    # If no mapping has an entry, a suitable location cannot be determined for this node.
    # This should not happen, as only relevant nodes are queried from overpass.
    raise Exception(f"Could not match an OSM node: {row}")


def map_osm_node(mappings: dict[str, dict], row) -> LocationType:
    nonwork_location = get_nonwork_location_for_node(mappings, row)
    work_locations = []  # TODO
    return LocationType([nonwork_location], work_locations)


def map_osm_tags_to_locations(
    data: gpd.GeoDataFrame, keys: list[str]
) -> dict[str, LocationType]:
    mappings = {key: overpass_query.load_osm_mapping(key) for key in keys}
    # TODO: load mapping for work locations
    osm_node_location_types = {
        row[DFColumns.OSM_ID]: map_osm_node(
            mappings,
        )
        for row in data.iterrows()
    }
    return osm_node_location_types


def add_osm_location_types(buildings: dict[str, BuildingWithLocationType]) -> None:
    overpass_df = load_overpass_data("Aachen")
    # convert BUILDA objects to GeoDataFrame
    builda_df = builda_to_geodf(b.building for b in buildings.values())

    overpass_df.to_crs("EPSG:3857", inplace=True)
    builda_df.to_crs("EPSG:3857", inplace=True)

    # spatial join
    joined_df = gpd.sjoin_nearest(
        overpass_df,
        builda_df,
        distance_col="distance",
        exclusive=False,
        max_distance=20,
    )
    joined_df = remove_duplicate_matches(joined_df)
    logging.info(f"Matched {len(joined_df)} non-residential buildings to OSM nodes.")
    keys = ["amenity", "healthcare", "office"]
    osm_node_locations = map_osm_tags_to_locations(joined_df, keys)

    # assign OSM locations to BUILDA buildings
    for row in joined_df.iterrows():
        # get the matching location type for the OSM node
        osm_loc_type = osm_node_locations[row[DFColumns.OSM_ID]]
        # assign this location type to the corresponding BUILDA building
        buildings[row[DFColumns.BUILDA_ID]].location_type = osm_loc_type


def main():
    # load overpass building data
    overpass_df = load_overpass_data("Aachen")

    # collect non-residential buildings
    builda_query = {
        "city": "Aachen",
        # "postcode": "52066",
        # "street": "Eupener Straße",
    }
    nonres_buildings = builda_client_import.get_nonresidential_buildings(builda_query)

    # convert BUILDA objects to GeoDataFrame
    builda_df = builda_to_geodf(nonres_buildings)
    builda_df["category"] = [
        buil_map.get_building_category_alkis(b) for b in nonres_buildings
    ]

    # convert to Web Mercator projection to get correct distances, but save old geometry first
    geometry_4326 = "geometry_4326"
    overpass_df[geometry_4326] = overpass_df.geometry
    builda_df[geometry_4326] = builda_df.geometry
    overpass_df.to_crs("EPSG:3857", inplace=True)
    builda_df.to_crs("EPSG:3857", inplace=True)

    # add a column for the popup text
    builda_df["popup"] = builda_df["id"] + "\n" + builda_df["category"]
    overpass_df["popup"] = overpass_df["id"] + "\n" + overpass_df["amenity"]

    # spatial join
    joined_df = gpd.sjoin_nearest(
        overpass_df,
        builda_df,
        distance_col="distance",
        exclusive=False,
        max_distance=20,
    )
    adapt_joined_df(joined_df, geometry_4326)

    joined_df = remove_duplicate_matches(joined_df)

    print(
        f"Builda: {len(builda_df)}, Overpass: {len(overpass_df)}, Joined: {len(joined_df)}, "
    )
    # unique_ids_left = len(joined_df["id_left"].unique())
    # unique_ids_right = len(joined_df["id_right"].unique())
    # print(f"Unique IDs left: {unique_ids_left}, right: {unique_ids_right}")

    plot_map([builda_df, overpass_df, joined_df], "health_map.html", geometry_4326)

    # TODO: compare OSM tags in overpass with ALKIS codes in Builda (use raw unmapped builda data, mapping happens later with OSM tags)

    pass


if __name__ == "__main__":
    main()
