"""
Loads OpenStreetMap (OSM) node data from overpass turbo and does a spatial join
with BUILDA buildings to add better location types to non-residential buildings.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Iterable
import folium
import geopandas as gpd  # type: ignore

from builda_client.dev_client import Building  # type: ignore
import pandas as pd
from shapely import Point  # type: ignore

from cityscenariogenerator import builda_client_import
from cityscenariogenerator.plots.building_map_interactive import MARKER_COLORS
import cityscenariogenerator.plots.unmapped_building_map as buil_map
from cityscenariogenerator.poi_type_mapping import (
    AlkisMapper,
    BuildingWithLocationType,
    LocationType,
)
from cityscenariogenerator.overpass_import import overpass_query
from cityscenariogenerator.scenario_params import ScenarioParams

#: directory with input OSM data from overpass
DATA_DIR = Path("data")
OVERPASS_DATA_DIR = DATA_DIR / "osm_nonres_buildings"


class DFColumns:
    BUILDA_ID = "id_builda"
    OSM_ID = "id"
    DISTANCE = "distance"


@dataclass(frozen=True)
class LocReplacement:
    """
    Stores a replacement of the location type of a single building, e.g., when adding
    data from OpenStreetMap to BUILDA buildings.
    """

    old: LocationType | None
    new: LocationType

    def is_identical(self) -> bool:
        """
        Whether the old and new location types are identical, meaning that the OSM
        data matches the location type determined from BUILDA data (ALKIS). Also returns
        True if multiple possible location types where determined from BUILDA, and the one
        determined from OSM is one of them.

        :return: True if identical, otherwise False
        """
        if self.old is None:
            return False
        if self.old.non_work_locations == self.new.non_work_locations:
            return True
        if len(self.new.non_work_locations) == 1:
            loc = next(iter(self.new.non_work_locations))
            return loc in self.old.non_work_locations
        return False

    def is_added(self) -> bool:
        """
        Whether the building was assigned a new location type when it did not
        have any type before.

        :return: True if the building did not have a location type before, otherwise False
        """
        return not self.old or not self.old.non_work_locations

    def is_replaced(self) -> bool:
        """
        Whether the building was assigned a new, different location type.

        :return: True if the new location type is different from the original one, otherwise False
        """
        return not self.is_identical() and not self.is_added()

    def __str__(self):
        old_str = ", ".join(self.old.non_work_locations) if self.old else ""
        new_str = ", ".join(self.new.non_work_locations)
        return f"{old_str} -> {new_str}"


def load_overpass_data(params: ScenarioParams) -> gpd.GeoDataFrame:
    """
    Loads an overpass data file for a city from the overpass data directory.

    :param params: the parameters for the scenario to get the OSM file path
    :return: the GeoDataFrame with the data
    """
    filepath = params.osm_input_path()
    overpass_df = gpd.read_file(filepath)
    return overpass_df


def load_location_work_mapping() -> dict[str, list[str]]:
    """
    Load the mapping of LPG non-work location types to work location types from a file.
    This mapping can be used to determine which type of employment can be carried out in
    a non-residential building, based on its non-work location.

    :return: the mapping as a dictionary
    """
    mapping_file = DATA_DIR / "location_work_mapping.json"
    with open(mapping_file, "r", encoding="utf8") as f:
        return json.load(f)


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
        joined_df[DFColumns.OSM_ID]
        + " - "
        + joined_df[DFColumns.BUILDA_ID]
        + "\n"
        + joined_df["amenity"]
        + "\n"
        + joined_df[DFColumns.DISTANCE].round(1).astype(str)
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
    filtered = df.sort_values(by=DFColumns.DISTANCE).drop_duplicates(
        subset=[DFColumns.BUILDA_ID], keep="first"
    )
    logging.info(f"Removed {len(df) - len(filtered)} duplicate matches")
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


def get_nonwork_location_for_node(mappings: dict[str, dict], row: pd.Series) -> str:
    for key, mapping in mappings.items():
        # check if the key for this mapping (e.g. 'amenity') is given for this node
        if val := row.get(key):
            # check if the value for the key has a mapping entry
            if loc := mapping.get(val):
                return loc
        # otherwhise continue trying with the remaining mappings
    # If no mapping has an entry, a suitable location cannot be determined for this node.
    # This should not happen, as only relevant nodes are queried from overpass.
    raise Exception(f"Could not match an OSM node:\n{row}")


def map_osm_node(
    mappings: dict[str, dict], row: pd.Series, work_mapping: dict[str, list[str]]
) -> LocationType:
    nonwork_location = get_nonwork_location_for_node(mappings, row)
    work_locations = set(work_mapping[nonwork_location])
    return LocationType({nonwork_location}, work_locations)


def map_osm_nodes_to_locations(
    data: gpd.GeoDataFrame, keys: list[str]
) -> dict[str, LocationType]:
    # load all mappings to use, one per OSM key
    mappings = {key: overpass_query.load_osm_mapping(key) for key in keys}
    work_mapping = load_location_work_mapping()
    osm_node_location_types = {
        row[DFColumns.OSM_ID]: map_osm_node(mappings, row, work_mapping)
        for _, row in data.iterrows()
    }
    return osm_node_location_types


def add_osm_location_types(
    params: ScenarioParams, buildings: dict[str, BuildingWithLocationType]
) -> set[str]:
    overpass_df = load_overpass_data(params)
    # convert BUILDA objects to GeoDataFrame
    builda_df = builda_to_geodf(b.building for b in buildings.values())

    # convert to Web Mercator projection to get correct distances
    overpass_df.to_crs("EPSG:3857", inplace=True)
    builda_df.to_crs("EPSG:3857", inplace=True)

    # spatial join
    distance = 20
    joined_df = gpd.sjoin_nearest(
        overpass_df,
        builda_df,
        distance_col=DFColumns.DISTANCE,
        exclusive=False,
        max_distance=distance,
    )
    joined_df = remove_duplicate_matches(joined_df)
    logtext = f"Matched {len(joined_df)} of {len(overpass_df)} OSM nodes to "
    logtext += f"non-residential buildings. Max distance: {distance} m."
    logging.info(logtext)

    # determine the LPG location type for each OSM node ID
    keys = overpass_query.get_osm_keys_for_mapping()
    osm_node_locations = map_osm_nodes_to_locations(overpass_df, keys)

    # create a directory for statistics on the OSM mapping
    directory = params.result_directory / "poi_mapping"
    directory.mkdir(parents=True, exist_ok=True)

    # write statistics on ignored OSM nodes
    ignored_df = overpass_df[
        ~overpass_df[DFColumns.OSM_ID].isin(joined_df[DFColumns.OSM_ID])
    ]
    write_osm_ignored_nodes_statistics(ignored_df, osm_node_locations, directory)

    # assign OSM locations to BUILDA buildings
    changed = assign_osm_location_type_to_buildings(
        buildings, joined_df, osm_node_locations, directory
    )
    return changed


def write_osm_ignored_nodes_statistics(
    ignored_df: gpd.GeoDataFrame,
    osm_node_locations: dict[str, LocationType],
    result_dir: Path,
) -> None:
    """
    Writes a json file with statistics on the OSM nodes that were ignored
    because they could not be matched to any building in BUILDA due to the
    maximum distance or another node that was closer.

    :param ignored_df: the GeoDataFrame with the ignored nodes
    :param result_dir: the directory to store the result file in
    """
    ignored_loc_types = [
        next(iter(osm_node_locations[id].non_work_locations))
        for id in ignored_df[DFColumns.OSM_ID]
    ]
    counter = Counter(ignored_loc_types)
    ignored_counts = dict(counter.most_common())
    ignored_counts["total"] = counter.total()
    with open(result_dir / "ignored_osm_node_types.json", "w", encoding="utf8") as f:
        json.dump(ignored_counts, f, indent=4)


def assign_osm_location_type_to_buildings(
    buildings: dict[str, BuildingWithLocationType],
    joined_df: gpd.GeoDataFrame,
    osm_node_locations: dict[str, LocationType],
    result_dir: Path,
) -> set[str]:
    assignments: list[LocReplacement] = []
    changed = set()
    for _, row in joined_df.iterrows():
        # get the matching location type for the OSM node
        osm_loc_type = osm_node_locations[row[DFColumns.OSM_ID]]
        matched_building = buildings[row[DFColumns.BUILDA_ID]]
        # collect which location types were changed due to the assignment
        replacement = LocReplacement(matched_building.location_type, osm_loc_type)
        assignments.append(replacement)
        if not replacement.is_identical():
            changed.add(matched_building.building.id)

        # assign this location type to the corresponding BUILDA building
        matched_building.location_type = osm_loc_type

    log_changes_in_location_type(assignments)

    # for all changed buildings, calculat statistics on building types and new locations
    changed_buildings = {k: v for k, v in buildings.items() if k in changed}
    create_building_category_location_statistics(changed_buildings, result_dir)
    return changed


def log_changes_in_location_type(assignments: list[LocReplacement]):
    """
    Logs an overview on how many buildings of each type were assigned
    a new location type, and whether the new type is identical to the old one.

    :param assignments: list of location type replacements
    """
    identical = [str(x) for x in assignments if x.is_identical()]
    added = [str(x) for x in assignments if x.is_added()]
    replaced = [str(x) for x in assignments if x.is_replaced()]
    c_ident = Counter(identical)
    c_added = Counter(added)
    c_repl = Counter(replaced)
    logging.info(
        f"Identical location types ({c_ident.total()}): {c_ident.most_common()}"
    )
    logging.info(f"Added location types ({c_added.total()}): {c_added.most_common()}")
    logging.info(f"Changed location types ({c_repl.total()}): {c_repl.most_common()}")


def create_building_category_location_statistics(
    buildings: dict[str, BuildingWithLocationType],
    result_dir: Path,
) -> None:
    """
    Checks how many buildings of each category were assigned the same location type,
    and creates a text file with the results.

    :param buildings: the buildings to examine
    :param result_dir: the directory to store the result file in
    """
    # group all buildings by their new non-work location type
    buildings_by_loc = defaultdict(list)
    for b in buildings.values():
        locs = b.location_type.non_work_locations
        assert len(locs) == 1, "When replacing locations, only one should be given"
        buildings_by_loc[next(iter(locs))].append(b.building)

    # check how many buildings of each category were assigned the same location type
    poi_mapper = AlkisMapper()
    text = "The following shows all BUILDA building categories that were assigned "
    text += "a new location type using OpenStreetMap data.\n===\n"
    for location, group in buildings_by_loc.items():
        pairs = [poi_mapper.get_orig_category(b) for b in group]
        c = Counter(pairs)
        text += f"\nBuildings with new location type {location}: {len(group)}\n"
        text += "\n".join(f"{count:3d}: {key}" for key, count in c.most_common())

    # write the results to a text file
    with open(
        result_dir / "categories_with_new_osm_tag.txt", "w", encoding="utf8"
    ) as f:
        f.write(text)


def show_osm_builda_join_on_map():
    # load overpass building data
    overpass_df = gpd.read_file("data/custom_input/Aachen/osm_nonres_nodes.geojson")

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
    builda_df["popup"] = builda_df[DFColumns.BUILDA_ID] + "\n" + builda_df["category"]
    overpass_df["popup"] = overpass_df[DFColumns.OSM_ID] + "\n" + overpass_df["amenity"]

    # spatial join
    joined_df = gpd.sjoin_nearest(
        overpass_df,
        builda_df,
        distance_col=DFColumns.DISTANCE,
        exclusive=False,
        max_distance=20,
    )
    adapt_joined_df(joined_df, geometry_4326)

    joined_df = remove_duplicate_matches(joined_df)

    print(
        f"Builda: {len(builda_df)}, Overpass: {len(overpass_df)}, Joined: {len(joined_df)}, "
    )

    plot_map([builda_df, overpass_df, joined_df], "health_map.html", geometry_4326)


if __name__ == "__main__":
    show_osm_builda_join_on_map()
