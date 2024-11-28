"""Module for generating random samples for LPG households in Germany."""

import os
import pandas as pd
from typing import Dict, List

# from hisim import utils
import random

DATA_PATH = os.path.join(
    "cityscenariogenerator", "builda_file_import", "data_used_for_config_generation"
)


def get_lpg_households():
    """Read lpg households."""
    hh_data_path = os.path.join(DATA_PATH, "Tabelle_LPG_Households.xlsx")
    lpg_household_data = pd.read_excel(hh_data_path)

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


def sort_lpg_households_according_to_household_types(
    lpg_household_data, dict_zensus_household_types_and_weights
):
    """Sort LPG households according to their column names."""
    dict_with_household_type_and_lpg_households = {}
    for key in dict_zensus_household_types_and_weights.keys():
        dict_with_household_type_and_lpg_households.update(
            {key: lpg_household_data.loc[lpg_household_data["householdtype"] == key]}
        )

    return dict_with_household_type_and_lpg_households


def test_distribution(
    sample_list: List,
    random_samples_generated: List,
    dict_literature_percentages_of_samples: Dict,
):
    """Test percentages of randomly generated samples with literature values in order to validate the generated distribution."""
    all_relative_differences = []
    percentages_sample = []
    percentages_literature = []

    for sample in sample_list:
        if sample in random_samples_generated:

            count = random_samples_generated.count(sample)

            percentage_generated = count / len(random_samples_generated)

            percentage_literature = dict_literature_percentages_of_samples[sample]

            relative_difference = (
                abs(percentage_generated - percentage_literature)
                / percentage_literature
            )

            percentages_sample.append(percentage_generated)
            percentages_literature.append(percentage_literature)
            all_relative_differences.append(relative_difference)

    print("sample percentages ", percentages_sample)
    print("literature percentages ", percentages_literature)
    print(
        "rel. difference of sample percentages and literature values ",
        all_relative_differences,
    )


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
            filtered_dict = {
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
                list(lpg_household_working["lpg household"])
            )

        # or if dataframe was empty and no lpg household was found with this working status, take a random sample out of precedent dataframe
        else:
            final_random_lpg_household = random.choice(
                list(lpg_household["lpg household"])
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


def get_random_distributions_of_lpg_households_for_multiple_buildings(
    list_with_number_of_dwellings: List[int],
):
    """Get realsitic distributions of lpg houesholds for multiple buildings and their respective number of dwellings."""

    dict_lpg_households_per_number_of_dwellings: Dict = {}
    list_all_lpg_households = []
    for index, number_of_dwelling_per_building in enumerate(
        list_with_number_of_dwellings
    ):
        (
            list_of_random_lpg_households,
            list_of_random_household_types,
            list_of_random_number_of_residents,
            list_of_random_working_status,
        ) = get_random_distribution_of_lpg_households_per_building(
            number_of_dwellings_per_building=number_of_dwelling_per_building
        )

        list_all_lpg_households.append(list_of_random_lpg_households)

    dict_lpg_households_per_number_of_dwellings.update(
        {"lpg_households": list_all_lpg_households}
    )

    return dict_lpg_households_per_number_of_dwellings


def get_lpg_household_based_on_builda_household_information(
    number_of_dwellings_per_building: int,
    number_of_persons_per_household: int,
    working_status_per_household: float,
    female_status_per_household: float,
    senior_status_per_household: float,
):
    """Get lpg household based on builda household information."""
    # get lpg households
    lpg_household_data = get_lpg_households()
    lpg_household_data = lpg_household_data.loc[
        lpg_household_data["number of residents"] == number_of_persons_per_household
    ]

    lpg_household_data_working = lpg_household_data.loc[
        lpg_household_data["working status"] == working_status_per_household
    ]
    lpg_household_data_female = lpg_household_data_working.loc[
        lpg_household_data_working["female status"] == female_status_per_household
    ]
    lpg_household_data_senior = lpg_household_data_female.loc[
        lpg_household_data_female["senior status float"] == senior_status_per_household
    ]
    # at the end, if dataframe is not empty take random choice and get the final random lpg household
    if lpg_household_data_senior.empty is False:

        final_random_lpg_household = random.choice(
            list(lpg_household_data_senior["lpg household"])
        )

    # or if dataframe was empty and no lpg household was found with this working status, take a random sample out of precedent dataframe
    else:
        if lpg_household_data_female.empty is False:
            final_random_lpg_household = random.choice(
                list(lpg_household_data_female["lpg household"])
            )
        else:
            if lpg_household_data_working.empty is False:
                final_random_lpg_household = random.choice(
                    list(lpg_household_data_working["lpg household"])
                )
            else:
                # if no lpg household is compatible with builda household, choose randoml based on census 2011
                (
                    list_of_random_lpg_households,
                    list_of_random_household_types,
                    list_of_random_number_of_residents,
                    list_of_random_working_status,
                ) = get_random_distribution_of_lpg_households_per_building(
                    number_of_dwellings_per_building=number_of_dwellings_per_building
                )
                final_random_lpg_household = list_of_random_lpg_households[0]
    return final_random_lpg_household


def get_lpg_households_based_on_builda_data(
    list_number_of_persons_per_building: List[List[int]],
    list_dwellings_per_building: List[int],
    list_working_status_per_building: List[List[float]],
    list_female_status_per_building: List[List[float]],
    list_senior_status_per_building: List[List[float]],
):
    """Get lpg households based on builda data."""

    dict_lpg_households_per_number_of_dwellings: Dict = {}
    list_all_lpg_households = []
    # iterate over buildings
    for building_index, number_of_dwellings_per_building in enumerate(
        list_dwellings_per_building
    ):

        list_number_of_persons_per_household = list_number_of_persons_per_building[
            building_index
        ]
        list_working_status_per_household = list_working_status_per_building[
            building_index
        ]
        list_female_status_per_household = list_female_status_per_building[
            building_index
        ]
        list_senior_status_per_household = list_senior_status_per_building[
            building_index
        ]
        list_with_lpg_households_per_building = []
        # iterate over dwellings in building
        for dwelling_index in range(number_of_dwellings_per_building):
            final_lpg_household = get_lpg_household_based_on_builda_household_information(
                number_of_dwellings_per_building=number_of_dwellings_per_building,
                number_of_persons_per_household=list_number_of_persons_per_household[
                    dwelling_index
                ],
                working_status_per_household=list_working_status_per_household[
                    dwelling_index
                ],
                female_status_per_household=list_female_status_per_household[
                    dwelling_index
                ],
                senior_status_per_household=list_senior_status_per_household[
                    dwelling_index
                ],
            )
            list_with_lpg_households_per_building.append(final_lpg_household)
        list_all_lpg_households.append(list_with_lpg_households_per_building)
    # put huseholds in dict
    dict_lpg_households_per_number_of_dwellings.update(
        {"lpg_households": list_all_lpg_households}
    )
    print(dict_lpg_households_per_number_of_dwellings)

    return dict_lpg_households_per_number_of_dwellings
