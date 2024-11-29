"""Creates configuration files for the LPG out of BuildingData objects generated from BUILDA"""

import json
from pathlib import Path
import random
import shutil
from typing import Any
from pylpg import lpgdata
from builda_client.client import NonResidentialBuildingWithSourceDto, Coordinates

import household_data


class LPGConfigCreator:
    ONE_CAR_TRANSPORT_DEVICE_SETS = [
        lpgdata.TransportationDeviceSets.Bus_and_one_30_km_h_Car,
        lpgdata.TransportationDeviceSets.Bus_and_one_60_km_h_Car,
        lpgdata.TransportationDeviceSets.Bus_and_one_30_km_h_Gasoline_Car,
    ]
    TWO_CAR_TRANSPORT_DEVICE_SETS = [
        lpgdata.TransportationDeviceSets.Bus_and_two_30_km_h_Cars,
        lpgdata.TransportationDeviceSets.Bus_and_two_60_km_h_Cars,
    ]
    # TODO: missing transportation device sets for the following variants
    NO_CAR_TRANSPORT_DEVICE_SETS = ONE_CAR_TRANSPORT_DEVICE_SETS
    MORE_CAR_TRANSPORT_DEVICE_SETS = TWO_CAR_TRANSPORT_DEVICE_SETS

    def __init__(self) -> None:
        self.houses: dict[str, lpgdata.HouseData] = {}
        self.pois: dict[str, lpgdata.PointOfInterestData] = {}
        self.nace_loc_mapping = self.load_nace_location_mapping()

    def load_nace_location_mapping(self) -> dict[str, list[str]]:
        """
        Loads the mapping of nace codes to corresponding descriptions and the
        mapping of nace code descriptions to matching LPG locations, and combines
        both mappings into one.

        :return: mapping dict from nace codes to LPG locations
        """
        path = r"data\nace_code_descriptions.json"
        with open(path, "r") as f:
            nace_to_description = json.load(f)
        path = r"data\nace_codes_to_locations.json"
        with open(path, "r") as f:
            description_to_loc = json.load(f)
        combined = {
            nace: description_to_loc[desc]
            for nace, desc in nace_to_description.items()
            if desc in description_to_loc
        }
        return combined

    def select_transportation_device_set(
        self, household_data: household_data.HouseholdData
    ) -> lpgdata.JsonReference:
        possible_devices = []
        match household_data.num_cars:
            case 0:
                possible_devices = LPGConfigCreator.NO_CAR_TRANSPORT_DEVICE_SETS
            case 1:
                possible_devices = LPGConfigCreator.ONE_CAR_TRANSPORT_DEVICE_SETS
            case 2:
                possible_devices = LPGConfigCreator.TWO_CAR_TRANSPORT_DEVICE_SETS
            case _:
                possible_devices = LPGConfigCreator.MORE_CAR_TRANSPORT_DEVICE_SETS
        return random.choice(possible_devices)

    def select_charging_station_set(
        self, transport_device_set: lpgdata.TransportationDeviceSets
    ) -> lpgdata.JsonReference:
        # select a filling station for the gasoline car
        if (
            transport_device_set
            == lpgdata.TransportationDeviceSets.Bus_and_one_30_km_h_Gasoline_Car
        ):
            return lpgdata.ChargingStationSets.Filling_Station_At_Home
        # select a default set for all other situations
        return lpgdata.ChargingStationSets.Charging_At_Home_with_11_kW

    def create_lpg_household(
        self, index: int, household_data: household_data.HouseholdData
    ):
        hh_template_spec = lpgdata.HouseholdTemplateSpecification(
            HouseholdTemplateName=household_data.household_name
        )
        transport_device_set = self.select_transportation_device_set(household_data)
        charging_station_set = self.select_charging_station_set(transport_device_set)
        poiPreferences = {"personname": lpgdata.PersonPoiPreferences()}
        return lpgdata.HouseholdData(
            None,
            hh_template_spec,
            None,
            str(index),
            str(index),
            charging_station_set,
            transport_device_set,
            None,
            lpgdata.HouseholdDataSpecificationType.ByTemplateName,
            poiPreferences,
        )  # TODO: add PersonPoiPreferences once they are in the python bindings

    def convert_coordinates(self, coordinates: Coordinates) -> lpgdata.Coordinates:
        """Convert coordinates from BUILDA format to LPG format"""
        return lpgdata.Coordinates(coordinates.latitude, coordinates.longitude)

    def add_lpg_house(
        self, id: str, building: household_data.BuildingData
    ) -> lpgdata.HouseData:
        if id in self.houses:
            raise Exception(f"Encountered a duplicate building ID: {id}")

        households = [
            self.create_lpg_household(i, hh) for i, hh in enumerate(building.households)
        ]
        house = lpgdata.HouseData(
            id,
            None,
            self.convert_coordinates(building.coordinates),
            households,
            lpgdata.HouseTypes.HT23_No_Infrastructure_at_all,
        )
        self.houses[id] = house
        return house

    def get_matching_locations(
        self, building: NonResidentialBuildingWithSourceDto
    ) -> list[str]:
        use: dict | None = building.use.value
        if not use:
            return []
        nace_text = use.get("nace_code", "")
        if not nace_text:
            return []
        code = nace_text.split("_")[0]
        return self.nace_loc_mapping[code]

    def select_location(self, building: NonResidentialBuildingWithSourceDto) -> str:
        matching_locations = self.get_matching_locations(building)
        if not matching_locations:
            # use "Employment" locations as default for now
            matching_locations = self.nace_loc_mapping["78"]
        return random.choice(matching_locations)

    def add_poi(
        self, building: NonResidentialBuildingWithSourceDto
    ) -> lpgdata.PointOfInterestData:
        if building.id in self.pois:
            raise Exception(
                f"Encountered a duplicate non-residential building ID: {building.id}"
            )

        location = self.select_location(building)
        timelimit = None
        poi = lpgdata.PointOfInterestData(
            location, self.convert_coordinates(building.coordinates.value), timelimit
        )
        self.pois[building.id] = poi
        return poi

    def create_config_files(self, path: Path, clear_folder: bool = False):
        if path.is_dir() and clear_folder:
            print(f"Clearing directory: {path}")
            shutil.rmtree(path)
        # make sure the directory exists
        path.mkdir(parents=True, exist_ok=True)
        if any(path.iterdir()):
            raise Exception(f"Target directory was not empty: {path}")
        self.create_house_config_files(path / "houses")
        self.create_poi_config_files(path / "POIs")

    def create_house_config_files(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)
        for id, house in self.houses.items():
            self.create_lpg_object_config_file(path, id, house)

    def create_poi_config_files(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)
        for id, poi in self.pois.items():
            self.create_lpg_object_config_file(path, id, poi)

    def create_lpg_object_config_file(self, path: Path, id: str, house: Any):
        filename = path / f"{id}.json"
        house_json = house.to_json(indent=4)
        with open(filename, "w+") as f:
            f.write(house_json)


def check_nace_to_location_mapping():
    """Checks whether all locations are covered in the mapping, and whether all location names are correct"""
    all_locations = """Museum
Dance Studio
Bar Location
Hiking Location
Concert House
Cinema Location
Opera
Dance Club
Cafe
Singing School
Walking Location
Friend's House
Doctors Office
Childrens House
Indoor Swimming Pool
Local Recreational Area
Mountain Road
Running Path
Yoga Studio
Bow Range
Outdoor Swimming Pool
Golf Club
Bicycle Route
Theater
Fishing Location
Soccer Practice Location
Horse Stable
Summer Camp
Musical Society
Parents House
Flea Market Location
Fitness Studio
Festival Location
Hunting Forest
School
School 1
School 2
School 3
Kindergarden
Community College
University
Food Market
Supermarket
Shopping Mall
Car Wash
Office Workplace 1
Office Workplace 2
Workplace (shift worker)
Volunteer Workplace
Home
Office
"""
    locations = all_locations.splitlines()
    print(f"Locations: {len(locations)}")

    print("\nLocations that are not covered yet:")
    mapping = LPGConfigCreator().nace_loc_mapping
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
