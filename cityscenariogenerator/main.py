"""Generates a city scenario for the LPG from BUILDA data"""

import logging
from pathlib import Path
import random

from builda_client.client import NonResidentialBuildingWithSourceDto, Coordinates  # type: ignore

from cityscenariogenerator import builda_client_import, utils, create_lpg_configs
from cityscenariogenerator.household_data import BuildingData


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
    custom_poi_path = Path("data/custom_pois_all.json")
    config_creator.load_and_add_custom_pois(custom_poi_path)

    # determine which POIs each person visits
    config_creator.create_poi_preferences()

    # create random routes for testing
    config_creator.create_routes_for_testing()

    # set additional parameters
    config_creator.global_city_definition.MinimumDrivingAge = 18

    # create config files for all created objects
    config_creator.create_config_files(path)


def create_city_scenario(
    builda_query: dict,
    scenario_directory: Path,
    lpg_result_dir: Path,
    db_file_path: str = "",
):
    # determine the output directory
    query_str = utils.descriptive_query_text(builda_query)
    result_dir_name = f"scenario_{query_str}"
    result_dir_path = scenario_directory / result_dir_name
    lpg_result_path = lpg_result_dir / result_dir_name

    utils.clear_directory(result_dir_path)
    if result_dir_path.exists() and any(result_dir_path.iterdir()):
        raise Exception(f"Target directory was not empty: {result_dir_path}")

    utils.init_logging(scenario_directory)

    # init RNG
    seed = 0  # random.randrange(sys.maxsize)
    random.seed(seed)
    logging.info(f"Using RNG seed {seed}")

    # collect residential buildings
    res_buildings = import_residential_buildings_from_builda(builda_query)

    # collect non-residential buildings
    nonres_buildings = builda_client_import.get_nonresidential_buildings(builda_query)

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
    scenario_dir = Path("./scenarios")
    lpg_result_dir = Path("D:/LPG/Results")

    # for the cluster
    scenario_dir = Path(
        "/storage_cluster/projects/2022-d-neuroth-phd/data/city_scenarios/"
    )
    lpg_result_dir = Path("/fast/home/d-neuroth/city_simulation_results/")

    create_city_scenario(builda_query, scenario_dir, lpg_result_dir, "")
