"""Imports buildings from BUILDA"""

import logging
import os
from dotenv import load_dotenv
from builda_client.client import (
    BuildaClient,
    NonResidentialBuildingWithSourceDto,
)
from builda_client.dev_client import BuildaDevClient, Phase, ResidentialBuilding


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


def get_residential_buildings(search_args: dict) -> list[ResidentialBuilding]:
    # load credentials for the BuildaDevClient
    load_dotenv()
    # init the Builda API client
    client = BuildaDevClient(
        proxy=False,
        username=os.getenv("username"),
        password=os.getenv("password"),
        phase=Phase.PRODUCTION,
        version="v8_20240916",
    )

    res_buildings = client.get_residential_buildings(**search_args)
    logging.info(f"Residential buildings in {search_args}: {len(res_buildings)}")
    return res_buildings
