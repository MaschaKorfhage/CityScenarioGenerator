"""Creates configuration files for the LPG out of BuildingData objects generated from BUILDA"""

import logging
from pathlib import Path
from pylpg import lpgdata

from cityscenariogenerator.household_data import BuildingData
from cityscenariogenerator import (
    lpg_config_creator,
    site_export,
)
from cityscenariogenerator.poi_type_mapping import BuildingWithLocationType
from cityscenariogenerator.scenario_params import ScenarioParams


def copy_calcspec_file(
    result_directory: Path,
    template_path: Path,
    lpg_result_path: str = "",
    db_file_path: str = "",
):
    """
    Reads the house job template file (which only contains the database path and the
    CalcSpec), adapts some settings if necessary, and saves the new settings to the
    output directory.

    :param result_directory: output directory to save the settings file to
    :param template_path: path to the settings template file, defaults to "calcspec.json"
    :param lpg_result_path: LPG output path to specifiy in the settings
    :param db_file_path: database path to specify in the settings
    """
    # load the template calcspec.json
    with open(template_path, "r", encoding="utf8") as f:
        lines = f.readlines()
        # remove line comments (which are no valid JSON)
        filtered_lines = [s for s in lines if not s.strip().startswith("//")]
        json_str = "\n".join(filtered_lines)
    house_job: lpgdata.HouseCreationAndCalculationJob = (
        lpgdata.HouseCreationAndCalculationJob.from_json(json_str)  # type: ignore
    )
    assert house_job.CalcSpec is not None, (
        f"No CalcSpec set in the template file: {template_path}"
    )

    # change some settings if necessary
    if lpg_result_path:
        house_job.CalcSpec.OutputDirectory = lpg_result_path
    if db_file_path:
        house_job.PathToDatabase = db_file_path
    # TODO: choose an appropriate GeographicLocation and TemperatureProfile

    # save the adjusted settings to the result directory
    result_json_str: str = house_job.to_json(indent=4)  # type: ignore
    result_file_path = result_directory / "calcspec.json"
    logging.info(f"Saving simulation settings to {result_file_path}")
    with open(result_file_path, "w", encoding="utf8") as f:
        f.write(result_json_str)


def create_configs_from_buildings(
    params: ScenarioParams,
    res_buildings: list[BuildingData],
    nonres_buildings: dict[str, BuildingWithLocationType],
    generate_test_routes: bool = False,
):
    """Main function for creating an LPG scenario with the LPGConfigCreator.

    :param params: scenario parameter object
    :param res_buildings: list of residential buildings to configure for the LPG
    :param nonres_buildings: list of non-residential buildings to use as POIs
    :param generate_test_routes: if True, also generates additional test routes with
                                 distance as the crow flies
    """
    config_creator = lpg_config_creator.LPGConfigCreator(params)
    # create a POI config for each nonresidential building
    skipped_pharmacies: list[str] = []
    for nonres_building in nonres_buildings.values():
        if "Pharmacy" not in nonres_building.location_type.non_work_locations:
            config_creator.add_poi(nonres_building)
        else:
            skipped_pharmacies.append(nonres_building.building.id)

    if skipped_pharmacies:
        logging.info(
            f"Skipped {len(skipped_pharmacies)} base pharmacies: {skipped_pharmacies}"
        )

    # create an LPG house config for each residential building
    for building in res_buildings:
        config_creator.add_lpg_house(building)

    # load custom POIs for this scenario
    config_creator.load_and_add_custom_pois()

    # determine which POIs each person visits
    config_creator.create_poi_preferences(generate_test_routes)

    # optional custom instance export
    #site_export.create_pharmacy_instances(params, config_creator)

    # optional application of site planning results
    # site_export.apply_eplpo_pharmacy_results(params, config_creator)

    config_creator.add_default_queuecapacity("Pharmacy", 2)

    if generate_test_routes:
        # create random routes for testing
        config_creator.create_routes_for_testing()

    # set additional parameters
    assert config_creator.global_city_definition.TravelDefinition, (
        "TravelDefinition not set"
    )
    config_creator.global_city_definition.TravelDefinition.MinimumDrivingAge = 18

    # create config files for all created objects
    config_creator.create_config_files()
