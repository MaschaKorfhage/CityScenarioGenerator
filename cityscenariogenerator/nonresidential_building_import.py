import logging
import random

import geopandas as gpd
from builda_client.dev_model import NonResidentialBuilding, Coordinates, Address
from shapely import Point  # type: ignore

from cityscenariogenerator.scenario_params import ScenarioParams
from cityscenariogenerator import builda_client_import
from cityscenariogenerator.household_data import BuildingData
from cityscenariogenerator.overpass_import import osm_data_join
from cityscenariogenerator.poi_type_mapping import (
    AlkisMapper,
    BuildingWithLocationType,
    LocationType,
)


def load_custom_nonres_buildings(
    params: ScenarioParams,
) -> dict[str, BuildingWithLocationType]:
    """Parses additional custom non-residential buildings from a geojson file.

    :param params: the simulation parameter object
    :raises Exception: if the file had an invalid format
    :return: the parsed buildings, if any
    """
    # check if a file with additional custom buildings exists
    path = params.custom_nonresidentials_path()
    if not path.is_file():
        logging.info("No custom non-residential buildings specified")
        return {}

    work_mapping = osm_data_join.load_location_work_mapping()

    buildings = {}
    building_info = gpd.read_file(path).set_crs(4326)
    for i, row in building_info.iterrows():
        src_id = row.get("id")
        id = f"CustomNonres_{src_id}{i}"
        poi_type: str = row["poi"]
        try:
            point = row["geometry"]
            building = NonResidentialBuilding(
                id,
                Coordinates(point.y, point.x),
                Address("", "", "", ""),
                -1,
                -1,
                -1,
                -1,
                "",
                "",
                None,
                "",
                "",
                -1,
            )
            # raise Exception(f"Unsupported POI type in custom building: {poi_type}")
            # check if there is a matching working location for this POI type
            worklocations = set(work_mapping.get(poi_type, []))
            buildings[id] = BuildingWithLocationType(
                building, LocationType({poi_type}, worklocations)
            )
        except ValueError as e:
            raise Exception(
                f"Could not parse custom non-residential building {id} from file {path}: {e}"
            )
    logging.info(f"Parsed {len(buildings)} custom residential buildings from {path}")
    return buildings


def nonresbuilding_dict_to_geodf(
    buildings: dict[str, BuildingWithLocationType],
) -> gpd.GeoDataFrame:
    """Creates a GeoDataFrame out of a list of nonresidential buildings. The
    GeoDataFrame contains the building IDs, coordinates, and the POI type.

    :param buildings: the list of building raw data objects
    :return: the GeoDataFrame
    """
    records = []
    for id, b in buildings.items():
        records.append(
            {
                "id": id,
                "poi_type": None,  # TODO
                "geometry": Point(
                    b.building.coordinates.longitude, b.building.coordinates.latitude
                ),
            }
        )
    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    return gdf


def apply_custom_nonresidential_deletions(
    params: ScenarioParams, buildings: dict[str, BuildingWithLocationType]
) -> dict[str, BuildingWithLocationType]:
    """If a file with custom POI deletions is specified, applies
    the deletions.

    :param params: parameter object
    :param buildings: the full list of input buildings
    :return: the remaining buildings that were not deleted
    """
    path = params.custom_nonresidentials_deletions_path()
    if not path.is_file():
        logging.info("No custom non-residential deletions specified")
        return buildings

    building_gdf = nonresbuilding_dict_to_geodf(buildings)
    deletions = gpd.read_file(path).set_crs(4326)
    deleted = set()
    # handle each deletion area individually
    for i, entry in deletions.iterrows():
        area = entry["geometry"]
        poi_type = entry["poi"]
        buildings_to_delete = entry["n_pois"]

        # get all buildings in the affected area
        buildings_in_area = building_gdf.loc[building_gdf["geometry"].within(area)]
        if len(buildings_in_area) == 0:
            logging.info(f"No buildings in deletion area {i}; skipping")
            continue

        # filter all buildings that have the specified type
        mask_not_yet_deleted = buildings_in_area["id"].isin(deleted)
        mask_correct_poi_type = buildings_in_area["id"].apply(
            lambda id: poi_type in buildings[id].location_type.non_work_locations
        )
        mask_matching_buildings = mask_not_yet_deleted & mask_correct_poi_type
        matching_buildings = buildings_in_area.loc[mask_matching_buildings]

        new_deletions = []
        if len(matching_buildings) < buildings_to_delete:
            # fewer matching buildings than should be deleted -> delete all
            logging.warning(
                f"Only found {len(matching_buildings)} of {buildings_to_delete} households to delete in area {i}."
            )
            new_deletions = matching_buildings
        else:
            # randomly select buildings to delete
            seed = random.randrange(2**32)
            new_deletions = matching_buildings.sample(
                buildings_to_delete, random_state=seed
            )
        deleted.update(new_deletions["id"])

    # return the houses that were not deleted
    logging.info(
        f"Deleting {len(deleted)} of {len(buildings)} non-residential buildings"
    )
    return {id: b for id, b in buildings.items() if id not in deleted}


def import_nonresidential_buildings_from_builda(
    params: ScenarioParams,
    residential_buildings: list[BuildingData],
) -> dict[str, BuildingWithLocationType]:

    # collect non-residential buildings
    nonres_buildings = builda_client_import.get_nonresidential_buildings(
        params.builda_query
    )

    # determine suitable LPG location typs for each building
    poi_mapper = AlkisMapper()
    buildings = poi_mapper.get_locations_for_buildings(nonres_buildings)
    buildings_by_id = {b.building.id: b for b in buildings}

    if params.has_custom_adaptations():
        # optionally delete some buildings
        # buildings_by_id = apply_custom_nonresidential_deletions(params, buildings_by_id)

        # optionally load additional custom buildings and add them
        custom_nonres_buildings = load_custom_nonres_buildings(params)
        buildings_by_id.update(custom_nonres_buildings)

    # use OSM data to get more accurate building types
    osm_data_join.add_osm_location_types(params, buildings_by_id, residential_buildings)

    return buildings_by_id
