import logging

import geopandas as gpd
from builda_client.dev_model import NonResidentialBuilding, Coordinates, Address  # type: ignore

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

    # optionally load additional custom buildings and add them
    custom_nonres_buildings = load_custom_nonres_buildings(params)
    buildings_by_id.update(custom_nonres_buildings)

    # use OSM data to get more accurate building types
    osm_data_join.add_osm_location_types(params, buildings_by_id, residential_buildings)

    return buildings_by_id
