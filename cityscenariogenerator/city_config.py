"""A city simulation configuration for the LoadProfileGenerator"""

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any
from pylpg import lpgdata

from cityscenariogenerator import utils
from tqdm import tqdm


@dataclass
class LPGCityConfig:
    """A city configuration for the LoadProfileGenerator"""

    houses: dict[str, lpgdata.HouseCreationAndCalculationJob]
    city: lpgdata.CityData

    def save(self, path: Path):
        """
        Save the LPGCityConfig as a directory, containing files for
        houses, routes, and the city definition.

        :param path: the directory to save the config to
        :raises Exception: if the target directory was not empty
        """
        # make sure the directory exists
        path.mkdir(parents=True, exist_ok=True)
        files = list(path.iterdir())
        # check if the directory is empty (besides the logfile)
        if len(files) == 0 or (len(files) == 1 and files[0] == utils.LOGFILENAME):
            raise Exception(f"Target directory was not empty: {path}")
        self.create_house_config_files(path / "houses")
        self.create_global_city_config_file(path)
        self.create_house_coordinates_dict(path)

    def create_house_config_files(self, path: Path):
        """Creates all house config files for the LoadProfileGenerator.

        :param path: the directory to store the house files in
        """
        path.mkdir(parents=True, exist_ok=True)
        for id, hcj in self.houses.items():
            LPGCityConfig.create_lpg_object_config_file(path, id, hcj)

    def create_global_city_config_file(self, path: Path):
        """Creates the city config file containing all POIs and optionally
        travel data.

        :param path: the directory to save the file to
        """
        filename = path / "city.json"
        assert self.city.TravelDefinition is not None, "TravelDefinition is not set"
        if self.city.TravelDefinition.TimeSlotRouteLists:
            # extract routes into a separate file
            LPGCityConfig.create_routes_config_subdir(path, self.city.TravelDefinition)
            # create a copy of the city data, but without the routes
            self.city.TravelDefinition.TimeSlotRouteLists = []
        city_data = self.city.to_json(indent=4)  # type: ignore
        with open(filename, "w", encoding="utf8") as f:
            f.write(city_data)

    def create_house_coordinates_dict(self, path: Path):
        """Creates a JSON file containing every house and its coordinates.

        :param path: path of the scenario directory
        """
        house_coordinates = {
            id: house.House.Coordinates.to_dict()  # type: ignore
            for id, house in self.houses.items()
        }
        with open(path / "house_coordinates.json", "w", encoding="utf8") as f:
            json.dump(house_coordinates, f, indent=4)

    @staticmethod
    def create_lpg_object_config_file(path: Path, id: str, house: Any):
        filename = path / f"{id}.json"
        house_json = house.to_json(indent=4)
        with open(filename, "w", encoding="utf8") as f:
            f.write(house_json)

    @staticmethod
    def create_routes_config_subdir(path: Path, travel_def: lpgdata.TravelDefinition):
        filename = path / "routes/generated_All_0to86400.json"
        filename.parent.mkdir(parents=True, exist_ok=True)
        assert len(travel_def.TimeSlotRouteLists) == 1, (
            "Saving more than one timeslot route is not implemented yet"
        )
        routes = travel_def.TimeSlotRouteLists[0].Routes
        route_dict = {f"{i}": r.to_dict() for i, r in enumerate(routes)}  # type: ignore
        with open(filename, "w", encoding="utf8") as f:
            json.dump(route_dict, f, indent=4)

    @staticmethod
    def load(path: Path):
        """
        Loads an LPGCityConfig from the specified directory

        :param path: the directory including the config files
        :return: the loaded LPGCityConfig
        """
        assert path.is_dir(), f"{path} is no directory, cannot load city config"
        logging.info(f"Loading a city scenario from {path}. This might take a while.")

        # load all houses
        houses_subdir = path / "houses"
        house_files = list(houses_subdir.iterdir())
        houses = {}
        for file in tqdm(house_files):
            # filepath = houses_subdir / filename
            with open(file, "r", encoding="utf8") as f:
                filetext = f.read()
            houses[file.stem] = lpgdata.HouseCreationAndCalculationJob.from_json(  # type: ignore
                filetext
            )

        # load city definition with POIs
        with open(path / "city.json", "r", encoding="utf8") as f:
            filetext = f.read()
        city = lpgdata.CityData.from_json(filetext)  # type: ignore

        # load additional routes from separate files
        routes_subdir = path / "routes"
        if routes_subdir.is_dir():
            logging.warning("Loading city config routes not implemented yet.")
            # TODO: include routes and location clustering file if present

        return LPGCityConfig(houses, city)
