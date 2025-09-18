"""Generates a city scenario for the LPG from BUILDA data"""

import logging
import random
from datetime import datetime
from pathlib import Path

from cityscenariogenerator import (
    builda_client_import,
    create_lpg_configs,
    scenario_params,
    utils,
)
from cityscenariogenerator.household_data import BuildingData
from cityscenariogenerator.scenario_params import ScenarioParams
from cityscenariogenerator.nonresidential_building_import import (
    import_nonresidential_buildings_from_builda,
)
from cityscenariogenerator.poi_type_mapping import BuildingWithLocationType
from cityscenariogenerator.residential_building_import import (
    import_residential_buildings_from_builda,
)


def create_configs_from_buildings(
    params: ScenarioParams,
    res_buildings: list[BuildingData],
    nonres_buildings: dict[str, BuildingWithLocationType],
):
    config_creator = create_lpg_configs.LPGConfigCreator(params)
    # create a POI config for each nonresidential building
    for nonres_building in nonres_buildings.values():
        config_creator.add_poi(nonres_building)

    # create an LPG house config for each residential building
    for building in res_buildings:
        config_creator.add_lpg_house(building)

    # load custom POIs for this scenario
    config_creator.load_and_add_custom_pois()

    # determine which POIs each person visits
    config_creator.create_poi_preferences()

    # create random routes for testing
    config_creator.create_routes_for_testing()

    # set additional parameters
    assert config_creator.global_city_definition.TravelDefinition, (
        "TravelDefinition not set"
    )
    config_creator.global_city_definition.TravelDefinition.MinimumDrivingAge = 18

    # create config files for all created objects
    config_creator.create_config_files()


def create_city_scenario(
    builda_query: dict,
    scenario_directory: Path,
    lpg_result_dir: Path,
    scenario_adapt_dir: Path | None = None,
    db_file_path: str = "",
):
    start = datetime.now()
    # determine the output directory
    query_str = utils.descriptive_query_text(builda_query)
    result_dir_name = f"scenario_{query_str}"
    result_dir = scenario_directory / result_dir_name
    lpg_result_path = lpg_result_dir / result_dir_name

    utils.clear_directory(result_dir)
    if result_dir.exists() and any(result_dir.iterdir()):
        raise Exception(f"Target directory was not empty: {result_dir}")

    utils.init_logging(result_dir)

    # setup the scenario parameters object
    params = scenario_params.get_params(
        builda_query, result_dir, lpg_result_path, scenario_adapt_dir
    )
    if params.has_custom_adaptations():
        logging.info(f"Applying custom adaptations: {params.custom_adaptations_dir()}")
    else:
        logging.info("Applying no custom adaptations")

    # init RNG
    seed = 0  # random.randrange(sys.maxsize)
    random.seed(seed)
    logging.info(f"Using RNG seed {seed}")

    # collect residential and non-residential buildings
    builda_client_import.check_matching_cache_files(params.builda_query)
    res_buildings = import_residential_buildings_from_builda(params)
    nonres_buildings = import_nonresidential_buildings_from_builda(
        params, res_buildings
    )

    # create config files for the collected buildings
    create_configs_from_buildings(params, res_buildings, nonres_buildings)
    logging.info(f"Finished writing city scenario to {result_dir}")

    # copy the calcspec.json into the scenario directory
    template_path = Path("data/calcspec_template.json")
    create_lpg_configs.copy_calcspec_file(
        result_dir, template_path, str(lpg_result_path), db_file_path
    )
    logging.info(f"Finished scenario creation in {datetime.now() - start}")


def main():
    builda_query = {"city": "Jülich", "postcode": "", "street": ""}
    scenario_dir = Path("./scenarios")
    lpg_result_dir = Path("C:/LPG/Results")
    scenario_adapt_dir = Path("scenario_adaptations/rhivas")

    # for the cluster
    scenario_dir = Path("/fast/central/projects/2022-d-neuroth-phd/city_scenarios")
    lpg_result_dir = Path("/fast/central/projects/2022-d-neuroth-phd/results/")

    create_city_scenario(builda_query, scenario_dir, lpg_result_dir, scenario_adapt_dir)


if __name__ == "__main__":
    main()
