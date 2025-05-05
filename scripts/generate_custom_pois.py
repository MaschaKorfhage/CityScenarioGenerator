"""simple script to generate one custom POI of each type, at a random location"""

import json
from pathlib import Path
import random

from pylpg.lpgdata import CityData

from cityscenariogenerator.lpg_locations import LpgLocations


def generate_random_pois():
    pois = {}

    for location in LpgLocations.ALL:
        name = location + " Custom"
        lat = round(random.uniform(50.6, 50.6638), 3)
        long = round(random.uniform(6.4029, 6.5747), 3)
        pois[name] = {
            "LocationType": location,
            "Coordinates": {"Latitude": lat, "Longitude": long},
            "TimeLimit": None,
        }
    return pois


def select_pois_from_citydata(city_path: Path):
    """Selects the first POI of each type from the city file."""
    with open(city_path, "r") as file:
        citydata: CityData = CityData.from_json(file.read())
    print(f"Loaded city data with {len(citydata.PointsOfInterest)} POIs")
    pois = {}
    poi_types = set()
    for poiid, poi in citydata.PointsOfInterest.items():
        if poi.LocationType not in poi_types:
            pois[poiid] = poi
            poi_types.add(poi.LocationType)
    print(f"Selected {len(pois)} POIs of different types")
    # convert the pois to dicts to write to json
    poi_dicts = {id: poi.to_dict() for id, poi in pois.items()}
    return poi_dicts


# all_pois = generate_random_pois()

cityfile = Path("R:/phd_dir/data/city_scenarios/scenario_julich/city.json")
all_pois = select_pois_from_citydata(cityfile)

# write the pois to a json file
data = {"PointsOfInterest": all_pois}
with open("data/custom_pois_all.json", "w") as file:
    json.dump(data, file, indent=4)
