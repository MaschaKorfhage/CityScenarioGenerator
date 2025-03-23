"""calculate statistics about the distribution of households etc. in a generated scenario"""

from collections import Counter
import json
from pathlib import Path
from typing import Iterable

from pylpg import lpgdata


def write_general_info(
    house_jobs: Iterable[lpgdata.HouseCreationAndCalculationJob],
    pois: Iterable[lpgdata.PointOfInterestData],
    path: Path,
):
    """
    Collect some general information about the generated scenario

    :param house_jobs: list of created house jobs
    :param pois: list of created POIs
    :param path: path for the result file
    """
    houselist = list(house_jobs)
    num_hh = sum(len(hj.House.Households) for hj in houselist)  # type: ignore
    num_persons = sum(
        len(hh.PointOfInterestPreferences)  # type: ignore
        for hj in houselist
        for hh in hj.House.Households  # type: ignore
    )
    info = {
        "houses": len(houselist),
        "households": num_hh,
        "persons": num_persons,
        "POIs": len(list(pois)),
    }
    info["houses"]
    with open(path / "general_info.json", "w+") as f:
        json.dump(info, f, indent=4)


def write_household_statistics(
    house_jobs: Iterable[lpgdata.HouseCreationAndCalculationJob], path: Path
):
    """
    Creates two statistics files about the distribution of households in the scenario.
    The first lists the distribution of the number of households per house.
    The second lists the distribution of the different household types.

    :param house_jobs: house configs to analyze
    :param path: path for the result files
    """
    hh_per_house = []
    all_households: list[str] = []
    for house_job in house_jobs:
        hh_per_house.append(len(house_job.House.Households))  # type: ignore
        all_households.extend(
            hh.HouseholdTemplateSpec.HouseholdTemplateName  # type: ignore
            for hh in house_job.House.Households  # type: ignore
        )

    hh_counter = Counter(hh_per_house)
    hh_numbers: dict = dict(sorted(hh_counter.items()))
    hh_numbers["total"] = hh_counter.total()
    with open(path / "households_per_house.json", "w+") as f:
        json.dump(hh_numbers, f, indent=4)

    household_types = Counter(all_households)
    hh_types_ordered = dict(sorted(household_types.items()))
    with open(path / "household_types.json", "w+") as f:
        json.dump(dict(hh_types_ordered), f, indent=4)


def write_poi_statistics(
    pois: Iterable[lpgdata.PointOfInterestData], path: Path, name: str = "poi_types"
):
    """
    Writes a JSON file containing the number of each type of PIO in the scenario.

    :param pois: the POIs to analyze
    :param path: the directory to save the JSON file to
    :param name: name of the produced file, defaults to "poi_types"
    """
    poi_types = Counter(poi.LocationType for poi in pois)
    poi_types_ordered = dict(sorted(poi_types.items()))
    with open(path / f"{name}.json", "w+") as f:
        json.dump(dict(poi_types_ordered), f, indent=4)
