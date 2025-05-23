"""Creates configuration files for the LPG out of BuildingData objects generated from BUILDA"""

from collections import defaultdict
import functools
import itertools
import logging
from pathlib import Path
import random
from typing import Iterable
import geopy.distance  # type: ignore
import numpy
from tqdm import tqdm  # type: ignore
from pylpg import lpgdata
from builda_client import dev_client as builda  # type: ignore

from cityscenariogenerator.lpg_locations import LpgLocations
from cityscenariogenerator import (
    poi_type_mapping,
    scenario_statistics,
    household_data,
)
from cityscenariogenerator.plots import building_map, building_map_interactive, population_comparison
from cityscenariogenerator.scenario_params import ScenarioParams
from cityscenariogenerator.city_config import LPGCityConfig


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


@functools.lru_cache
def calc_distance_in_km(c1: lpgdata.Coordinates, c2: lpgdata.Coordinates) -> float:
    """Calculates the distance between two sets of coordinates in km"""
    p1 = (c1.Latitude, c1.Longitude)
    p2 = (c2.Latitude, c2.Longitude)
    dist = geopy.distance.distance(p1, p2)
    return dist.m / 1000  # convert to km


def convert_coordinates(coordinates: builda.Coordinates) -> lpgdata.Coordinates:
    """Convert coordinates from BUILDA format to LPG format"""
    return lpgdata.Coordinates(coordinates.latitude, coordinates.longitude)


def copy_calcspec_file(
    result_directory: Path,
    template_path: Path,
    lpg_result_path: str = "",
    db_file_path: str = "",
):
    """
    Reads the house job template file (which only contains the database path and the
    CalcSpec), adapts some settings if necessary, and saves the new settings to the
    output directory.

    :param result_directory: output directory to save the settings file to
    :param template_path: path to the settings template file, defaults to "calcspec.json"
    :param lpg_result_path: LPG output path to specifiy in the settings
    :param db_file_path: database path to specify in the settings
    """
    # load the template calcspec.json
    with open(template_path, "r") as f:
        lines = f.readlines()
        # remove line comments (which are no valid JSON)
        filtered_lines = [s for s in lines if not s.strip().startswith("//")]
        json_str = "\n".join(filtered_lines)
    house_job: lpgdata.HouseCreationAndCalculationJob = (
        lpgdata.HouseCreationAndCalculationJob.from_json(json_str)  # type: ignore
    )
    assert (
        house_job.CalcSpec is not None
    ), f"No CalcSpec set in the template file: {template_path}"

    # change some settings if necessary
    if lpg_result_path:
        house_job.CalcSpec.OutputDirectory = lpg_result_path
    if db_file_path:
        house_job.PathToDatabase = db_file_path
    # TODO: choose an appropriate GeographicLocation and TemperatureProfile

    # save the adjusted settings to the result directory
    result_json_str: str = house_job.to_json(indent=4)  # type: ignore
    result_file_path = result_directory / "calcspec.json"
    logging.info(f"Saving simulation settings to {result_file_path}")
    with open(result_file_path, "w+") as f:
        f.write(result_json_str)


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

    def __init__(self, params: ScenarioParams) -> None:
        self.params = params

        # set numpy random seed
        numpy_seed = random.randrange(2**32)
        logging.info(f"Using numpy RNG seed {numpy_seed}")
        numpy.random.seed(numpy_seed)

        self.houses: dict[str, lpgdata.HouseCreationAndCalculationJob] = {}
        self.pois: dict[str, lpgdata.PointOfInterestData] = {}
        self.poi_ids_by_type: defaultdict[str, list[str]] = defaultdict(list)
        self.persons_in_each_hh = build_household_person_map()
        self.global_city_definition = lpgdata.CityData()
        self.global_city_definition.TravelDefinition = lpgdata.TravelDefinition()
        self.nonresidential_buildings = 0
        self.excluded_nonres_buildings = 0

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
            str(index),
            f"Generated {household_data.household_name} - {index}",
            charging_station_set,
            transport_device_set,
            None,
            None,
            lpgdata.HouseholdDataSpecificationType.ByTemplateName,
        )

    def add_lpg_house(self, building: household_data.BuildingData) -> lpgdata.HouseData:
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
        hcj = lpgdata.HouseCreationAndCalculationJob(house)
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
        poi_id = f"{location} {building.id}"
        self._add_poi_object(poi_id, poi)
        return poi

    def add_poi(
        self, building_with_type: poi_type_mapping.BuildingWithLocationType
    ) -> None:
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

    def select_residential_poi_for_person(
        self, person: lpgdata.PersonData
    ) -> dict[str, float]:
        """
        Select residentil buildings for locations such as friend's house and turn them into
        POIs. This is a simple workaround as an accurate implementation would require significant
        changes to the LPG city simulation.

        :param person: the person to select residential POIs for
        """
        # assign POIs of every residential type to the person
        poi_weights = {}
        for location in LpgLocations.RESIDENTIAL:
            for i in range(self._determine_poi_num_for_person()):
                # select a random residential building using a uniform distribution
                house_id: str = random.choice(list(self.houses.keys()))
                poi_id = f"{location} {house_id}"

                # check if there already exist a POI for this building-location combination
                if poi_id not in self.pois:
                    # create the POI
                    poi = lpgdata.PointOfInterestData(
                        location, self.houses[house_id].House.Coordinates, None  # type: ignore
                    )
                    self._add_poi_object(poi_id, poi)

                # add the POI with fixed weight
                poi_weights[poi_id] = 1.0
        return poi_weights

    def select_pois_for_person(
        self,
        person: lpgdata.PersonData,
        coordinates: lpgdata.Coordinates,
    ) -> dict[str, float]:
        poi_weights: dict[str, float] = {}
        # select POIs of every available type
        for location, poi_ids in self.poi_ids_by_type.items():
            if location in LpgLocations.RESIDENTIAL:
                continue  # residential POIs are added separately below
            # determine how many POIs of this type the person will select
            size = self._determine_poi_num_for_person()
            size = min(size, len(poi_ids))
            # calculate distances to all POIs of this type
            distances = {
                p: calc_distance_in_km(coordinates, self.pois[p].Coordinates)
                for p in poi_ids
            }
            # randomly select some POIs, using the inverted distances as weights
            if len(distances) > 1 and (distmax := max(distances.values())) > 0:
                # norm the distances to [0, 1] to avoid double precision issues
                distances = {p: d / distmax for p, d in distances.items()}

            weights = {poi: 1 / (d + 0.1) for poi, d in distances.items()}
            weightsum: float = sum(weights.values())
            probabilities = [w / weightsum for w in weights.values()]
            selected_pois: Iterable[str] = numpy.random.choice(
                poi_ids, size=size, replace=False, p=probabilities
            )
            # store the pois with according int weights in the persons preferences
            poi_weights.update({poi_id: weights[poi_id] for poi_id in selected_pois})

        # add residential POIs separately
        res_poi_weights = self.select_residential_poi_for_person(person)
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
        missing = locations - available
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
        with open(self.params.custom_poi_path(), "r") as f:
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

    def create_poi_preferences(self, include_unused_pois: bool = False) -> None:
        if not self.houses:
            raise Exception("No houses have been added yet.")
        if not self.pois:
            raise Exception("No POIs have been added yet.")
        self.check_location_availability()

        logging.info("Creating POI preferences for all persons")
        all_relevant_pois = {}
        for id, hcj in tqdm(self.houses.items()):
            assert hcj.House is not None and hcj.House.Coordinates is not None
            # store all POI that are used by persons in this house
            relevant_pois: dict[str, lpgdata.PointOfInterestData] = {}
            for hh in hcj.House.Households:
                hh_poi_preferences: dict[str, lpgdata.PersonPoiPreferences] = {}
                persons = self._determine_person_in_hh(hh)
                for person in persons:
                    poi_weights = self.select_pois_for_person(
                        person, hcj.House.Coordinates
                    )
                    hh_poi_preferences[person.PersonName] = (  # type: ignore
                        lpgdata.PersonPoiPreferences(poi_weights)
                    )
                    # add selected POIs to the list of used POIs for the house
                    relevant_pois.update(
                        {poi_id: self.pois[poi_id] for poi_id in poi_weights.keys()}
                    )

                hh.PointOfInterestPreferences = hh_poi_preferences

            # save the relevant POIs for this building in a CityData object
            hcj.City = lpgdata.CityData(relevant_pois)
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
        # relevant sites for this person are all of their POIs and their home
        sites = list(pois) + [house_id]
        for poi_id_start in sites:
            for poi_id_end in sites:
                if poi_id_start == poi_id_end:
                    continue
                key = (poi_id_start, poi_id_end, transportation_device.Name)
                if key in existing_routes:
                    continue  # there is already a matching route
                start = self._get_site_coordinates(
                    poi_id_start, house_coordinates, house_id
                )
                end = self._get_site_coordinates(
                    poi_id_end, house_coordinates, house_id
                )
                # calculate the distance of the route
                dist = calc_distance_in_km(start, end)
                category_key = LPGConfigCreator.TRANS_DEVICE_CATEGORY_MAP[
                    transportation_device.Name
                ]
                # create routes in both directions
                existing_routes[key] = lpgdata.RouteData(
                    poi_id_start,
                    poi_id_end,
                    {},
                    {category_key: dist},
                    prob_with_car_hh={category_key: 1},
                    prob_no_car_hh={category_key: 1},
                )
                existing_routes[key] = lpgdata.RouteData(
                    poi_id_end,
                    poi_id_start,
                    {},
                    {category_key: dist},
                    prob_with_car_hh={category_key: 1},
                    prob_no_car_hh={category_key: 1},
                )

    def create_routes_for_testing(self):
        """Creates a set of simple bus routes so that each person can reach all of their POIs. All persons share the same routes."""
        logging.info("Creating routes for all persons")
        all_routes = {}
        for id, hcj in tqdm(self.houses.items()):
            assert hcj.House is not None and hcj.House.Coordinates is not None
            for hh in hcj.House.Households:
                for person, poi_preferences in hh.PointOfInterestPreferences.items():
                    self.add_routes_for_one_person(
                        poi_preferences.PoiWeights.keys(),
                        id,
                        hcj.House.Coordinates,
                        all_routes,
                        lpgdata.TransportationDeviceCategories.Bus_Category,
                    )
        travel_definition = self.global_city_definition.TravelDefinition
        assert travel_definition is not None, "TravelDefinition is not set"

        # use a single timeslot that is always active
        weekdays = {e for e in lpgdata.DayOfWeek}
        time_slot_always = lpgdata.TimeSlot(0, 24 * 60 * 60, weekdays)
        travel_definition.TimeSlotRouteLists = [
            lpgdata.RoutesForTimeSlot(time_slot_always, list(all_routes.values()))
        ]

    def limit_scenario(self, houses: int = 1, households: int = 1):
        """
        Truncates the scenario to only include the specified number of houses and
        households.

        :param houses: max. number of houses, defaults to 1
        :param households: max. number of households per house, defaults to 1
        """
        self.houses = dict(list(self.houses.items())[:houses])
        for house in self.houses.values():
            house.House.Households = house.House.Households[:households]  # type: ignore

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
