"""A city simulation configuration for the LoadProfileGenerator"""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from pylpg import lpgdata

from cityscenariogenerator import utils


@dataclass
class LPGCityConfig:
    houses: dict[str,]
    city: lpgdata.CityData

    def save(self, path: Path):
        # make sure the directory exists
        path.mkdir(parents=True, exist_ok=True)
        files = list(path.iterdir())
        # check if the directory is empty (besides the logfile)
        if len(files) == 0 or (len(files) == 1 and files[0] == utils.LOGFILENAME):
            raise Exception(f"Target directory was not empty: {path}")
        self.create_house_config_files(path / "houses")
        self.create_global_city_config_file(path)

    def create_house_config_files(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)
        for id, hcj in self.houses.items():
            LPGCityConfig.create_lpg_object_config_file(path, id, hcj)

    def create_global_city_config_file(self, path: Path):
        filename = path / "city.json"
        assert self.city.TravelDefinition is not None, "TravelDefinition is not set"
        if self.city.TravelDefinition.TimeSlotRouteLists:
            # extract routes into a separate file
            LPGCityConfig.create_routes_config_subdir(path, self.city.TravelDefinition)
            # create a copy of the city data, but without the routes
            self.city.TravelDefinition.TimeSlotRouteLists = []
        city_data = self.city.to_json(indent=4)  # type: ignore
        with open(filename, "w+") as f:
            f.write(city_data)

    @staticmethod
    def create_lpg_object_config_file(path: Path, id: str, house: Any):
        filename = path / f"{id}.json"
        house_json = house.to_json(indent=4)
        with open(filename, "w+") as f:
            f.write(house_json)

    @staticmethod
    def create_routes_config_subdir(path: Path, travel_def: lpgdata.TravelDefinition):
        filename = path / "routes/generated_All_0to86400.json"
        filename.parent.mkdir(parents=True, exist_ok=True)
        assert (
            len(travel_def.TimeSlotRouteLists) == 1
        ), "Saving more than one timeslot route is not implemented yet"
        routes = travel_def.TimeSlotRouteLists[0].Routes
        route_dict = {f"{i}": r.to_dict() for i, r in enumerate(routes)}  # type: ignore
        with open(filename, "w+") as f:
            json.dump(route_dict, f, indent=4)
