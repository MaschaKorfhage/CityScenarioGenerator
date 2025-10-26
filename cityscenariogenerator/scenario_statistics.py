"""calculate statistics about the distribution of households etc. in a generated scenario"""

from collections import Counter, defaultdict
import json
import logging
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

from pylpg import lpgdata

from cityscenariogenerator.lpg_locations import LpgLocations
from cityscenariogenerator.utils import (
    create_json_file,
    get_jsonref_name,
    sort_by_key,
    sort_by_val,
)

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
    create_json_file(path / "general_info.json", info)


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
    create_json_file(path / "households_per_house.json", hh_numbers)

    household_types = Counter(all_households)
    hh_types_ordered = dict(sorted(household_types.items()))
    create_json_file(path / "household_types.json", dict(hh_types_ordered))


def write_persons_per_house(
    house_jobs: Iterable[lpgdata.HouseCreationAndCalculationJob], path: Path
):
    """
    Creats a file specifying the number of person in each house.

    :param house_jobs: house configs to analyze
    :param path: path for the result file
    """
    personcounts = {}
    for house in house_jobs:
        assert house.House is not None
        id = house.House.Name
        count = sum(len(hh.PointOfInterestPreferences) for hh in house.House.Households)
        personcounts[id] = count
    # store person count for each individual house ID
    create_json_file(path / "persons_per_house.json", dict(personcounts))

    # additionally store frequency of all house sizes
    house_sizes = Counter(personcounts.values())
    house_sizes = sort_by_key(house_sizes)
    create_json_file(path / "house_sizes.json", house_sizes)


def write_household_sizes(
    house_jobs: Iterable[lpgdata.HouseCreationAndCalculationJob], path: Path
):
    """
    Creates a file showing the distribution of different household sizes.

    :param house_jobs: house configs to analyze
    :param path: path for the result file
    """
    household_sizes = defaultdict(int)
    for house in house_jobs:
        assert house.House is not None
        for household in house.House.Households:
            size = len(household.PointOfInterestPreferences)
            household_sizes[size] += 1

    # sort by size
    household_sizes = sort_by_key(household_sizes)
    create_json_file(path / "household_sizes.json", dict(household_sizes))


def write_car_numbers(
    house_jobs: Iterable[lpgdata.HouseCreationAndCalculationJob], path: Path
):
    """
    Creates a file showing the number of cars per household, and the total number
    of cars.

    :param house_jobs: house configs to analyze
    :param path: path for the result file
    """
    transport_device_sets = defaultdict(int)
    for house in house_jobs:
        assert house.House is not None
        for household in house.House.Households:
            assert household.TransportationDeviceSet is not None
            trans_set = get_jsonref_name(household.TransportationDeviceSet)
            transport_device_sets[trans_set] += 1

    transport_device_sets = sort_by_val(transport_device_sets)
    create_json_file(path / "cars_per_household.json", dict(transport_device_sets))


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
    with open(PERSON_CHARACTERISTICS_PATH, "r", encoding="utf8") as f:
        person_characteristics = json.load(f)

    # collect the information from each person
    all_infos: list[dict[str, Any]] = []
    for house in house_jobs:
        assert house.House is not None
        for hh in house.House.Households:
            for person in hh.PointOfInterestPreferences.keys():
                all_infos.append(person_characteristics[person])
    if not all_infos:
        logging.warning("Did not find any PointOfinterestPreferences")
        return

    # count the distribution of all charactististics
    counters = generate_person_statistics(all_infos)

    # special addition for Zensus validation: get statistics for persons older than 14 years
    persons_over_14 = [d for d in all_infos if d["age"] > 14]
    counters_over_14 = generate_person_statistics(persons_over_14)
    counters.update({f"{k}_15+": v for k, v in counters_over_14.items()})

    filename = path / "person_statistics.json"
    create_json_file(filename, counters)

    # additionally create the same statistics file with relative values
    rel_counts = {}
    personcount = len(all_infos)
    for key, counter in counters.items():
        rel_counts[key] = {k: v / personcount for k, v in counter.items()}

    filename = path / "person_statistics_relative.json"
    create_json_file(filename, rel_counts)


def generate_person_statistics(
    all_infos: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Generate a nested person statistics dict form a list of
    person characteristics.

    :param all_infos: list of person characteristics as dicts
    :return: nested dict containing statistics for all person attributes
    """
    counters = {}
    for info_name in all_infos[0].keys():
        counter = Counter(x[info_name] for x in all_infos)
        counters[info_name] = dict(sorted(counter.items()))

    # special case: aggregate ages to age categories
    if "age" in counters:
        age_category_counts = defaultdict(int)
        AGE_CATEGORIES = {
            "<6": (0, 5),
            "6-9": (6, 9),
            "10-18": (10, 18),
            "19-24": (19, 24),
            "25-39": (25, 39),
            "40-66": (40, 66),
            ">66": (67, 200),
        }
        for age, frequency in counters["age"].items():
            for catkey, catlimits in AGE_CATEGORIES.items():
                if catlimits[0] <= age <= catlimits[1]:
                    age_category_counts[catkey] += frequency
        counters["age_categories"] = age_category_counts

    # special case: aggregate work status to categories
    if "work_status" in counters:
        work_counter = counters["work_status"]
        employment_categories = {}
        WORK_CATEGORIES = {
            "employed": ["full time", "part time"],
            "student": ["student"],
            "unemployed": ["unemployed"],
            "retired": ["retired"],
        }
        for cat, values in WORK_CATEGORIES.items():
            employment_categories[cat] = sum(work_counter.get(v, 0) for v in values)
        counters["employment_categories"] = employment_categories

        # special case: combine sex and employment
        if "sex" in counters:
            employment_sex = {}
            combined_count = Counter((d["work_status"], d["sex"]) for d in all_infos)
            for sex in counters["sex"].keys():
                for cat, values in WORK_CATEGORIES.items():
                    employment_sex[f"{cat}_{sex}"] = sum(
                        combined_count.get((v, sex), 0) for v in values
                    )
            counters["employment_sex"] = sort_by_key(employment_sex)
    return counters


def write_poi_statistics(
    pois: Iterable[lpgdata.PointOfInterestData], path: Path, name: str = "poi_types"
):
    """
    Writes a JSON file containing the number of each type of POI in the scenario.

    :param pois: the POIs to analyze
    :param path: the directory to save the JSON file to
    :param name: name of the produced file, defaults to "poi_types"
    """
    poi_types = Counter(poi.LocationType for poi in pois)
    poi_types_ordered = dict(sorted(poi_types.items()))
    create_json_file(path / f"{name}.json", dict(poi_types_ordered))

    # also count the number of POIs per category
    poi_categories = {
        "Nichtwohngebäude": LpgLocations.NONRES_BUILD_NO_WORK,
        "Wohngebäude": LpgLocations.RESIDENTIAL,
        "Arbeitsplatz": LpgLocations.WORK,
        "Kein Gebäude": LpgLocations.NO_BUILDING,
    }
    category_counts: dict[str, int] = {}
    for category, location_set in poi_categories.items():
        category_counts[category] = sum(
            n for p, n in poi_types.items() if p in location_set
        )
    create_json_file(path / f"{name}_categories.json", category_counts)


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
    create_json_file(filepath, statistics)
