from dataclasses import dataclass
from pathlib import Path


@dataclass
class ScenarioParams:
    """Stores all parameters for a generating a scenario"""

    builda_query: dict[str, str]
    result_directory: Path
    lpg_result_path: Path

    def __post_init__(self):
        # check if all required input files exist
        path = self.custom_poi_path()
        assert path.is_file(), f"Custom POI file not found: {path}"
        path = self.osm_input_path()
        assert path.is_file(), f"OSM input file not found: {path}"

    def input_data_dir(self) -> Path:
        return Path("data/custom_input") / self.get_city()

    def custom_poi_path(self) -> Path:
        return self.input_data_dir() / "custom_pois.json"

    def osm_input_path(self) -> Path:
        return self.input_data_dir() / "osm_nonres_nodes.geojson"

    def get_city(self) -> str:
        """
        Returns the name of the city of this scenario.

        :raises Exception: if the query contains no city
        :return: the name of the city
        """
        if not (city := self.builda_query.get("city")):
            raise Exception(f"No city was specified in the query: {self.builda_query}")
        return city
