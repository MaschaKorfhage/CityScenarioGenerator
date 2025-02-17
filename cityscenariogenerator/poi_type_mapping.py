import abc
from dataclasses import dataclass
import json
from typing import Any
from builda_client import dev_client as builda  # type: ignore
from dataclasses_json import dataclass_json  # type: ignore

from cityscenariogenerator.lpg_locations import LpgLocations


@dataclass_json
@dataclass
class LocationType:
    """
    Stores all LPG locations that apply for a certain type of POI.
    One object is used for one building code (e.g., ALKIS).
    """

    non_work_locations: set[str]
    work_locations: set[str]


class PoiLocationMapper(abc.ABC):

    @staticmethod
    def load_mapping(path: str) -> dict[str, Any]:
        with open(path, "r", encoding="utf8") as f:
            return json.load(f)

    @staticmethod
    def combine_mappings(
        mapping1: dict[str, str], mapping2: dict[str, Any]
    ) -> dict[str, Any]:
        return {key: mapping2[val] for key, val in mapping1.items() if val in mapping2}

    @abc.abstractmethod
    def get_matching_locations(
        self, building: builda.NonResidentialBuilding
    ) -> list[str]:
        pass


class NaceCodeMapper(PoiLocationMapper):
    def __init__(self):
        self.nace_loc_mapping = NaceCodeMapper.load_nace_location_mapping()

    @staticmethod
    def load_nace_location_mapping() -> dict[str, list[str]]:
        """
        Loads the mapping of nace codes to corresponding descriptions and the
        mapping of nace code descriptions to matching LPG locations, and combines
        both mappings into one.

        :return: mapping dict from nace codes to LPG locations
        """
        path_nace_codes = "data/nace_code_descriptions.json"
        nace_to_description = PoiLocationMapper.load_mapping(path_nace_codes)
        path_nace_locs = "data/nace_codes_to_locations.json"
        description_to_loc = PoiLocationMapper.load_mapping(path_nace_locs)
        combined = PoiLocationMapper.combine_mappings(
            nace_to_description, description_to_loc
        )
        return combined

    def get_matching_locations(
        self, building: builda.NonResidentialBuilding
    ) -> list[str]:
        use: dict | None = building.use
        if not use:
            return []
        nace_text = use.get("nace_code", "")
        if not nace_text:
            return []
        # get the number of the NACE code (BUILDA entries don't always contain the full
        # NACE code text, but the number is correct)
        code = nace_text.split("_")[0]
        return self.nace_loc_mapping[code]


class AlkisMapper(PoiLocationMapper):
    def __init__(self):
        path_alkis_codes = "data/alkis_code_descriptions.json"
        self.code_descriptions = PoiLocationMapper.load_mapping(path_alkis_codes)

        path_alkis_locs = "data/alkis_codes_to_locations.json"
        description_to_loc_dict = PoiLocationMapper.load_mapping(path_alkis_locs)
        # parse LocationType objects from dicts
        self.desc_to_loc_type = {
            k: LocationType.from_dict(d) for k, d in description_to_loc_dict.items() if d  # type: ignore
        }

        # combine both mappings to directly get from ALKIS code to the LocationType object
        self.location_mapping = PoiLocationMapper.combine_mappings(
            self.code_descriptions, self.desc_to_loc_type
        )

    def get_matching_locations(
        self, building: builda.NonResidentialBuilding
    ) -> list[str]:
        category = building.use.get("raw", {}).get("alkis", "")
        if not category:
            return []
        return self.location_mapping.get(category, [])


def check_nace_to_location_mapping():
    """Checks whether all locations are covered in the mapping, and whether all location names are correct"""
    locations = LpgLocations.ALL
    print(f"Locations: {len(locations)}")

    print("\nLocations that are not covered yet:")
    mapping = NaceCodeMapper.load_nace_location_mapping()
    occurring = {x for val in mapping.values() for x in val}
    for loc in locations:
        if loc not in occurring:
            print(loc)

    print("\nWrong location names:")
    for k, v in mapping.items():
        for val in v:
            if val not in locations:
                print(val)


def check_alkis_mapping():
    am = AlkisMapper()
    mapping = am.location_mapping
    alkis_codes = am.code_descriptions
    nowork = [
        alkis_codes[k]
        for k, v in mapping.items()
        if len(v.work_locations) == 0 and len(v.non_work_locations) > 0
    ]
    print("ALKIS Codes that cannot be a workplace:")
    print("\n".join(nowork))

    onlywork = [
        alkis_codes[k]
        for k, v in mapping.items()
        if len(v.non_work_locations) == 0 and len(v.work_locations) > 0
    ]
    print("\nALKIS Codes that are only a workplace:")
    print("\n".join(onlywork))

    empty = [
        alkis_codes[k]
        for k, v in mapping.items()
        if len(v.non_work_locations) == 0 and len(v.work_locations) == 0
    ]
    print("\nALKIS Codes without any mapping:")
    print("\n".join(empty))

    empty = [alkis_codes[k] for k in alkis_codes.keys() if k not in mapping]
    print("\nExcluded ALKIS Codes:")
    print("\n".join(empty))


if __name__ == "__main__":
    check_alkis_mapping()
