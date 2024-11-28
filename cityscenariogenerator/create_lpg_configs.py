"""Creates configuration files for the LPG out of BuildingData objects generated from BUILDA"""

from pathlib import Path
import random
from pylpg import lpgdata

import household_data


class LPGConfigCreator:
    # TODO: missing transportation device sets for other
    ONE_CAR_TRANSPORT_DEVICE_SETS = [
        lpgdata.TransportationDeviceSets.Bus_and_one_30_km_h_Car,
        lpgdata.TransportationDeviceSets.Bus_and_one_60_km_h_Car,
        lpgdata.TransportationDeviceSets.Bus_and_one_30_km_h_Gasoline_Car,
    ]
    TWO_CAR_TRANSPORT_DEVICE_SETS = [
        lpgdata.TransportationDeviceSets.Bus_and_two_30_km_h_Cars,
        lpgdata.TransportationDeviceSets.Bus_and_two_60_km_h_Cars,
    ]
    MORE_CAR_TRANSPORT_DEVICE_SETS = TWO_CAR_TRANSPORT_DEVICE_SETS
    NO_CAR_TRANSPORT_DEVICE_SETS = ONE_CAR_TRANSPORT_DEVICE_SETS

    def __init__(self) -> None:
        self.houses: dict[str, lpgdata.HouseData] = {}

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
        )

    def add_lpg_house(
        self, id: str, building: household_data.BuildingData
    ) -> lpgdata.HouseData:
        if id in self.houses:
            raise Exception(f"Encountered a duplicate building ID: {id}")

        households = [
            self.create_lpg_household(i, hh) for i, hh in enumerate(building.households)
        ]
        house = lpgdata.HouseData(
            id, None, households, lpgdata.HouseTypes.HT23_No_Infrastructure_at_all
        )
        self.houses[id] = house
        return house

    def create_house_config_file(self, path: Path, id: str, house: lpgdata.HouseData):
        filename = path / f"{id}.json"
        house_json = house.to_json(indent=4)
        with open(filename, "w+") as f:
            f.write(house_json)

    def create_house_config_files(self, path: Path, clear_folder: bool = False):
        path.mkdir(parents=True, exist_ok=True)
        if any(path.iterdir()) and not clear_folder:
            raise Exception(f"Target directory was not empty: {path}")

        for id, house in self.houses.items():
            self.create_house_config_file(path, id, house)
