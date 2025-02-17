"""
Reads a code-to-location mapping from JSON and converts it to a new format.
Old format: each code is mapped to a list of locations
New format: a LocationType object for each code, separating work and non-work locations
"""

from dataclasses import dataclass
import json

from dataclasses_json import dataclass_json

from cityscenariogenerator.lpg_locations import LpgLocations


@dataclass_json
@dataclass
class LocationType:
    non_work_locations: set[str]
    work_locations: set[str]


with open("data/alkis_codes_to_locations.json", encoding="utf8") as f:
    mapping2 = json.load(f)


normal_locs = LpgLocations.NON_WORK
work_locs = LpgLocations.WORK

converted = {}
for alkis, locations in mapping2.items():
    if not locations:
        converted[alkis] = locations
        continue
    normal = {loc for loc in locations if loc in normal_locs}
    work = {loc for loc in locations if loc in work_locs}
    converted[alkis] = LocationType(normal, work).to_dict()  # type: ignore


with open("data/alkis_codes_to_locations2.json", "w+", encoding="utf8") as f:
    json.dump(converted, f, indent=4, ensure_ascii=False)
