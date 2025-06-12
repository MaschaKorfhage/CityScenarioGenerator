"""Module for generating random samples for LPG households in Germany."""

from collections import Counter, defaultdict
import dataclasses
from enum import StrEnum
import json
import os
from pathlib import Path
import pandas as pd
from typing import Dict, List

import random

from cityscenariogenerator.household_data import (
    BuildingData,
    BuildingRawData,
    HouseholdData,
    HouseholdRawData,
)

DATA_PATH = os.path.join(
    "cityscenariogenerator", "builda_file_import", "data_used_for_config_generation"
)

#: the colum with the household ID to choose
HH_KEY_COLUMN = "lpg household name"


def get_lpg_households():
    """Read lpg households."""
    hh_data_path = os.path.join(DATA_PATH, "Tabelle_LPG_Households.csv")
    lpg_household_data = pd.read_csv(hh_data_path, delimiter=";")

    return lpg_household_data


def get_zensus_household_data():
    """Get zensus data for households and people in Germany."""
    zensus_data = pd.read_excel(
        os.path.join(DATA_PATH, "Tabelle_Zensus_Households.xlsx")
    )

    return zensus_data


def get_zensus_data_and_weights(zensus_dataframe: pd.DataFrame):
    """Get zensus household types and weights."""

    # household types
    zensus_household_types = zensus_dataframe["zensus household types"]
    household_type_weights = zensus_dataframe[
        "number of households with household type"
    ]
    dict_zensus_household_types_and_weights = dict(
        zip(zensus_household_types, household_type_weights)
    )

    # number of residents
    zensus_number_of_residents = zensus_dataframe[
        "zensus number of persons per households"
    ]
    number_of_residents_weights = zensus_dataframe[
        "number of households with number of persons"
    ]
    dict_zensus_number_of_residents_and_weights = dict(
        zip(zensus_number_of_residents, number_of_residents_weights)
    )

    # working status
    zensus_working_status = zensus_dataframe["zensus working status"]
    working_status_weights = zensus_dataframe["number working status"]
    dict_zensus_working_status_and_weights = dict(
        zip(zensus_working_status, working_status_weights)
    )
    dict_zensus_working_status_and_weights.popitem()

    return (
        dict_zensus_household_types_and_weights,
        dict_zensus_number_of_residents_and_weights,
        dict_zensus_working_status_and_weights,
    )


def create_random_samples_for_household_data(
    number_of_random_samples: int, dict_zensus_parameter_and_weights: Dict
):
    """Create random distributions of households based on zensus data."""

    # create random distribution
    number_of_random_samples = number_of_random_samples
    sample_list = list(dict_zensus_parameter_and_weights.keys())
    sample_weights = list(dict_zensus_parameter_and_weights.values())
    random_samples = random.choices(
        sample_list, weights=sample_weights, k=number_of_random_samples
    )
    return random_samples


def get_representative_lpg_household_for_each_household_type(
    list_of_random_household_type_samples: List,
    dict_zensus_number_of_residents_and_weights: Dict,
    dict_zensus_working_status_and_weights: Dict,
    lpg_household_data: pd.DataFrame,
):
    """Get representative lpg household for each zensus household type."""
    list_of_random_lpg_household_samples = []
    list_of_random_number_of_residents = []
    list_of_randomw_working_status = []
    for household_type in list_of_random_household_type_samples:

        if household_type in ["single woman and kids", "single man and kids"]:

            # for these household types number of residents can be either 2 or 3 (based on LPG households)
            filtered_dict: dict = {
                key: dict_zensus_number_of_residents_and_weights[key] for key in [2, 3]
            }
            # make random choice for number of residents on basis of zensus
            number_of_residents = create_random_samples_for_household_data(
                number_of_random_samples=1,
                dict_zensus_parameter_and_weights=filtered_dict,
            )
            number_of_residents = number_of_residents[0]

        elif household_type == "couple with kids":
            # for these household types number of residents can be either 2,3,4,5 or more than 5 (based on LPG households)
            filtered_dict = {
                key: dict_zensus_number_of_residents_and_weights[key]
                for key in [3, 4, 5, "more than 5"]
            }
            # make random choice for number of residents on basis of zensus
            number_of_residents = create_random_samples_for_household_data(
                number_of_random_samples=1,
                dict_zensus_parameter_and_weights=filtered_dict,
            )
            number_of_residents = number_of_residents[0]

        elif household_type == "multiple people (no family)":
            number_of_residents = 3

        elif household_type == "couple without kids":
            number_of_residents = 2

        elif household_type == "single":
            number_of_residents = 1

        if number_of_residents == "more than 5":
            # translate for lpg households (max numer of residents in lpg households is 6)
            number_of_residents = 6

        # get lpg households that have these household_type and number of residents
        lpg_household = lpg_household_data.loc[
            lpg_household_data["householdtype"] == household_type
        ]
        lpg_household = lpg_household.loc[
            lpg_household_data["number of residents"] == number_of_residents
        ]
        list_of_random_number_of_residents.append(number_of_residents)

        # get working status for all residents
        working_status = create_random_samples_for_household_data(
            number_of_random_samples=number_of_residents,
            dict_zensus_parameter_and_weights=dict_zensus_working_status_and_weights,
        )
        list_of_randomw_working_status.append(working_status)
        # get percentage of working status per each household
        number_of_working_people = working_status.count("working")
        percentage_of_working_people_per_household = (
            number_of_working_people / number_of_residents
        )

        # check if household_type with this working status percentage exist and if so filter it
        lpg_household_working = lpg_household.loc[
            lpg_household["working status"]
            == percentage_of_working_people_per_household
        ]

        # at the end, if dataframe is not empty take random choice and get the final random lpg household
        if lpg_household_working.empty is False:

            final_random_lpg_household = random.choice(
                list(lpg_household_working[HH_KEY_COLUMN])
            )

        # or if dataframe was empty and no lpg household was found with this working status, take a random sample out of precedent dataframe
        else:
            final_random_lpg_household = random.choice(
                list(lpg_household[HH_KEY_COLUMN])
            )

        list_of_random_lpg_household_samples.append(final_random_lpg_household)

    return (
        list_of_random_lpg_household_samples,
        list_of_random_number_of_residents,
        list_of_randomw_working_status,
    )


def get_random_distribution_of_lpg_households_per_building(
    number_of_dwellings_per_building: int,
):
    """Get a random realistic distribution of lpg households based on zensus data.

    Get also household types, number of residents and working status of distribution.
    """
    lpg_household_data = get_lpg_households()
    zensus_data = get_zensus_household_data()

    (
        dict_zensus_household_types_and_weights,
        dict_zensus_number_of_residents_and_weights,
        dict_zensus_working_status_and_weights,
    ) = get_zensus_data_and_weights(zensus_dataframe=zensus_data)

    list_of_random_household_types = create_random_samples_for_household_data(
        number_of_random_samples=number_of_dwellings_per_building,
        dict_zensus_parameter_and_weights=dict_zensus_household_types_and_weights,
    )

    (
        list_of_random_lpg_households,
        list_of_random_number_of_residents,
        list_of_random_working_status,
    ) = get_representative_lpg_household_for_each_household_type(
        list_of_random_household_type_samples=list_of_random_household_types,
        dict_zensus_number_of_residents_and_weights=dict_zensus_number_of_residents_and_weights,
        dict_zensus_working_status_and_weights=dict_zensus_working_status_and_weights,
        lpg_household_data=lpg_household_data,
    )

    return (
        list_of_random_lpg_households,
        list_of_random_household_types,
        list_of_random_number_of_residents,
        list_of_random_working_status,
    )


class HHSamplingType(StrEnum):
    """Indicates which criteria were used to limit the eligible households
    during sampling. All criteria might be dropped if no matching households
    are found, ultimately falling back to random sampling with the census
    distribution.
    """

    NONE = "census distribution"
    SIZE = "size"
    WORK = "size, work status"
    WORK_SEX = "size, work status, gender"
    WORK_SEX_SENIOR = "size, work status, gender, senior"


class HouseholdSampler:
    """Helper class to sample LPG households based on the raw data from BUILDA, and to keep
    track of some population statistics."""

    def __init__(self):
        self.sampling_types = defaultdict(int)
        self.household_characteristics = defaultdict(lambda: defaultdict(int))

        # keep track of the total number of households, persons etc.
        self.persons_source = 0
        self.female_source = 0
        self.working_source = 0
        self.senior_source = 0
        self.households_source = 0

    def _add_hh_data_to_statistics(self, household_data: HouseholdRawData) -> None:
        """
        Add the specified household to the statistics counters of this sampler object.

        :param household_data: the household data to add
        """
        for field in dataclasses.fields(household_data):
            value = getattr(household_data, field.name)
            self.household_characteristics[field.name][value] += 1
        self.households_source += 1
        self.persons_source += household_data.num_persons
        self.female_source += household_data.num_persons * household_data.female_ratio
        self.working_source += household_data.num_persons * household_data.working_ratio
        self.senior_source += household_data.num_persons * household_data.senior_ratio

    def get_lpg_household_based_on_builda_household_information(
        self,
        household_data: HouseholdRawData,
    ) -> HouseholdData:
        """Get lpg household based on builda household information."""
        self._add_hh_data_to_statistics(household_data)

        # get lpg households
        lpg_household_data = get_lpg_households()

        lpg_household_data = lpg_household_data.loc[
            lpg_household_data["number of residents"] == household_data.num_persons
        ]

        # collect all LPG households with matching characteristics
        lpg_household_data_working = lpg_household_data.loc[
            lpg_household_data["working status"] == household_data.working_ratio
        ]
        lpg_household_data_female = lpg_household_data_working.loc[
            lpg_household_data_working["female status"] == household_data.female_ratio
        ]
        lpg_household_data_senior = lpg_household_data_female.loc[
            lpg_household_data_female["senior status float"]
            == household_data.senior_ratio
        ]

        household_set_to_use = None
        sampling_type = HHSamplingType.NONE
        # check if there are households that fulfill all criteria, or else drop some conditions
        if lpg_household_data_senior.empty is False:
            # take all criteria into account
            household_set_to_use = lpg_household_data_senior
            sampling_type = HHSamplingType.WORK_SEX_SENIOR
        elif lpg_household_data_female.empty is False:
            # ignore the share of seniors
            household_set_to_use = lpg_household_data_female
            sampling_type = HHSamplingType.WORK_SEX
        elif lpg_household_data_working.empty is False:
            # ignore the share of females
            household_set_to_use = lpg_household_data_working
            sampling_type = HHSamplingType.WORK
        elif lpg_household_data.empty is False:
            # ignore the share of working people
            household_set_to_use = lpg_household_data
            sampling_type = HHSamplingType.SIZE
        # store how the household was sampled, for statistics
        self.sampling_types[sampling_type] += 1

        # randomly select one household out of the matching ones
        if household_set_to_use is not None:
            hh_names = list(household_set_to_use[HH_KEY_COLUMN])
            lpg_household_name = random.choice(hh_names)
        else:
            # if no LPG household is compatible even when dropping most conditions, choose randomly based on census 2011
            (
                list_of_random_lpg_households,
                list_of_random_household_types,
                list_of_random_number_of_residents,
                list_of_random_working_status,
            ) = get_random_distribution_of_lpg_households_per_building(1)
            lpg_household_name = list_of_random_lpg_households[0]
        return HouseholdData(lpg_household_name, household_data.num_cars)


def create_stat_file(path: Path, data: dict):
    with open(path, "w", encoding="utf8") as f:
        json.dump(data, f, indent=4)


def get_lpg_households_based_on_builda_data(
    building_data_list: list[BuildingRawData], stats_path: Path | None = None
) -> list[BuildingData]:
    """Get lpg households based on builda data."""
    sampler = HouseholdSampler()
    buildings: list[BuildingData] = []
    # iterate over buildings
    for building_raw in building_data_list:
        households = []
        # iterate over dwellings in building
        for household_raw in building_raw.households:
            household = sampler.get_lpg_household_based_on_builda_household_information(
                household_raw
            )
            households.append(household)
        building = BuildingData(building_raw.id, households, building_raw.coordinates)
        buildings.append(building)
    if stats_path:
        # write statistics on original BUILDA data and the household sampling
        stats_path.mkdir(parents=True, exist_ok=True)
        general_info = {
            "houses": len(building_data_list),
            "households": sampler.households_source,
            "persons": sampler.persons_source,
            "female": sampler.female_source,
            "working": sampler.working_source,
            "senior": sampler.senior_source,
        }
        create_stat_file(stats_path / "general_info.json", general_info)
        create_stat_file(stats_path / "household_sampling.json", sampler.sampling_types)
        create_stat_file(
            stats_path / "household_characteristics.json",
            sampler.household_characteristics,
        )
        car_numbers = Counter(h.num_cars for b in buildings for h in b.households)
        cars_sorted = dict(sorted(car_numbers.items()))
        create_stat_file(stats_path / "cars_per_household.json", cars_sorted)
    return buildings
