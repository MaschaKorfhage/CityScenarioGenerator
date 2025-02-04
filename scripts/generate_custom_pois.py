"""simple script to generate one custom POI of each type, at a random location"""

import json
import random


path = "data/lpg_remote_locations.txt"

with open(path, "r") as file:
    content: str = file.read()

locations = content.splitlines()

all_pois = {}

for location in locations:
    if location == "Home":
        continue  # skip the home location
    name = location + " Custom"
    lat = round(random.uniform(50.4, 50.9), 2)
    long = round(random.uniform(6.2, 6.8), 2)
    all_pois[name] = {
        "LocationType": location,
        "Coordinates": {"Latitude": lat, "Longitude": long},
        "TimeLimit": None,
    }

data = {"PointsOfInterest": all_pois}

with open("data/custom_pois_all.json", "w") as file:

    json.dump(data, file, indent=4)
