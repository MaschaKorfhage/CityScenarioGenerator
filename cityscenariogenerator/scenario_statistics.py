"""calculate statistics about the distribution of households etc. in a generated scenario"""

from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import mean, median
from typing import Iterable

from pylpg import lpgdata

#: path to a file providing characteristic information for each LPG person (from ETHOS.ActivityAssure)
PERSON_CHARACTERISTICS_PATH = Path("data/person_characteristics.json")


def write_general_info(
    house_jobs: Iterable[lpgdata.HouseCreationAndCalculationJob],
    pois: Iterable[lpgdata.PointOfInterestData],
    path: Path,
):
    """
    Collect some general information about the generated scenario

    :param house_jobs: list of created house jobs
    :param pois: list of created POIs
    :param path: directory for the result file
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


def write_person_statistics(
    house_jobs: Iterable[lpgdata.HouseCreationAndCalculationJob], path: Path
):
    """
    Creates a file with statistics about age, gender and employment of all
    persons in the city scenario

    :param house_jobs: house configs containing the persons to analyze
    :param path: directory for the result file
    """
    # load the person characteristics file
    with open(PERSON_CHARACTERISTICS_PATH, "r") as f:
        person_characteristics = json.load(f)

    # collect the information from each person
    all_infos: list[dict] = []
    for house in house_jobs:
        assert house.House is not None
        for hh in house.House.Households:
            for person in hh.PointOfInterestPreferences.keys():
                all_infos.append(person_characteristics[person])

    # count the distribution of all charactististics
    counters = {}
    for info_name in all_infos[0].keys():
        counter = Counter(x[info_name] for x in all_infos)
        counters[info_name] = dict(sorted(counter.items()))

    # special case: aggregate ages to age categories
    if "age" in counters:
        age_category_counts = defaultdict(int)
        AGE_CATEGORIES = {
            "<18": (0, 18),
            "18-66": (18, 67),
            ">66": (67, 200),
        }
        for age, frequency in counters["age"].items():
            for catkey, catlimits in AGE_CATEGORIES.items():
                if catlimits[0] <= age < catlimits[1]:
                    age_category_counts[catkey] += frequency
        counters["age_categories"] = age_category_counts

    filename = path / "person_statistics.json"
    with open(filename, "w+", encoding="utf8") as f:
        json.dump(counters, f, indent=4)

    # additionally create the same statistics file with relative values
    rel_counts = {}
    personcount = len(all_infos)
    for key, counter in counters.items():
        rel_counts[key] = {k: v / personcount for k, v in counter.items()}

    filename = path / "person_statistics_relative.json"
    with open(filename, "w+", encoding="utf8") as f:
        json.dump(rel_counts, f, indent=4)


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


def write_route_statistics(routes: Iterable[lpgdata.RouteData], path: Path):
    """
    Create statistics on route distances per mode.

    :param routes: list of route
    :param path: the directory to save the statistics file to
    """
    # group all route distances by mode
    mode_distances = [r.mode_distances for r in routes]
    distances_by_mode = defaultdict(list)
    for dist_dict in mode_distances:
        for mode, distance in dist_dict.items():
            distances_by_mode[mode].append(distance)

    # calculate statistics for each mode separately
    statistics = {}
    for mode, distances in distances_by_mode.items():
        statistics[mode] = {
            "mean": mean(distances),
            "min": min(distances),
            "max": max(distances),
            "median": median(distances),
        }
    filepath = path / "route_distances.json"
    with open(filepath, "w+", encoding="utf8") as f:
        json.dump(statistics, f, indent=4)
