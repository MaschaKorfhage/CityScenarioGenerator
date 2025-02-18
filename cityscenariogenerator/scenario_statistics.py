"""calculate statistics about the distribution of households etc. in a generated scenario"""

from collections import Counter
import json
from pathlib import Path
from typing import Iterable

from pylpg import lpgdata  # type: ignore


def write_household_statistics(
    house_jobs: Iterable[lpgdata.HouseCreationAndCalculationJob], path: Path
):
    hh_per_house = []
    all_households: list[str] = []
    for house_job in house_jobs:
        hh_per_house.append(len(house_job.House.Households))
        all_households.extend(hh.Name for hh in house_job.House.Households)

    hh_numbers = Counter(hh_per_house)
    with open(path / "households_per_house.json", "w+") as f:
        json.dump(dict(hh_numbers), f, indent=4)

    household_types = Counter(all_households)
    hh_types_ordered = dict(sorted(household_types.items()))
    with open(path / "household_types.json", "w+") as f:
        json.dump(dict(hh_types_ordered), f, indent=4)


def write_poi_statistics(city_data: lpgdata.CityData, path: Path):
    poi_types = Counter(poi.LocationType for poi in city_data.PointsOfInterest.values())
    poi_types_ordered = dict(sorted(poi_types.items()))
    with open(path / "poi_types.json", "w+") as f:
        json.dump(dict(poi_types_ordered), f, indent=4)
