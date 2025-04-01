"""
Contains functions to import residential buildings from BUILDA, and map them to the data required for the LoadProfileGenerator.
"""

import logging
import sys
from cityscenariogenerator import builda_client_import
import cityscenariogenerator.builda_file_import.sampling_with_builda_data.sampling_buildings_from_builda as builda_file_sampler
import cityscenariogenerator.builda_file_import.statistical_sampling.sampling_lpg_households as lpg_household_sampler
from cityscenariogenerator.household_data import BuildingData
from cityscenariogenerator.scenario_params import ScenarioParams


def import_residential_buildings_from_builda_file(
    number_of_buildings: int,
) -> list[BuildingData]:
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
    ) = builda_file_sampler.get_buildings_from_builda_file(
        number_of_random_samples=number_of_buildings
    )

    # get lpg profiles based on builda data
    buildings = lpg_household_sampler.get_lpg_households_based_on_builda_data(
        building_data_list
    )
    return buildings


def import_residential_buildings_from_builda(
    params: ScenarioParams,
) -> list[BuildingData]:
    # load residential buildings from BUILDA
    raw_buildings = builda_client_import.get_residential_buildings(params.builda_query)
    # parse the household data into data objects
    building_data_list = builda_file_sampler.convert_residential_buildings_from_builda(
        raw_buildings
    )

    # determine LPG households for each building
    buildings = lpg_household_sampler.get_lpg_households_based_on_builda_data(
        building_data_list
    )
    return buildings
