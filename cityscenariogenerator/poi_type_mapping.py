import abc
import json
from builda_client import dev_client as builda  # type: ignore


class PoiLocationMapper(abc.ABC):
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
        path = "data/nace_code_descriptions.json"
        with open(path, "r") as f:
            nace_to_description = json.load(f)
        path = "data/nace_codes_to_locations.json"
        with open(path, "r") as f:
            description_to_loc = json.load(f)
        combined = {
            nace: description_to_loc[desc]
            for nace, desc in nace_to_description.items()
            if desc in description_to_loc
        }
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


def get_lpg_remote_locations() -> set[str]:
    """
    Returns a list of all LPG locations that are not at home,
    and that therefore requrire a POI.

    :return: list of location names
    """
    with open("data/lpg_remote_locations.txt", "r") as f:
        all_locations = f.read()
    return set(all_locations.splitlines())


def check_nace_to_location_mapping():
    """Checks whether all locations are covered in the mapping, and whether all location names are correct"""
    locations = get_lpg_remote_locations()
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


if __name__ == "__main__":
    check_nace_to_location_mapping()
