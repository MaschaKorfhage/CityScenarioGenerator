"""Generates a city scenario for the LPG from BUILDA data"""

from pathlib import Path
import random
import sys


from builda_client.client import NonResidentialBuildingWithSourceDto

import builda_file_import.sampling_with_builda_data.sampling_buildings_from_builda as builda_file_sampler
import builda_file_import.statistical_sampling.sampling_lpg_households as lpg_household_sampler
import builda_client_import
from household_data import BuildingData
import create_lpg_configs


def import_buildings_from_builda_file():
    # init random
    seed = random.randrange(sys.maxsize)
    random.seed(seed)
    print(f"Using RNG seed {seed}")

    # get building data from builda csv file
    (
        building_ids,
        tabula_building_codes,
        conditioned_floor_areas_in_m2,
        number_of_dwellings,
        norm_heating_load_in_kw,
        postal_code,
        pv_capacities_in_kw,
        pv_generations_in_kwh,
        commodities,
        supply_levels,
        building_data_list,
    ) = builda_file_sampler.get_buildings_from_builda(number_of_random_samples=2)

    # get lpg profiles based on builda data
    building_objects = lpg_household_sampler.get_lpg_households_based_on_builda_data(
        building_data_list
    )
    # print(building_ids)
    # print(building_objects)
    buildings = dict(zip(building_ids, building_objects))
    return buildings


def create_configs_from_buildings(
    path: Path,
    res_buildings: dict[str, BuildingData],
    nonres_buildings: list[NonResidentialBuildingWithSourceDto],
):
    config_creator = create_lpg_configs.LPGConfigCreator()
    # create a POI config for each nonresidential building
    for nonres_building in nonres_buildings:
        config_creator.add_poi(nonres_building)

    # TODO: include coordinates in house
    # TODO: create POI preferences (nearest ones)

    # create an LPG config for each building
    for id, building in res_buildings.items():
        config_creator.add_lpg_house(id, building)
    config_creator.create_config_files(path)


if __name__ == "__main__":
    builda_query = {"city": "Heimbach", "postcode": "52396", "street": "Bachstraße"}
    # collect non-residential buildings
    nonres_buildings = builda_client_import.get_nonresidential_buildings(builda_query)
    # collect residential buildings
    res_buildings = import_buildings_from_builda_file()

    create_configs_from_buildings(
        Path("./LPG_House_configs"), res_buildings, nonres_buildings
    )
