"""Class that collects and manages all data while successively building the city scenario."""

from dataclasses import dataclass
import itertools
import logging
import random
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import numpy
from pylpg import lpgdata
from tqdm import tqdm
from builda_client import dev_client as builda

from cityscenariogenerator import (
    deterrence,
    distances,
    household_data,
    poi_type_mapping,
    scenario_statistics,
    utils,
)
from cityscenariogenerator.city_config import LPGCityConfig
from cityscenariogenerator.lpg_locations import (
    LpgLocations,
    location_to_omod_activity_type,
)
from cityscenariogenerator.plots import (
    building_map,
    building_map_interactive,
    poi_numbers,
    population_comparison,
)
from cityscenariogenerator.scenario_params import ScenarioParams


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


def convert_coordinates(coordinates: builda.Coordinates) -> lpgdata.Coordinates:
    """Convert coordinates from BUILDA format to LPG format"""
    return lpgdata.Coordinates(coordinates.latitude, coordinates.longitude)


@dataclass
class ResidentialBuildingList:
    """Simple class to store IDs and corresponding weights
    for sampling residential POIs"""

    ids: list[str]
    weights: list[float]


class LPGConfigCreator:
    ONE_CAR_TRANSPORT_DEVICE_SETS = [
        lpgdata.TransportationDeviceSets.Bus_and_one_30_km_h_Car,
        lpgdata.TransportationDeviceSets.Bus_and_one_60_km_h_Car,
        # lpgdata.TransportationDeviceSets.Bus_and_one_30_km_h_Gasoline_Car,
    ]
    TWO_CAR_TRANSPORT_DEVICE_SETS = [
        lpgdata.TransportationDeviceSets.Bus_and_two_30_km_h_Cars,
        lpgdata.TransportationDeviceSets.Bus_and_two_60_km_h_Cars,
    ]
    NO_CAR_TRANSPORT_DEVICE_SETS = [
        lpgdata.TransportationDeviceSets.Bus_and_Bicycles_no_Car
    ]
    MORE_CAR_TRANSPORT_DEVICE_SETS = [
        lpgdata.TransportationDeviceSets.Bus_and_three_30_km_h_Cars
    ]

    # determine how many POIs of the same location type a person can visit
    MIN_POIS_PER_TYPE = 1
    MAX_POIS_PER_TYPE = 1

    # maps the correct transportation device category names for the Routes definition
    TRANS_DEVICE_CATEGORY_MAP = {
        lpgdata.TransportationDeviceCategories.Bus_Category.Name: "pt",
        lpgdata.TransportationDeviceCategories.Car_Category.Name: "car",
        lpgdata.TransportationDeviceCategories.Bicycle_Category.Name: "bicycle",
        lpgdata.TransportationDeviceCategories.Walking_Category.Name: "walk",
    }

    # persons that are maids in the LPG and require a special location
    MAID_PERSONS = {"CHR19 Jenny"}
    # additional location only for maids
    MAID_LOCATIONS = {"Home"}

    def __init__(self, params: ScenarioParams) -> None:
        self.params = params
        self.houses: dict[str, lpgdata.HouseCreationAndCalculationJob] = {}
        self.pois: dict[str, lpgdata.PointOfInterestData] = {}
        self.poi_ids_by_type: defaultdict[str, list[str]] = defaultdict(list)
        self.persons_in_each_hh = build_household_person_map()
        self.global_city_definition = lpgdata.CityData()
        self.global_city_definition.TravelDefinition = lpgdata.TravelDefinition()
        self.nonresidential_buildings = 0
        self.excluded_nonres_buildings = 0

        #: # probabilities for residential POIs; are initialized during POI choice
        self.residential_building_weights: ResidentialBuildingList | None = None
        self.distcalc: distances.DistanceCalculator | None = None

    def _select_transportation_device_set(
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

    def _select_charging_station_set(
        self, transport_device_set: lpgdata.JsonReference
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
        transport_device_set = self._select_transportation_device_set(household_data)
        charging_station_set = self._select_charging_station_set(transport_device_set)
        return lpgdata.HouseholdData(
            None,
            hh_template_spec,
            None,
            str(index + 1),  # id matches the HH key number assigned by the LPG
            f"Generated {household_data.household_name} - {index}",
            charging_station_set,
            transport_device_set,
            None,
            None,
            lpgdata.HouseholdDataSpecificationType.ByTemplateName,
        )

    def add_lpg_house(self, building: household_data.BuildingData) -> lpgdata.HouseData:
        assert self.residential_building_weights is None, (
            "Cannot add more houses after setting POI preferences"
        )
        if building.id in self.houses:
            raise Exception(f"Encountered a duplicate building ID: {building.id}")

        households = [
            self.create_lpg_household(i, hh) for i, hh in enumerate(building.households)
        ]
        house = lpgdata.HouseData(
            building.id,
            None,
            convert_coordinates(building.coordinates),
            households,
            lpgdata.HouseTypes.HT23_No_Infrastructure_at_all,
        )
        hcj = lpgdata.HouseCreationAndCalculationJob(House=house)
        self.houses[building.id] = hcj
        return house

    def _add_poi_object(self, poi_id: str, poi: lpgdata.PointOfInterestData) -> None:
        """
        Adds a new POI object to the internal dicts, checking for duplicate IDs.

        :param poi_id: the ID of the POI
        :param poi: the POI object to add
        :raises Exception: if there was already a POI with the same ID
        """
        if poi_id in self.pois:
            raise Exception(f"Encountered a duplicate POI ID: {poi_id}")
        assert isinstance(poi.LocationType, str), "Unexpected location type format"
        self.pois[poi_id] = poi
        self.poi_ids_by_type[poi.LocationType].append(poi_id)

    def _add_poi_instance(
        self, building: builda.NonResidentialBuilding, location: str
    ) -> lpgdata.PointOfInterestData:
        timelimit = None
        poi = lpgdata.PointOfInterestData(
            location, convert_coordinates(building.coordinates), timelimit
        )
        # determine the ID of the POI
        poi_id = utils.create_poi_id(building.id, location)
        self._add_poi_object(poi_id, poi)
        return poi

    def add_poi(
        self, building_with_type: poi_type_mapping.BuildingWithLocationType
    ) -> None:
        assert self.residential_building_weights is None, (
            "Cannot add more POIs after setting POI preferences"
        )
        building = building_with_type.building
        if building.id in self.pois:
            raise Exception(
                f"Encountered a duplicate non-residential building ID: {building.id}"
            )
        self.nonresidential_buildings += 1

        locations = building_with_type.collect_lpg_locations()
        if not locations:
            # this building is not relevant for the simulation
            self.excluded_nonres_buildings += 1
            return
        # create one POI for each usage type of the building
        for location in locations:
            self._add_poi_instance(building, location)

    def remove_poi(self, poi_id: str):
        """Removes the POI from the internal POI lists

        :param poi_id: ID of the POI to remove
        """
        assert poi_id in self.pois, f"No POI with the given ID found: {poi_id}"
        poi = self.pois[poi_id]
        assert poi.LocationType
        poi_type = utils.get_jsonref_name(poi.LocationType)
        self.poi_ids_by_type[poi_type].remove(poi_id)
        del self.pois[poi_id]

    def _determine_person_in_hh(
        self, hh: lpgdata.HouseholdData
    ) -> list[lpgdata.PersonData]:
        return self.persons_in_each_hh[hh.HouseholdTemplateSpec.HouseholdTemplateName]  # type: ignore

    def _determine_poi_num_for_person(self) -> int:
        # TODO: use appropriate distributions to determine the number for each POI type
        number = random.randint(
            LPGConfigCreator.MIN_POIS_PER_TYPE, LPGConfigCreator.MAX_POIS_PER_TYPE
        )
        return number

    def select_residential_pois_for_person(
        self, person: lpgdata.PersonData
    ) -> dict[str, float]:
        """
        Select residential buildings for locations such as friend's house and turn them into
        POIs. This is a simple workaround as an accurate implementation would require significant
        changes to the LPG city simulation.

        :param person: the person to select residential POIs for
        """
        # assign POIs of every residential type to the person
        poi_weights = {}
        assert self.residential_building_weights is not None, (
            "Residential POI weights not initialized yet"
        )

        residential_pois = LpgLocations.RESIDENTIAL.copy()
        # custom behavior for maids: add the Home location
        if person.PersonName in LPGConfigCreator.MAID_PERSONS:
            residential_pois |= LPGConfigCreator.MAID_LOCATIONS

        for location in residential_pois:
            # select a random residential building using a uniform distribution
            num_houses = self._determine_poi_num_for_person()
            selected_houses = numpy.random.choice(
                self.residential_building_weights.ids,
                num_houses,
                p=self.residential_building_weights.weights,
            )
            for house_id in selected_houses:
                poi_id = utils.create_poi_id(house_id, location)

                # check if there already exist a POI for this building-location combination
                if poi_id not in self.pois:
                    # create the POI
                    poi = lpgdata.PointOfInterestData(
                        location,
                        self.houses[house_id].House.Coordinates,  # type: ignore
                        None,
                    )
                    self._add_poi_object(poi_id, poi)

                # add the POI with fixed weight
                poi_weights[poi_id] = 1.0
        return poi_weights

    def select_pois_for_person(
        self,
        person: lpgdata.PersonData,
        house_id: str,
    ) -> dict[str, float]:
        assert self.distcalc is not None
        poi_weights: dict[str, float] = {}
        # select POIs of every available type
        for location, poi_ids in self.poi_ids_by_type.items():
            if location in LpgLocations.RES_AND_SPECIAL:
                continue  # residential POIs are added separately below
            # determine how many POIs of this type the person will select
            size = self._determine_poi_num_for_person()
            size = min(size, len(poi_ids))
            # calculate distances to all POIs of this type
            distances = {
                p: self.distcalc.get_distance_in_km(house_id, p) for p in poi_ids
            }

            activity_type = location_to_omod_activity_type(location)
            # use a minimum distance, as the deterrence function cannot work with distance 0
            MIN_DISTANCE_IN_KM = 0.05
            # calculate destination weights using the OMOD deterrence function
            weights = {
                p: deterrence.omod_deterrence(
                    max(d, MIN_DISTANCE_IN_KM),
                    activity_type,
                )
                for p, d in distances.items()
            }

            weightsum: float = sum(weights.values())
            probabilities = [w / weightsum for w in weights.values()]
            selected_pois: Iterable[str] = numpy.random.choice(
                poi_ids, size=size, replace=False, p=probabilities
            )
            # store the pois with according int weights in the persons preferences
            poi_weights.update({poi_id: weights[poi_id] for poi_id in selected_pois})

        # add residential POIs separately
        res_poi_weights = self.select_residential_pois_for_person(person)
        poi_weights.update(res_poi_weights)
        return poi_weights

    def _get_site_coordinates(
        self, building_id: str, house_coordinates: lpgdata.Coordinates, house_id: str
    ) -> lpgdata.Coordinates:
        """
        Returns the coordinates of a building depending on its type. Either looks up
        the corresponding POI, or, if the building is the home of the person, returns
        the house coordinates.

        :param building_id: ID of the building to get coordinates for (POI or house)
        :param house_coordinates: coordinates of the house to use
        :param house_id: ID of the house the person lives in
        :return: coordinates of the specified building
        """
        if building_id == lpgdata.Sites.Home.Name or building_id == house_id:
            return house_coordinates
        return self.pois[building_id].Coordinates  # type: ignore

    def check_location_availability(self) -> None:
        """
        Checks if there is at least one POI for every LPG location. If locations are missing,
        households that require them cannot be simulated.
        """
        locations = LpgLocations.NON_RESIDENTIAL
        available = self.poi_ids_by_type.keys()
        # special locations are not required for every household
        missing = locations - available - LpgLocations.SPECIAL
        if missing:
            raise Exception(
                f"The following {len(missing)} locations are not covered by any POI: {missing}"
            )

    def load_and_add_custom_pois(self) -> None:
        """
        Loads additional custom POIs from a file and adds them to the
        list of available POIs. This can be helpful if the target city does
        not contain certain POI types and people need to go to specific POIs in
        the surrounding area for the corresponding activities.
        """
        # load the custom POIs from file
        with open(self.params.custom_poi_path(), "r", encoding="utf8") as f:
            json_str = f.read()
            poi_dict = lpgdata.CityData.from_json(json_str).PointsOfInterest  # type: ignore
        # add them to the POIs stored in the attributes
        for id, poi in poi_dict.items():
            if id in self.pois:
                if self.pois[id].LocationType != poi.LocationType:
                    raise Exception(
                        f"Custom POI with duplicate ID and different type: {id}"
                    )
                logging.warning(
                    f"Loaded a custom POI with the same ID as an existing POI: {id}"
                )
            else:
                self.poi_ids_by_type[poi.LocationType].append(id)
        self.pois.update(poi_dict)
        logging.info(f"Loaded {len(poi_dict)} custom POIs")

    def _calc_residential_poi_probabilities(self) -> None:
        """Calculates probabilities for choosing a house as a residential POI
        for activities like visiting a friend.
        """
        house_ids = list(self.houses.keys())
        # simplification for better performance: only use part of the houses for residential POIs
        # house_ids = house_ids[::10]

        # weight houses depending on the number of households
        hhs_per_house = [
            len(self.houses[id].House.Households)  # type: ignore
            for id in house_ids
        ]
        total_hh = sum(hhs_per_house)
        weights = [i / total_hh for i in hhs_per_house]
        self.residential_building_weights = ResidentialBuildingList(house_ids, weights)

    def create_poi_preferences(
        self, generate_test_routes: bool = False, include_unused_pois: bool = False
    ) -> None:
        if not self.houses:
            raise Exception("No houses have been added yet.")
        if not self.pois:
            raise Exception("No POIs have been added yet.")
        self.check_location_availability()
        self._calc_residential_poi_probabilities()
        self.distcalc = distances.DistanceCalculator(
            self.houses, self.pois, generate_test_routes
        )

        logging.info("Creating POI preferences for all persons.")
        all_relevant_pois = {}
        for id, hcj in tqdm(self.houses.items()):
            assert hcj.House is not None and hcj.House.Coordinates is not None
            # store all POI that are used by persons in this house
            relevant_pois: dict[str, lpgdata.PointOfInterestData] = {}
            for hh in hcj.House.Households:
                hh_poi_preferences: dict[str, lpgdata.PersonPoiPreferences] = {}
                persons = self._determine_person_in_hh(hh)
                for person in persons:
                    poi_weights = self.select_pois_for_person(person, id)
                    hh_poi_preferences[person.PersonName] = (  # type: ignore
                        lpgdata.PersonPoiPreferences(poi_weights)
                    )
                    # add selected POIs to the list of used POIs for the house
                    relevant_pois.update(
                        {poi_id: self.pois[poi_id] for poi_id in poi_weights.keys()}
                    )

                hh.PointOfInterestPreferences = hh_poi_preferences

            # save the relevant POIs for this building in a CityData object
            hcj.City = lpgdata.CityData(PointsOfInterest=relevant_pois)
            all_relevant_pois.update(relevant_pois)
        logging.info(
            f"{len(self.pois) - len(all_relevant_pois)} POIs are not visited by anyone."
        )
        if include_unused_pois:
            # include all POIs read from BUILDA
            self.global_city_definition.PointsOfInterest = self.pois
        else:
            # only include POIs that are actually used by at least one person
            self.global_city_definition.PointsOfInterest = all_relevant_pois

    def add_routes_for_one_person(
        self,
        pois: Iterable[str],
        house_id: str,
        house_coordinates: lpgdata.Coordinates,
        existing_routes: dict[tuple, lpgdata.RouteData],
        transportation_device: lpgdata.JsonReference = lpgdata.TransportationDeviceCategories.Bus_Category,
    ) -> None:
        """Creates simple dummy routes from every POI to every other one, if they don't exist yet"""
        assert self.distcalc is not None
        # relevant sites for this person are all of their POIs and their home
        sites = list(pois) + [house_id]
        for id_start in sites:
            for id_end in sites:
                if id_start == id_end:
                    continue
                key = (id_start, id_end, transportation_device.Name)
                if key in existing_routes:
                    continue  # there is already a matching route

                # calculate the distance of the route
                dist = self.distcalc.get_distance_in_km(id_start, id_end)
                category_key = LPGConfigCreator.TRANS_DEVICE_CATEGORY_MAP[
                    transportation_device.Name
                ]
                # create routes in both directions
                existing_routes[key] = lpgdata.RouteData(
                    id_start,
                    id_end,
                    {},
                    {category_key: dist},
                    prob_with_car_hh={category_key: 1},
                    prob_no_car_hh={category_key: 1},
                )
                existing_routes[key] = lpgdata.RouteData(
                    id_end,
                    id_start,
                    {},
                    {category_key: dist},
                    prob_with_car_hh={category_key: 1},
                    prob_no_car_hh={category_key: 1},
                )

    def create_routes_for_testing(self):
        """Creates a set of simple bus routes so that each person can reach all of their
        POIs. All persons share the same routes."""
        logging.info("Creating routes for all persons")
        assert self.distcalc and self.distcalc.all_distances, (
            "In order to create testing routes, the DistanceCalculator must be configured"
            " to create the full matrix with all_distances=True"
        )
        all_routes = {}
        for id, hcj in tqdm(self.houses.items()):
            assert hcj.House is not None and hcj.House.Coordinates is not None
            for hh in hcj.House.Households:
                for person, poi_preferences in hh.PointOfInterestPreferences.items():
                    # check if the household has a car or not
                    no_car = (
                        hh.TransportationDeviceSet
                        in LPGConfigCreator.NO_CAR_TRANSPORT_DEVICE_SETS
                    )
                    # create car routes for households with a car and bus routes for those without
                    device_cat = (
                        lpgdata.TransportationDeviceCategories.Bus_Category
                        if no_car
                        else lpgdata.TransportationDeviceCategories.Car_Category
                    )
                    self.add_routes_for_one_person(
                        poi_preferences.PoiWeights.keys(),
                        id,
                        hcj.House.Coordinates,
                        all_routes,
                        device_cat,
                    )
        travel_definition = self.global_city_definition.TravelDefinition
        assert travel_definition is not None, "TravelDefinition is not set"

        # use a single timeslot that is always active
        weekdays = {e for e in lpgdata.DayOfWeek}
        time_slot_always = lpgdata.TimeSlot(0, 24 * 60 * 60, weekdays)
        travel_definition.TimeSlotRouteLists = [
            lpgdata.RoutesForTimeSlot(time_slot_always, list(all_routes.values()))
        ]

    def limit_scenario(
        self,
        houses: int | None = None,
        households: int | None = None,
        pois_per_type: int | None = None,
    ):
        """Truncates the scenario to only include the specified number of houses,
        households, and POIs per type.

        :param houses: max. number of houses, unlimited by default
        :param households: max. number of households per house, unlimited by default
        :param pois_per_type: max. number of POIs per type, unlimited by default
        """
        self.houses = dict(list(self.houses.items())[:houses])
        for house in self.houses.values():
            house.House.Households = house.House.Households[:households]  # type: ignore

        if houses is not None and self.residential_building_weights:
            # refresh the building weights
            self._calc_residential_poi_probabilities()

        # limit the POIs
        for poi_type in self.poi_ids_by_type.keys():
            self.poi_ids_by_type[poi_type] = self.poi_ids_by_type[poi_type][
                :pois_per_type
            ]
        all_poi_ids = {id for idlist in self.poi_ids_by_type.values() for id in idlist}
        self.pois = {id: poi for id, poi in self.pois.items() if id in all_poi_ids}

    def add_default_queuecapacity(self, poi_type: str, capacity: int):
        """Sets QueueCapacity for all POIs of a certain type to the specified value.

        :param poi_type: the POI type to adapt
        :param capacity: the queue capacity to set
        """
        logging.info(f"Setting QueueCapacity for {poi_type} POIs to {capacity}")
        for poi_id in self.poi_ids_by_type[poi_type]:
            self.pois[poi_id].QueueCapacity = capacity

    def create_config_files(self) -> LPGCityConfig:
        path = self.params.result_directory
        city_config = LPGCityConfig(self.houses, self.global_city_definition)
        city_config.save(path)

        # create statistics and plots describing the scenario
        self.create_scenario_statistics(path / "statistics")
        self.create_plots(path / "plots")
        return city_config

    def create_scenario_statistics(self, path: Path):
        """
        Write statistics about this scenario

        :param path: path for the statistics files
        """
        logging.info(
            f"Excluded {self.excluded_nonres_buildings} of {self.nonresidential_buildings} non-residential buildings."
        )
        logging.info(f"Generated {len(self.pois)} POIs.")

        path.mkdir(parents=True, exist_ok=True)
        scenario_statistics.write_general_info(
            self.houses.values(), self.pois.values(), path
        )
        scenario_statistics.write_household_statistics(self.houses.values(), path)
        scenario_statistics.write_person_statistics(self.houses.values(), path)
        scenario_statistics.write_persons_per_house(self.houses.values(), path)
        scenario_statistics.write_household_sizes(self.houses.values(), path)
        scenario_statistics.write_info_for_each_hh(self.houses.values(), path)
        scenario_statistics.write_car_numbers(self.houses.values(), path)
        scenario_statistics.write_poi_statistics(
            self.global_city_definition.PointsOfInterest.values(),
            path,
            "poi_types_relevant",
        )
        scenario_statistics.write_poi_statistics(
            self.pois.values(), path, "poi_types_all"
        )
        all_routes = itertools.chain.from_iterable(
            r.Routes
            for r in self.global_city_definition.TravelDefinition.TimeSlotRouteLists  # type: ignore
        )
        scenario_statistics.write_route_statistics(all_routes, path)

    def create_plots(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)

        all_pois = [
            building_map.PointWithCategory(poi.Coordinates, poi.LocationType)  # type: ignore
            for id, poi in self.pois.items()
        ]
        building_map.map_locations_plot(all_pois, path)
        building_map_interactive.map_locations_plot_html(all_pois, path)
        population_comparison.population_statistics(self.params, path)
        poi_numbers.plot_poi_numbers(self.params, path)
