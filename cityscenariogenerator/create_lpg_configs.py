"""Creates configuration files for the LPG out of BuildingData objects generated from BUILDA"""

from collections import defaultdict
import itertools
import json
import logging
import math
from pathlib import Path
import random
import shutil
from typing import Any, Iterable
import geopy
import geopy.distance
import numpy
from pylpg import lpgdata
from builda_client import client as builda

import household_data


def load_nace_location_mapping() -> dict[str, list[str]]:
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


def build_household_person_map() -> dict[str, list[lpgdata.PersonData]]:
    """
    Generates a dict that maps each household template name to
    a list of persons in this template.

    :return: dict with a list of occupants for each household template
    """
    persons = [
        getattr(lpgdata.TemplatePersons, p)
        for p in dir(lpgdata.TemplatePersons)
        if not p.startswith("__")
    ]
    # adapt the household template names to fit to the usual
    return {k: list(g) for k, g in itertools.groupby(persons, lambda p: p.TemplateName)}


def calc_distance(c1: lpgdata.Coordinates, c2: lpgdata.Coordinates) -> float:
    """Calculates euclidean distance between two sets of coordinates in m"""
    # TODO: implement a geographically correct distance function
    # return math.dist([c1.Latitude, c1.Longitude], [c2.Latitude, c2.Longitude])
    p1 = (c1.Latitude, c1.Longitude)
    p2 = (c2.Latitude, c2.Longitude)
    dist = geopy.distance.distance(p1, p2)
    return dist.m


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

    # determine how many POIs of the same location type a person can visit
    MIN_POIS_PER_TYPE = 1
    MAX_POIS_PER_TYPE = 2

    def __init__(self) -> None:
        self.houses: dict[str, lpgdata.HouseCreationAndCalculationJob] = {}
        self.pois: dict[str, lpgdata.PointOfInterestData] = {}
        self.poi_ids_by_type: defaultdict[str, list[str]] = defaultdict(list)
        self.nace_loc_mapping = load_nace_location_mapping()
        self.persons_in_each_hh = build_household_person_map()
        self.global_city_definition = lpgdata.CityData()

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
            None,
            lpgdata.HouseholdDataSpecificationType.ByTemplateName,
        )

    def convert_coordinates(
        self, coordinates: builda.Coordinates
    ) -> lpgdata.Coordinates:
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
        hcj = lpgdata.HouseCreationAndCalculationJob(house)
        self.houses[id] = hcj
        return house

    def get_matching_locations(
        self, building: builda.NonResidentialBuildingWithSourceDto
    ) -> list[str]:
        use: dict | None = building.use.value
        if not use:
            return []
        nace_text = use.get("nace_code", "")
        if not nace_text:
            return []
        code = nace_text.split("_")[0]
        return self.nace_loc_mapping[code]

    def select_location(
        self, building: builda.NonResidentialBuildingWithSourceDto
    ) -> str:
        matching_locations = self.get_matching_locations(building)
        if not matching_locations:
            # use "Employment" locations as default for now
            matching_locations = self.nace_loc_mapping["78"]
        return random.choice(matching_locations)

    def add_poi(
        self, building: builda.NonResidentialBuildingWithSourceDto
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
        # determine the ID of the POI
        poi_id = f"{location} {building.id}"
        self.pois[poi_id] = poi
        self.poi_ids_by_type[location].append(poi_id)
        return poi

    def determine_person_in_hh(
        self, hh: lpgdata.HouseholdData
    ) -> list[lpgdata.PersonData]:
        return self.persons_in_each_hh[hh.HouseholdTemplateSpec.HouseholdTemplateName]

    def get_poi_distances(
        self,
        coordinates: lpgdata.Coordinates,
        poi_list: list[lpgdata.PointOfInterestData],
    ):
        return [calc_distance(coordinates, p.Coordinates) for p in poi_list]

    def select_pois_for_person(
        self,
        person: lpgdata.PersonData,
        coordinates: lpgdata.Coordinates,
        has_car: bool = True,
    ) -> dict[str, int]:
        poi_weights = {}
        for location, poi_ids in self.poi_ids_by_type.items():
            # determine how many POIs of this type the person will select
            size = random.randint(
                LPGConfigCreator.MIN_POIS_PER_TYPE, LPGConfigCreator.MAX_POIS_PER_TYPE
            )
            size = min(size, len(poi_ids))
            # calculate distances to all POIs of this type
            distances = {
                p: calc_distance(coordinates, self.pois[p].Coordinates) for p in poi_ids
            }
            # randomly select some POIs, using the inverted distances as weights
            if len(distances) > 1:
                # norm the distances to [0, 1] to avoid double precision issues
                distmax: float = max(distances.values())
                distances = {p: d / distmax for p, d in distances.items()}

            weights = {poi: 1 / (d + 0.1) for poi, d in distances.items()}
            weightsum: float = sum(weights.values())
            probabilities = [w / weightsum for w in weights.values()]
            selected_pois: Iterable[lpgdata.PointOfInterestData] = numpy.random.choice(
                poi_ids, size=size, replace=False, p=probabilities
            )
            # store the pois with according int weights in the persons preferences
            poi_weights.update({poi_id: weights[poi_id] for poi_id in selected_pois})
        return poi_weights

    def _get_site_coordinates(
        self, site_name: str, house_coordinates: lpgdata.Coordinates
    ) -> lpgdata.Coordinates:
        if site_name == lpgdata.Sites.Home.Name:
            return house_coordinates
        return self.pois[site_name].Coordinates

    def create_random_routes_for_testing(
        self, pois: Iterable[str], house_coordinates: lpgdata.Coordinates
    ) -> list[lpgdata.RouteData]:
        """Creates simple dummy routes from every POI to every other one."""
        routes = []
        sites = list(pois) + [lpgdata.Sites.Home.Name]
        for poi_id_start in sites:
            for poi_id_end in sites:
                if poi_id_start == poi_id_end:
                    continue
                start = self._get_site_coordinates(poi_id_start, house_coordinates)
                end = self._get_site_coordinates(poi_id_end, house_coordinates)
                # the LPG expects integer distances
                dist = int(calc_distance(start, end))
                routes.append(
                    lpgdata.RouteData(
                        poi_id_start,
                        poi_id_end,
                        dist,
                        0,
                        lpgdata.TransportationDeviceCategories.Bus_Category,
                        1,
                    )
                )
        return routes

    def create_poi_preferences(self):
        if not self.houses:
            raise Exception("No houses have been added yet.")
        if not self.pois:
            raise Exception("No POIs have been added yet.")

        all_relevant_pois = {}
        for id, hcj in self.houses.items():
            # store all POI that are used by persons in this house
            relevant_pois: dict[str, lpgdata.PointOfInterestData] = {}
            for hh in hcj.House.Households:
                hh_poi_preferences: dict[str, lpgdata.PersonPoiPreferences] = {}
                persons = self.determine_person_in_hh(hh)
                for person in persons:
                    poi_weights = self.select_pois_for_person(
                        person, hcj.House.Coordinates
                    )
                    hh_poi_preferences[person.PersonName] = (
                        lpgdata.PersonPoiPreferences(poi_weights, [], True)
                    )
                    # add selected POIs to the list of used POIs for the house
                    relevant_pois.update(
                        {poi_id: self.pois[poi_id] for poi_id in poi_weights.keys()}
                    )

                # set routes now that all relevant POIs for the household are known
                relevant_pois_for_hh = {
                    poi
                    for pref in hh_poi_preferences.values()
                    for poi in pref.PoiWeights.keys()
                }
                for person in persons:
                    hh_poi_preferences[person.PersonName].Routes = (
                        self.create_random_routes_for_testing(
                            relevant_pois_for_hh, hcj.House.Coordinates
                        )
                    )

                hh.PointOfInterestPreferences = hh_poi_preferences
            # save the relevant POIs for this building in a CityData object
            hcj.City = lpgdata.CityData(relevant_pois)
            all_relevant_pois.update(relevant_pois)
        logging.info(
            f"{len(self.pois) - len(all_relevant_pois)} POIs are not visited by anyone."
        )
        self.global_city_definition.PointsOfInterest = all_relevant_pois

    def create_config_files(self, path: Path, clear_folder: bool = False):
        if path.is_dir() and clear_folder:
            logging.info(f"Clearing directory: {path}")
            shutil.rmtree(path)
        # make sure the directory exists
        path.mkdir(parents=True, exist_ok=True)
        if any(path.iterdir()):
            raise Exception(f"Target directory was not empty: {path}")
        self.create_house_config_files(path / "houses")
        # self.create_poi_config_files(path / "POIs")
        self.create_global_city_config_file(path)

    def create_house_config_files(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)
        for id, hcj in self.houses.items():
            self.create_lpg_object_config_file(path, id, hcj)

    def create_poi_config_files(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)
        for id, poi in self.pois.items():
            self.create_lpg_object_config_file(path, id, poi)

    def create_lpg_object_config_file(self, path: Path, id: str, house: Any):
        filename = path / f"{id}.json"
        house_json = house.to_json(indent=4)
        with open(filename, "w+") as f:
            f.write(house_json)

    def create_global_city_config_file(self, path: Path):
        filename = path / "city.json"
        city_data = self.global_city_definition.to_json(indent=4)
        with open(filename, "w+") as f:
            f.write(city_data)


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
