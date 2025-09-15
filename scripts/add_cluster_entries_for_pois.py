"""
Adds all POIs, that are not part of the route cluster mapping, to a random cluster in the mapping.
This can be useful to test random scenarios with existing route sets.
"""

import json
from pathlib import Path
import random

from pylpg import lpgdata


scenario_path = Path("R:/phd_dir/data/city_scenarios/scenario_julich-grosse-rurstr")

cluster_info_file = scenario_path / "routes/cluster_info.json"
assert cluster_info_file.is_file()

with open(cluster_info_file, "r", encoding="utf8") as f:
    cluster_mapping = json.load(f)

clusters = list(set(cluster_mapping.values()))

# load city definition with POIs
with open(scenario_path / "city.json", "r", encoding="utf8") as f:
    filetext = f.read()
city: lpgdata.CityData = lpgdata.CityData.from_json(filetext)  # type: ignore

count = 0
for poiid in city.PointsOfInterest.keys():
    if poiid not in cluster_mapping:
        # assign a random cluster
        cluster_mapping[poiid] = random.choice(clusters)
        count += 1
print(f"Added {count} POIs to the cluster mapping")

new_file = cluster_info_file.parent / f"{cluster_info_file.stem}_new.json"
with open(new_file, "w", encoding="utf8") as f:
    json.dump(cluster_mapping, f)
