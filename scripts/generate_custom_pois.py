"""simple script to generate one custom POI of each type, at a random location"""

import json
import random

from cityscenariogenerator.lpg_locations import LpgLocations

all_pois = {}

for location in LpgLocations.ALL:
    name = location + " Custom"
    lat = round(random.uniform(50.6, 50.6638), 3)
    long = round(random.uniform(6.4029, 6.5747), 3)
    all_pois[name] = {
        "LocationType": location,
        "Coordinates": {"Latitude": lat, "Longitude": long},
        "TimeLimit": None,
    }

data = {"PointsOfInterest": all_pois}

with open("data/custom_pois_all.json", "w") as file:

    json.dump(data, file, indent=4)
