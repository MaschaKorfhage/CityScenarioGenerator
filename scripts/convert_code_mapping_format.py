"""
Reads a code-to-location mapping from JSON and converts it to a new format.
Old format: each code is mapped to a list of locations
New format: a LocationType object for each code, separating work and non-work locations
"""

import json


from cityscenariogenerator.lpg_locations import LpgLocations
from cityscenariogenerator.poi_type_mapping import LocationType


with open("data/alkis_mapping/codes_to_locations_old.json", encoding="utf8") as f:
    mapping2 = json.load(f)


normal_locs = LpgLocations.NO_WORK
work_locs = LpgLocations.WORK

converted: dict = {}
for alkis, locations in mapping2.items():
    if locations is None:
        converted[alkis] = locations
        continue
    normal = {loc for loc in locations if loc not in work_locs}
    work = {loc for loc in locations if loc in work_locs}
    converted[alkis] = LocationType(normal, work).to_dict()  # type: ignore


with open("data/alkis_mapping/location_mapping.json", "w+", encoding="utf8") as f:
    json.dump(converted, f, indent=4, ensure_ascii=False)
