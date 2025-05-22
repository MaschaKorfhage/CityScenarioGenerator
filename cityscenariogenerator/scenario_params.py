from dataclasses import dataclass
import logging
from pathlib import Path

from cityscenariogenerator import utils

#: directory with additional input data for specific scenarios
SCENARIO_INPUTS_DIR = Path("scenario_inputs")


@dataclass
class ScenarioParams:
    """Stores all parameters for a generating a scenario"""

    builda_query: dict[str, str]
    result_directory: Path
    lpg_result_path: Path

    def __post_init__(self):
        self.query_str = utils.descriptive_query_text(self.builda_query)

    def check_input_data(self) -> bool:
        """
        Checks if the scenario input directory exists and contains
        all required files.
        """
        # check if all required input files exist
        if not self.input_data_dir().is_dir():
            logging.warning(
                f"Scenario input directory not found: {self.input_data_dir()}"
            )
            return False
        if not self.custom_poi_path().is_dir():
            logging.warning(f"Custom POI file not found: {self.custom_poi_path()} ")
            return False
        if not self.osm_input_path().is_dir():
            logging.warning(f"OSM input file not found: {self.input_data_dir()}")
            return False
        return True

    def input_data_dir(self) -> Path:
        return SCENARIO_INPUTS_DIR / self.get_city()

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


class DummyParams(ScenarioParams):
    """
    Dummy class for testing purposes.
    This class uses a simple default custom POI file.
    """

    def input_data_dir(self) -> Path:
        """Always return the dummy input data directory."""
        return Path(SCENARIO_INPUTS_DIR / "testing")


def get_params(
    builda_query: dict[str, str], result_directory: Path, lpg_result_path: Path
) -> ScenarioParams:
    """
    Returns a scenario parameters object for the given query and directories.

    :param builda_query: the builda query for the scenario
    :param result_directory: the directory to save the scenario to
    :param lpg_result_path: the output path for the LPG
    :return: the scenario parameters
    """
    params = ScenarioParams(builda_query, result_directory, lpg_result_path)
    if params.check_input_data():
        return params
    logging.warning(
        "No valid scenario input data for query '{params.query_str}' found. Using dummy data."
    )
    return DummyParams(builda_query, result_directory, lpg_result_path)
