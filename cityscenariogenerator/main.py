"""Generates a city scenario for the LPG from BUILDA data"""

import logging
from pathlib import Path
import random
import sys


from builda_client.client import NonResidentialBuildingWithSourceDto, Coordinates

import builda_file_import.sampling_with_builda_data.sampling_buildings_from_builda as builda_file_sampler
import builda_file_import.statistical_sampling.sampling_lpg_households as lpg_household_sampler
import builda_client_import
import utils
from household_data import BuildingData
import create_lpg_configs


def import_residential_buildings_from_builda_file(
    number_of_buildings: int,
) -> dict[str, BuildingData]:
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
    ) = builda_file_sampler.get_buildings_from_builda(
        number_of_random_samples=number_of_buildings
    )

    # get lpg profiles based on builda data
    buildings = lpg_household_sampler.get_lpg_households_based_on_builda_data(
        building_data_list
    )
    return buildings


def import_residential_buildings_from_builda(
    builda_query: dict,
) -> list[BuildingData]:
    # load residential buildings from BUILDA
    raw_buildings = builda_client_import.get_residential_buildings(builda_query)
    # parse the household data into data objects
    building_data_list = builda_file_sampler.convert_residential_buildings_from_builda(
        raw_buildings
    )

    # determine LPG households for each building
    buildings = lpg_household_sampler.get_lpg_households_based_on_builda_data(
        building_data_list
    )
    return buildings


def create_configs_from_buildings(
    path: Path,
    res_buildings: list[BuildingData],
    nonres_buildings: list[NonResidentialBuildingWithSourceDto],
):
    config_creator = create_lpg_configs.LPGConfigCreator()
    # create a POI config for each nonresidential building
    for nonres_building in nonres_buildings:
        config_creator.add_poi(nonres_building)

    # create an LPG house config for each residential building
    for building in res_buildings:
        config_creator.add_lpg_house(building)

    # TODO: workaround for missing POI types; define the custom
    #       POIs properly or remove them
    custom_poi_path = Path("data/custom_pois.json")
    config_creator.load_and_add_custom_pois(custom_poi_path)

    # determine which POIs each person visits
    config_creator.create_poi_preferences()
    # create config files for all created objects
    config_creator.create_config_files(path)


def overwrite_residential_coordinates(
    nonres_buildings: list[NonResidentialBuildingWithSourceDto],
    res_buildings: dict[str, BuildingData],
):
    """This is for testing with buildings from the Builda dump file with
    buildings all over Germany"""
    # determine latitude/longitude ranges from nonresidential buildings
    allcoordinates = [b.coordinates.value for b in nonres_buildings]
    latitudes = [c.latitude for c in allcoordinates]
    latmin = min(latitudes)
    latrange = max(latitudes) - latmin
    longitudes = [c.longitude for c in allcoordinates]
    longmin = min(longitudes)
    longrange = max(longitudes) - longmin

    # replace coordinates of residential buildings with random fitting values
    for building in res_buildings.values():
        lat = random.random() * latrange + latmin
        long = random.random() * longrange + longmin
        building.coordinates = Coordinates(lat, long)


def create_city_scenario(
    builda_query: dict,
    scenario_directory: Path,
    lpg_result_dir: Path,
    db_file_path: str = "",
):
    # init logging
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # init RNG
    seed = 0  # random.randrange(sys.maxsize)
    random.seed(seed)
    logging.info(f"Using RNG seed {seed}")

    # collect residential buildings
    res_buildings = import_residential_buildings_from_builda(builda_query)

    # collect non-residential buildings
    nonres_buildings = builda_client_import.get_nonresidential_buildings(builda_query)

    # determine the output directory
    query_str = utils.descriptive_query_text(builda_query)
    result_dir_name = f"scenario_{query_str}"
    result_dir_path = scenario_directory / result_dir_name
    lpg_result_path = lpg_result_dir / result_dir_name

    # create config files for the collected buildings
    create_configs_from_buildings(result_dir_path, res_buildings, nonres_buildings)
    logging.info(f"Finished writing city scenario to {result_dir_path}")

    # copy the Calcspec.json into the scenario directory
    template_filename = "Calcspec.json"
    create_lpg_configs.copy_calcspec_file(
        result_dir_path, template_filename, db_file_path, str(lpg_result_path)
    )


if __name__ == "__main__":
    builda_query = {"city": "Heimbach", "postcode": "52396", "street": ""}
    scenario_directory = Path("./scenarios")
    lpg_result_dir = Path("D:/LPG/Results")
    db_file_path = ""

    # for the cluster
    scenario_directory = Path("R:/phd_dir/data/city_scenarios")
    lpg_result_dir = Path(
        "/storage_cluster/projects/2022-d-neuroth-phd/data/city_simulation_results/"
    )
    db_file_path = "/fast/home/d-neuroth/repos/LoadProfileGenerator/MassSimulation/bin/Release/net8.0/linux-x64/publish/profilegenerator-latest.db3"

    create_city_scenario(builda_query, scenario_directory, lpg_result_dir, db_file_path)
