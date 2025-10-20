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
from typing import TypeVar
import geopandas as gpd  # type: ignore

from builda_client.dev_model import (
    NonResidentialBuilding,
    Address,
    Coordinates,
)  # type: ignore
import pandas as pd

from cityscenariogenerator import utils
from cityscenariogenerator import geoutils
from cityscenariogenerator.geoutils import GeoDFColumns
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

#: type annotation for DataFrame or GeoDataFrame
DF = TypeVar("DF", pd.DataFrame, gpd.GeoDataFrame)


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


def remove_duplicate_matches(df: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    After a spatial join, removes duplicate matches to the same point of
    the left dataframe. Only keeps the closest match of the right dataframe.
    The result is a 1-to-1 matching between points from left and right.

    :param df: dataframe with result of spatial join
    :return: filtered dataframe
    """
    # filter duplicate matches
    filtered = df.sort_values(by=GeoDFColumns.DISTANCE).drop_duplicates(
        subset=[GeoDFColumns.BUILDA_ID], keep="first"
    )
    logging.info(f"Removed {len(df) - len(filtered)} duplicate OSM matches")
    return filtered


def filter_matched(
    df: pd.DataFrame, df2: pd.DataFrame, col: str = GeoDFColumns.BUILDA_ID
):
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


def filter_not_matched(
    df1: DF, df2: DF, col1: str = GeoDFColumns.BUILDA_ID, col2: str = ""
) -> DF:
    """
    Extracts all entries from the first dataframe whose ID is not
    contained in the second dataframe. Uses the specified columns as ID.

    :param df: the dataframe to extract rows from
    :param df2: the dataframe to check which rows shall be kept
    :param col: the ID column in the first to check if a row is contained
    :param col2: the corresponding ID column in the second dataframe; if not given,
                 col1 is used for both dataframes
    :return: the entries from df that are missing in df2
    """
    if not col2:
        col2 = col1
    assert col1 in df1.columns, f"Invalid column: {col1}"
    assert col2 in df2.columns, f"Invalid column: {col2}"
    return df1[~df1[col1].isin(df2[col2])]


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
        row[GeoDFColumns.EXT_ID]: map_osm_node(mappings, row, work_mapping)
        for _, row in data.iterrows()
    }
    return osm_node_location_types


def map_custom_pois_to_locations(
    custom_poi_dfs: list[gpd.GeoDataFrame], location: str = ""
):
    """
    Creates a dict mapping each custom POI ID to its location type.
    For the location type the category of the POI is used, but the
    location parameter can be used to overwrite it.

    :param custom_poi_dfs: list of all custom POI dataframes
    :param location: LPG location name to overwrite original categories,  defaults to ""
    :return: dict mapping POI IDs to their location type
    """
    custom_poi_locations = {}
    work_mapping = load_location_work_mapping()
    for data in custom_poi_dfs:
        for _, row in data.iterrows():
            nonwork_location = location or row[GeoDFColumns.CATEGORY]
            custom_poi_locations[row[GeoDFColumns.EXT_ID]] = LocationType(
                {nonwork_location}, set(work_mapping[nonwork_location])
            )
    return custom_poi_locations


def concat_builda_dfs(df1, df2) -> gpd.GeoDataFrame:
    """
    Combines two BUILDA GeoDataFrames, e.g. residential and nonresidential
    buildings. Uses the BUILDA_ID column to check for duplicates to only
    include them once.

    :param df1: first dataframe
    :param df2: second dataframe
    :return: combined dataframe with all entries
    """
    df2 = df2[~df2[GeoDFColumns.BUILDA_ID].isin(df1[GeoDFColumns.BUILDA_ID])]
    return pd.concat([df1, df2], axis="index")  # type: ignore


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
        for id in ignored_df[GeoDFColumns.EXT_ID]
    ]
    counter = Counter(ignored_loc_types)
    ignored_counts = dict(counter.most_common())
    ignored_counts["total"] = counter.total()
    with open(result_dir / "generated_poi_buildings.json", "w", encoding="utf8") as f:
        json.dump(ignored_counts, f, indent=4)


def assign_poi_location_type_to_buildings(
    nonres_buildings: dict[str, BuildingWithLocationType],
    res_buildings: dict[str, BuildingData],
    joined_df: gpd.GeoDataFrame,
    osm_node_locations: dict[str, LocationType],
    result_dir: Path,
) -> set[str]:
    # collect which location types were replaced with which new ones based on OSM
    assignments: list[LocReplacement] = []
    # store all buildings for which OSM provided a new or different type
    changed = set()
    # store how many copies of each building were already already created
    copy_counts: dict[str, int] = {}
    # store newly created non-residential building objects, with their modified ID
    new_buildings: dict[str, BuildingWithLocationType] = {}
    created_from_res = 0
    # handle each OSM node individually
    for _, row in joined_df.iterrows():
        # get the matching location type for the OSM node
        osm_loc_type = osm_node_locations[row[GeoDFColumns.EXT_ID]]
        original_id = row[GeoDFColumns.BUILDA_ID]
        if original_id in nonres_buildings:
            # assign the corresponding location type to the non-residential building
            matched_building = nonres_buildings[original_id]
        else:
            # matched to a residential building -> create a non-residential building out of it
            matched_building = res_to_nonres_building(res_buildings[original_id])
            created_from_res += 1

        # check if the building has been matched before
        if original_id in copy_counts:
            # building has already been assigned to another OSM node
            if original_id in nonres_buildings:
                # non-residential buildings need to be copied to get independent objects
                matched_building = copy.deepcopy(matched_building)
                # TODO: don't add the same work locations for copied buildings
                # matched_building.location_type.work_locations = set() # this is overwritten below
            # assign a new unique ID
            index = copy_counts[original_id] + 1
            matched_building.building.id += f"_copy_{index}"
            copy_counts[original_id] = index
        else:
            # this building was assigned to an OSM node for the first time
            copy_counts[original_id] = 0

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

    # write log entries about the newly created building objects
    logging.info(f"Matched {created_from_res} POIs to residential buildings.")
    logging.info(
        f"Created {len(new_buildings)} new non-residential building objects from residential buildings."
    )
    num_copies = len(joined_df) - len(copy_counts)
    logging.info(f"Created in total {num_copies} copies of building objects.")

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
        Address("", "", "", ""),
        -1,
        -1,
        -1,
        -1,
        "",
        "",
        None,
        "",
        {},  # type: ignore
        -1,
    )
    return BuildingWithLocationType(building, LocationType())


def create_new_poi_buildings(
    unmatched_df: gpd.GeoDataFrame, poi_locations: dict[str, LocationType]
) -> dict[str, BuildingWithLocationType]:
    """
    Creates new non-residential building objects for all unmatched POIs.
    The buildings are created with the same coordinates as the POI, but with
    a new ID and the location type of the POI.

    :param unmatched_df: the dataframe with unmatched POIs
    :return: a dictionary with the new building objects
    """
    # convert to the correct CRS used in BUILDA
    unmatched_df.to_crs("EPSG:4326", inplace=True)
    new_buildings = {}
    # for every unmatched POI, create a new building object
    for _, row in unmatched_df.iterrows():
        id = row[GeoDFColumns.EXT_ID]
        building_id = f"Generated_{utils.slugify(id)}"
        building = NonResidentialBuilding(
            building_id,
            Coordinates(row.geometry.y, row.geometry.x),
            Address("", "", "", ""),
            -1,
            -1,
            -1,
            -1,
            "",
            "",
            None,
            "",
            {},  # type: ignore
            -1,
        )
        new_buildings[building_id] = BuildingWithLocationType(
            building, poi_locations[id]
        )
    logging.info(
        f"Created {len(new_buildings)} new non-residential buildings for unmatched POIs."
    )
    return new_buildings


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
    text += "a new location type using external data.\n===\n"
    for location, group in buildings_by_loc.items():
        pairs = [poi_mapper.get_orig_category(b) for b in group]
        c = Counter(pairs)
        text += f"\nBuildings with new location type {location}: {len(group)}\n"
        text += "\n".join(f"{count:3d}: {key}" for key, count in c.most_common())

    # write the results to a text file
    with open(
        result_dir / "buildings_with_new_location_types.txt", "w", encoding="utf8"
    ) as f:
        f.write(text)


def combine_poi_dfs(
    poi_dfs: list[gpd.GeoDataFrame], distance: float
) -> gpd.GeoDataFrame:
    combined_df: gpd.GeoDataFrame = poi_dfs[0]
    for df in poi_dfs[1:]:
        # join with the next dataset to find duplicates
        duplicates = gpd.sjoin_nearest(
            combined_df,
            df,
            distance_col=GeoDFColumns.DISTANCE,
            exclusive=False,
            max_distance=distance,
        )
        # determine new POIs that are not already contained in the combined dataframe
        not_matched = filter_not_matched(
            df, duplicates, GeoDFColumns.EXT_ID, f"{GeoDFColumns.EXT_ID}_right"
        )
        logging.info(f"Found {len(not_matched)} new POIs in dataframe")
        # add the new POIs to the combined dataframe
        combined_df = pd.concat([combined_df, not_matched], axis="index")  # type: ignore
    assert combined_df[GeoDFColumns.EXT_ID].is_unique, "A POI ID was not unique"
    logging.info(f"Collected {len(combined_df)} POIs from {len(poi_dfs)} dataframes.")
    return combined_df


def add_osm_location_types(
    params: ScenarioParams,
    nonres_buildings: dict[str, BuildingWithLocationType],
    res_buildings: list[BuildingData],
) -> set[str]:
    if not params.osm_input_path().is_file():
        logging.info("No OSM data file found, skipping OSM mapping.")
        return set()

    # load additional POI data from OSM and address books
    overpass_df = load_overpass_data(params)

    # for now, only consider Doctors Offices here
    custom_poi_type = "Doctors Office"
    custom_poi_dir = params.specific_poi_sources_dir() / custom_poi_type
    assert custom_poi_dir.is_dir(), f"Missing additional POI data: {custom_poi_dir}"
    custom_poi_dfs = [
        geoutils.load_custom_poi_geodf(f) for f in custom_poi_dir.iterdir()
    ]
    poi_dfs = [overpass_df] + custom_poi_dfs

    # determine the LPG location type for each OSM node and custom POI ID
    keys = overpass_query.get_osm_keys_for_mapping()
    osm_node_locations = map_osm_nodes_to_locations(overpass_df, keys)
    custom_poi_locations = map_custom_pois_to_locations(custom_poi_dfs, custom_poi_type)
    poi_locations = osm_node_locations | custom_poi_locations

    # convert BUILDA objects to GeoDataFrame
    builda_nonres_df = geoutils.builda_to_geodf(
        b.building for b in nonres_buildings.values()
    )
    builda_res_df = geoutils.builda_to_geodf(res_buildings)
    builda_df = concat_builda_dfs(builda_nonres_df, builda_res_df)

    # convert to Web Mercator projection to get correct distances
    for df in poi_dfs:
        df.to_crs("EPSG:3857", inplace=True)
    builda_df.to_crs("EPSG:3857", inplace=True)

    # the maximum distance for all spatial joins
    distance = 30

    # first join all the additional POI source data
    combined_df = combine_poi_dfs(poi_dfs, distance)

    # then join the combined POI data to the BUILDA data
    joined_df = gpd.sjoin_nearest(
        combined_df,
        builda_df,
        distance_col=GeoDFColumns.DISTANCE,
        exclusive=False,
        max_distance=distance,
    )
    assert joined_df[GeoDFColumns.EXT_ID].is_unique, (
        "Matched a node to multiple buildings"
    )
    # joined_df = remove_duplicate_matches(joined_df)
    logtext = f"Matched {len(joined_df)} of {len(combined_df)} OSM nodes to "
    logtext += f"BUILDA buildings. Max distance: {distance} m."
    logging.info(logtext)

    # create a directory for statistics on the OSM mapping
    directory = params.result_directory / "statistics/poi_mapping"
    directory.mkdir(parents=True, exist_ok=True)

    # assign OSM locations to BUILDA buildings
    res_building_dict = {b.id: b for b in res_buildings}
    changed = assign_poi_location_type_to_buildings(
        nonres_buildings, res_building_dict, joined_df, poi_locations, directory
    )

    # write statistics on unmatched OSM nodes and create additional buildings for them
    unmatched_df = filter_not_matched(combined_df, joined_df, GeoDFColumns.EXT_ID)
    write_osm_ignored_nodes_statistics(unmatched_df, poi_locations, directory)
    new_buildings = create_new_poi_buildings(unmatched_df, poi_locations)
    nonres_buildings.update(new_buildings)
    return changed
