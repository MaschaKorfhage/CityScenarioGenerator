"""Module for getting samples for Germany from BUILDA database."""

import logging
import random
import pandas as pd
from typing import List
from ast import literal_eval
from builda_client.model import Coordinates
from builda_client.dev_client import ResidentialBuilding

from household_data import BuildingRawData, HouseholdRawData


def parse_coordinates(coordinate_str: str) -> Coordinates:
    """
    Parses coordinates from a str in the format POINT(4356954.886156103 3235845.6588559514).

    :param coordinate_str: the parsed coordinate object
    """
    number_str = coordinate_str.removeprefix("POINT(").removesuffix(")")
    numbers = number_str.split(" ")
    if not numbers or len(numbers) != 2:
        raise Exception(f"Unexpected coordinate format: {coordinate_str}")
    return Coordinates(float(numbers[0]), float(numbers[1]))


def get_working_status(employment_list_per_household: List[str]) -> float:
    """Get working status based on employment list for each household."""
    working_status_per_household = 0
    for employment in employment_list_per_household:
        if employment in ("full_time", "part_time"):
            working_status = 1
        elif employment in ("retired", "education", "unemployed"):
            working_status = 0
        working_status_per_household = working_status_per_household + working_status
    # get mean working status per household
    working_status_per_household = working_status_per_household / len(
        employment_list_per_household
    )
    return working_status_per_household


def get_female_status(gender_list_per_household: List[str]) -> float:
    """Get female status based on employment list for each household."""
    female_status_per_household = 0
    for gender in gender_list_per_household:
        if gender == "female":
            female_status = 1
        elif gender == "male":
            female_status = 0
        female_status_per_household = female_status_per_household + female_status
    # get mean female status per household
    female_status_per_household = female_status_per_household / len(
        gender_list_per_household
    )
    return female_status_per_household


def get_senior_status(employment_list_per_household: List[str]) -> float:
    """Get senior status based on employment list for each household."""
    senior_status_per_household = 0
    for employment in employment_list_per_household:
        if employment == "retired":
            senior_status = 1
        else:
            senior_status = 0
        senior_status_per_household = senior_status_per_household + senior_status
    # get mean senior status per household
    senior_status_per_household = senior_status_per_household / len(
        employment_list_per_household
    )
    return senior_status_per_household


def get_buildings_from_builda(
    number_of_random_samples: int | None = None,
) -> tuple[
    List, List, List, List, List, List, List, List, List, List, List[BuildingRawData]
]:
    """Read German buildings and their properties from Builda."""
    # path_to_builda_data = "/fast/home/k-rieck/builda_data/samples_for_mass_simulations_paper/samples_builda_1.xlsx"
    # path_to_builda_data = "/fast/home/k-rieck/builda_data/samples_for_waage_winterberg/buildings_winterberg_only_residential.xlsx"
    # path_to_builda_data = "/fast/home/k-rieck/builda_data/samples_for_waage_winterberg_with_heating_systems/buildings_winterberg_only_residential.xlsx"
    # path_to_builda_data = "/fast/home/k-rieck/builda_data/samples_for_waage_germany_new_census/ethos_builda_v8_random_buildings.xlsx"
    path_to_builda_data = r"D:\Home\OneDrive - Forschungszentrum Jülich GmbH\Promotion\builda_data\ethos_builda_v8_random_buildings.xlsx"
    logging.info(f"Read builda data from {path_to_builda_data}")

    d_f = pd.read_excel(path_to_builda_data, header=0)

    if number_of_random_samples is not None:
        # take random samples from df
        seed = random.randrange(2**32)
        d_f = d_f.sample(n=number_of_random_samples, axis=0, random_state=seed)

    # remove rows where norm heating load is nan
    d_f = d_f[d_f["norm_heating_load_kw"].notna()]
    building_ids = list(d_f["id"])
    tabula_building_codes = list(d_f["tabula_type"])
    conditioned_floor_areas_in_m2 = list(d_f["net_floor_area_m2"])
    number_of_dwellings = list(d_f["housing_unit_count"])
    norm_heating_load_in_kw = list(d_f["norm_heating_load_kw"])
    postal_code = list(d_f["postcode"].astype("string"))

    # get pv potentials
    pv_capacities_in_kw = []
    pv_generations_in_kwh = []
    for pv_potential_dict_string in d_f["pv_potential"].values:
        if isinstance(pv_potential_dict_string, str):
            pv_potential_dict = literal_eval(pv_potential_dict_string)
            pv_capacity = pv_potential_dict["capacity_kW"]
            pv_generation = pv_potential_dict["generation_kWh"]
            pv_capacities_in_kw.append(pv_capacity)
            pv_generations_in_kwh.append(pv_generation)
        else:
            print(
                f"pv potential dict string is no string but {type(pv_potential_dict_string)} {pv_potential_dict_string}. This data will be neglected."
            )

    # get heating systems (from new census)
    commodities = []
    supply_levels = []
    if "heating_system" in d_f.columns:
        for heating_system_dict_string in d_f["heating_system"].values:
            if isinstance(heating_system_dict_string, str):
                heating_system_dict_string = literal_eval(heating_system_dict_string)
                commodity = heating_system_dict_string["commodity"]
                supply_level = heating_system_dict_string["supply_level"]
                commodities.append(commodity)
                supply_levels.append(supply_level)
            else:
                print(
                    f"heating_system_dict_string is no string but {type(heating_system_dict_string)} {heating_system_dict_string}. This data will be neglected."
                )

    # get households (from new census)
    buildings = []
    if "households" in d_f.columns:
        for id, coordinate_str, household_list_string in d_f[
            ["id", "centroid", "households"]
        ].values:
            if not isinstance(household_list_string, str):
                print(
                    f"household_list_string is no string but {type(household_list_string)} {household_list_string}. This data will be neglected."
                )
                continue

            coordinates = parse_coordinates(coordinate_str)
            household_list_string = literal_eval(household_list_string)
            # go through household list for each building
            number_of_persons_per_households = []
            raw_households = []
            for household_dict in household_list_string:
                # get number of persons per household
                number_of_persons_per_households.append(len(household_dict["persons"]))
                num_cars = household_dict["cars"]

                # get employment for each person per household
                employment_list_per_household = []
                gender_list_per_household = []
                for person_dict in household_dict["persons"]:
                    # get employment for each person per household
                    employment_list_per_household.append(person_dict["employment"])
                    # get gender for each person per household
                    gender_list_per_household.append(person_dict["gender"])

                # get mean working status per household
                working_status = get_working_status(employment_list_per_household)
                # get mean female status per household
                female_status = get_female_status(gender_list_per_household)
                # get mean senior status per household
                senior_status = get_senior_status(employment_list_per_household)
                raw_households.append(
                    HouseholdRawData(
                        len(person_dict),
                        num_cars,
                        working_status,
                        female_status,
                        senior_status,
                    )
                )
            buildings.append(BuildingRawData(id, raw_households, coordinates))

    return (
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
        buildings,
    )


def convert_residential_buildings_from_builda(
    buildings: list[ResidentialBuilding],
) -> list[BuildingRawData]:
    """Parses household information for each house and stores it in data objects"""
    converted_buildings = []
    for building in buildings:
        # go through household list for each building
        number_of_persons_per_households = []
        raw_households = []

        # type annotation is apparently not up to date, households is no str
        household_list: list = building.households
        for household_dict in household_list:
            # get number of persons per household
            number_of_persons_per_households.append(len(household_dict["persons"]))
            num_cars = household_dict["cars"]

            # get employment for each person per household
            employment_list_per_household = []
            gender_list_per_household = []
            for person_dict in household_dict["persons"]:
                # get employment for each person per household
                employment_list_per_household.append(person_dict["employment"])
                # get gender for each person per household
                gender_list_per_household.append(person_dict["gender"])

            # get mean working status per household
            working_status = get_working_status(employment_list_per_household)
            # get mean female status per household
            female_status = get_female_status(gender_list_per_household)
            # get mean senior status per household
            senior_status = get_senior_status(employment_list_per_household)
            raw_households.append(
                HouseholdRawData(
                    len(person_dict),
                    num_cars,
                    working_status,
                    female_status,
                    senior_status,
                )
            )
        converted_buildings.append(
            BuildingRawData(building.id, raw_households, building.coordinates)
        )
    return converted_buildings


if __name__ == "__main__":
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
        number_of_persons_per_building,
        working_status_per_building,
        female_status_per_building,
        senior_status_per_building,
    ) = get_buildings_from_builda(number_of_random_samples=10)
