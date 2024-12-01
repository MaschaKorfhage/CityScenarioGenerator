"""Imports buildings from BUILDA"""

import logging
from builda_client.client import (
    BuildaClient,
    ResidentialBuildingWithSourceDto,
    NonResidentialBuildingWithSourceDto,
)
from pprint import pprint


def get_building_category(building: NonResidentialBuildingWithSourceDto):
    if building.use.value is None:
        return "No category"
    return tuple(building.use.value.values())


def get_nonresidential_buildings(
    search_args: dict,
) -> list[NonResidentialBuildingWithSourceDto]:
    # init the Builda API client
    client = BuildaClient()
    nonres_building_data = client.get_non_residential_buildings(**search_args)
    nonres_buildings = nonres_building_data.buildings
    logging.info(f"Non-residential buildings in {search_args}: {len(nonres_buildings)}")
    # c = Counter(get_building_category(b) for b in nonres_buildings)
    return nonres_buildings


def get_residential_buildings(search_args: dict):
    # init the Builda API client
    client = BuildaClient()
    res_building_data = client.get_residential_buildings(**search_args)
    res_buildings = res_building_data.buildings
    logging.info(
        f"Residential buildings in {search_args['city']}: {len(res_buildings)}"
    )
    for building in res_buildings:
        get_building(building)
        break


def get_building(building: ResidentialBuildingWithSourceDto):
    pprint(building)
