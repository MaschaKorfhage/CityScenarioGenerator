"""Script for testing how to work with the Builda client"""

from collections import Counter
from builda_client.client import BuildaClient, ResidentialBuildingWithSourceDto
import pandas as pd
import pprint

# init the Builda API client
client = BuildaClient()


def get_nonresidential_buildings(search_args: dict):
    nonres_building_data = client.get_non_residential_buildings(**search_args)
    nonres_buildings = nonres_building_data.buildings
    print(
        f"Non-residential buildings in {search_args['city']}: {len(nonres_buildings)}"
    )
    c = Counter(tuple(b.use.value.values()) for b in nonres_buildings)
    print(c)


def get_residential_buildings(search_args: dict):
    res_building_data = client.get_residential_buildings(**search_args)
    res_buildings = res_building_data.buildings
    print(f"Residential buildings in {search_args['city']}: {len(res_buildings)}")
    for building in res_buildings:
        get_building(building)
        break


def get_building(building: ResidentialBuildingWithSourceDto):
    pprint.pprint(building)


search_args = {"city": "Heimbach", "postcode": "52396", "street": "Bachstraße"}
get_residential_buildings(search_args)
# get_nonresidential_buildings(search_args)
