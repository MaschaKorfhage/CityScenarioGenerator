"""
Loads OpenStreetMap (OSM) node data from overpass turbo and does a spatial join
with BUILDA buildings to add better location types to non-residential buildings.
"""

from collections import Counter, defaultdict
import copy
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Iterable
import geopandas as gpd  # type: ignore

from builda_client.dev_client import Building, NonResidentialBuilding  # type: ignore
import pandas as pd
from shapely import Point  # type: ignore
from pylpg import lpgdata

from cityscenariogenerator.household_data import BuildingData
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

    CATEGORY = "category"


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


def builda_to_geodf(buildings: Iterable[Building | BuildingData]) -> gpd.GeoDataFrame:
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


def pois_to_geodf(pois: dict[str, lpgdata.PointOfInterestData]) -> gpd.GeoDataFrame:
    geometry = [
        Point(poi.Coordinates.Longitude, poi.Coordinates.Latitude)  # type: ignore
        for poi in pois.values()
    ]
    data = {
        DFColumns.BUILDA_ID: list(pois.keys()),
        DFColumns.CATEGORY: [p.LocationType for p in pois.values()],
    }
    df = gpd.GeoDataFrame(data, geometry=geometry)
    df.set_crs("EPSG:4326", inplace=True)
    return df


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
    logging.info(f"Removed {len(df) - len(filtered)} duplicate OSM matches")
    return filtered


def filter_matched(df: pd.DataFrame, df2: pd.DataFrame, col: str = DFColumns.BUILDA_ID):
    """
    Extracts only those entries from the first dataframe whose ID is also
    contained in the second dataframe. Uses the specified columns as ID.

    :param df: the dataframe to extract rows from
    :param df2: the dataframe to check which rows shall be kept
    :param col: the ID column to check if a row is contained
    :return: the entries from df that are also present in df2
    """
    assert col in df.columns and col in df2.columns, f"Invalid column: {col}"
    return df[df[col].isin(df2[col])]


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
    """
    Loads the OSM mapping for each specified key and then determines
    the matching LPG LocationType for each entry in the dataframe.
    Uses the first key of the specified list with a defined mapping.

    :param data: the data to map
    :param keys: the OSM keys to use for mapping, with descending priority
    :return: a dict mapping each dataframe entry ID to its LocationType
    """
    # load all mappings to use, one per OSM key
    mappings = {key: overpass_query.load_osm_mapping(key) for key in keys}
    work_mapping = load_location_work_mapping()
    osm_node_location_types = {
        row[DFColumns.OSM_ID]: map_osm_node(mappings, row, work_mapping)
        for _, row in data.iterrows()
    }
    return osm_node_location_types


def add_osm_location_types(
    params: ScenarioParams,
    nonres_buildings: dict[str, BuildingWithLocationType],
    res_buildings: list[BuildingData],
) -> set[str]:
    overpass_df = load_overpass_data(params)
    # convert BUILDA objects to GeoDataFrame
    builda_nonres_df = builda_to_geodf(b.building for b in nonres_buildings.values())
    builda_res_df = builda_to_geodf(res_buildings)
    builda_df = concat_builda_dfs(builda_nonres_df, builda_res_df)

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
    # joined_df = remove_duplicate_matches(joined_df)
    logtext = f"Matched {len(joined_df)} of {len(overpass_df)} OSM nodes to "
    logtext += f"BUILDA buildings. Max distance: {distance} m."
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
    # TODO: create new building objects for these POIs to use them as well?

    # assign OSM locations to BUILDA buildings
    res_building_dict = {b.id: b for b in res_buildings}
    changed = assign_osm_location_type_to_buildings(
        nonres_buildings, res_building_dict, joined_df, osm_node_locations, directory
    )
    return changed


def concat_builda_dfs(df1, df2):
    """
    Combines two BUILDA GeoDataFrames, e.g. residential and nonresidential
    buildings. Uses the BUILDA_ID column to check for duplicates to only
    include them once.

    :param df1: first dataframe
    :param df2: second dataframe
    :return: combined dataframe with all entries
    """
    df2 = df2[~df2[DFColumns.BUILDA_ID].isin(df1[DFColumns.BUILDA_ID])]
    return pd.concat([df1, df2], axis="index")


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
    nonres_buildings: dict[str, BuildingWithLocationType],
    res_buildings: dict[str, BuildingData],
    joined_df: gpd.GeoDataFrame,
    osm_node_locations: dict[str, LocationType],
    result_dir: Path,
) -> set[str]:
    assignments: list[LocReplacement] = []
    changed = set()
    handled: dict[str, int] = {}
    new_buildings: dict[str, BuildingWithLocationType] = {}
    for _, row in joined_df.iterrows():
        # get the matching location type for the OSM node
        osm_loc_type = osm_node_locations[row[DFColumns.OSM_ID]]
        original_id = row[DFColumns.BUILDA_ID]
        if original_id in nonres_buildings:
            # assign the corresponding location type to the non-residential building
            matched_building = nonres_buildings[original_id]
        else:
            # matched to a residential building -> create a non-residential building out of it
            matched_building = res_to_nonres_building(res_buildings[original_id])

        # check if the building has been matched before
        if original_id in handled:
            # building has already been assigned to another OSM node
            if original_id in nonres_buildings:
                # non-residential buildings need to be copied to get independent objects
                matched_building = copy.deepcopy(matched_building)
            # assign a new unique ID
            index = handled[original_id] + 1
            matched_building.building.id += f"_copy_{index}"
            handled[original_id] = index
        else:
            # mark the building as already assigned to an OSM node
            handled[original_id] = 0

        if matched_building.building.id not in nonres_buildings:
            new_buildings[matched_building.building.id] = matched_building

        # collect which location types were changed due to the assignment
        replacement = LocReplacement(matched_building.location_type, osm_loc_type)
        assignments.append(replacement)
        if not replacement.is_identical():
            changed.add(matched_building.building.id)

        # assign this location type to the corresponding BUILDA building
        matched_building.location_type = osm_loc_type

    log_changes_in_location_type(assignments)

    # add the created building copies
    nonres_buildings.update(new_buildings)

    # for all changed buildings, calculat statistics on building types and new locations
    changed_buildings = {k: v for k, v in nonres_buildings.items() if k in changed}
    create_building_category_location_statistics(changed_buildings, result_dir)
    return changed


def res_to_nonres_building(res_build: BuildingData):
    """
    Create a non-residential building object from a residential BUILDA building.
    This can be used when a building falsely categorized as purely residential
    should be used for non-residential purposes as well.

    :param res_build: the residential building
    :return: a newly created non-residential building object with matching properties
    """
    # TODO: fill in the correct values from the residential building BUILDA object
    building = NonResidentialBuilding(
        res_build.id + "_nonres",
        res_build.coordinates,
        {},
        -1,
        -1,
        -1,
        -1,
        "",
        "",
        None,
        "",
        {},
        -1,
    )
    return BuildingWithLocationType(building, LocationType())


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
