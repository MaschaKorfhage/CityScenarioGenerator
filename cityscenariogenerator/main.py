"""Generates a city scenario for the LPG from BUILDA data"""

# from cityscenariogenerator.builda_file_import.config_sample_generation import ConfigSamplingMode, SamplingModeEnum
from pathlib import Path
import random
import sys
import builda_file_import.sampling_with_builda_data.sampling_buildings_from_builda as builda_file_sampler
import builda_file_import.statistical_sampling.sampling_lpg_households as lpg_household_sampler
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
    print(building_ids)
    print(building_objects)

    # create an LPG config for each building
    config_creator = create_lpg_configs.LPGConfigCreator()
    buildings = dict(zip(building_ids, building_objects))
    for id, building in buildings.items():
        config_creator.add_lpg_house(id, building)
    config_creator.create_house_config_files(Path("./LPG_House_configs"))


if __name__ == "__main__":
    import_buildings_from_builda_file()
