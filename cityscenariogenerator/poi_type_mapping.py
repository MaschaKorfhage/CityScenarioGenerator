import abc
from dataclasses import dataclass, field
import json
import random
from typing import Any

from dataclasses_json import dataclass_json  # type: ignore
from builda_client import dev_client as builda  # type: ignore

from cityscenariogenerator.lpg_locations import LpgLocations


@dataclass_json
@dataclass(frozen=True)
class LocationType:
    """
    Stores all LPG locations that apply for a certain type of POI.
    One object is used for one building code (e.g., ALKIS).
    """

    non_work_locations: set[str] = field(default_factory=set)
    work_locations: set[str] = field(default_factory=set)


@dataclass
class BuildingWithLocationType:
    """
    Stores a nonresidential building, together with the LPG locations assigned
    to it.
    """

    building: builda.NonResidentialBuilding
    location_type: LocationType

    def collect_lpg_locations(self) -> list[str]:
        """
        Collects a list of all LPG locations (work and non-work) that
        this building provides. If multiple non-work locations are
        possible, one of them is sampled randomly.

        :return: list of locations for this building
        """
        if not self.location_type:
            # no locations fit this building
            return []

        if (
            not self.location_type.non_work_locations
            and not self.location_type.work_locations
        ):
            # no locations assigned yet
            return []

        # select all locations that will be available in this building
        # for that, select ALL matching work locations and ONE non-work location
        locations = list(self.location_type.work_locations)
        if len(self.location_type.non_work_locations) > 0:
            nonwork = random.choice(list(self.location_type.non_work_locations))
            locations.append(nonwork)
        return locations


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
    def get_orig_category(self, building: builda.NonResidentialBuilding) -> str | None:
        pass

    @abc.abstractmethod
    def get_matching_locations(
        self, building: builda.NonResidentialBuilding
    ) -> LocationType:
        pass

    def get_locations_for_buildings(
        self, buildings: list[builda.NonResidentialBuilding]
    ) -> list[BuildingWithLocationType]:
        return [
            BuildingWithLocationType(b, self.get_matching_locations(b))
            for b in buildings
        ]


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
        path_nace_codes = "data/nace_mapping/code_descriptions.json"
        nace_to_description = PoiLocationMapper.load_mapping(path_nace_codes)
        path_nace_locs = "data/nace_mapping/location_mapping.json"
        description_to_loc = PoiLocationMapper.load_mapping(path_nace_locs)
        combined = PoiLocationMapper.combine_mappings(
            nace_to_description, description_to_loc
        )
        return combined

    def get_orig_category(self, building):
        if not building.use:
            return None
        return building.use.get("nace_code", None)

    def get_matching_locations(
        self, building: builda.NonResidentialBuilding
    ) -> LocationType:
        raise NotImplementedError(
            "The interface changed, the Nace mapping has not been updated yet"
        )
        # use: dict | None = building.use
        # if not use:
        #     return set()
        # nace_text = use.get("nace_code", "")
        # if not nace_text:
        #     return set()
        # # get the number of the NACE code (BUILDA entries don't always contain the full
        # # NACE code text, but the number is correct)
        # code = nace_text.split("_")[0]
        # return self.nace_loc_mapping[code]


class AlkisMapper(PoiLocationMapper):
    def __init__(self) -> None:
        path_alkis_codes = "data/alkis_mapping/code_descriptions.json"
        self.code_descriptions = PoiLocationMapper.load_mapping(path_alkis_codes)

        path_alkis_locs = "data/alkis_mapping/location_mapping.json"
        description_to_loc_dict = PoiLocationMapper.load_mapping(path_alkis_locs)
        # parse LocationType objects from dicts
        self.desc_to_loc_type = {
            k: LocationType.from_dict(d) for k, d in description_to_loc_dict.items() if d  # type: ignore
        }

        # combine both mappings to directly get from ALKIS code to the LocationType object
        self.location_mapping: dict[str, LocationType] = (
            PoiLocationMapper.combine_mappings(
                self.code_descriptions, self.desc_to_loc_type
            )
        )

    def get_orig_category(
        self, building: builda.NonResidentialBuilding, as_text: bool = True
    ) -> str | None:
        category = (
            building.use.get("raw", {}).get("alkis", {}).get("function_type", None)
        )
        if not as_text:
            return category
        return self.code_descriptions.get(category, None)

    def get_matching_locations(
        self, building: builda.NonResidentialBuilding
    ) -> LocationType:
        category = self.get_orig_category(building, False)
        if not category:
            return LocationType()
        return self.location_mapping.get(category, LocationType())


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
