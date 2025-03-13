from typing import Iterable

from builda_client.dev_client import NonResidentialBuilding  # type: ignore
import pylpg.lpgpythonbindings  # type: ignore

from cityscenariogenerator.plots import building_map_interactive


def get_category(building: NonResidentialBuilding) -> str:
    # return building.use.get("raw", {}).get("alkis", {}).get("description", "None")
    return building.use.get("raw", {}).get("osm", {}).get("amenity", "None")


def alkis_type_map_plot(
    scenario_directory, nonres_buildings: Iterable[NonResidentialBuilding]
):
    """
    Generates a map showing the location of non-residential buildings and their ALKIS type.

    :param scenario_directory: the directory whrere the map will be saved
    :param nonres_buildings: the collection of non-residential buildings
    """
    scenario_directory.mkdir(parents=True, exist_ok=True)
    points = [
        building_map_interactive.PointWithCategory(
            pylpg.lpgpythonbindings.Coordinates(
                b.coordinates.latitude, b.coordinates.longitude
            ),
            get_category(b),
        )
        for b in nonres_buildings
    ]
    building_map_interactive.map_locations_plot_html(points, scenario_directory)
