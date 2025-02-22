from typing import Iterable
from cityscenariogenerator.plots import building_map_interactive
from cityscenariogenerator.builda_client_import import NonResidentialBuilding

import pylpg.lpgpythonbindings  # type: ignore


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
            # b.use.get("raw", {}).get("alkis", {}).get("description", "None"),
            b.use.get("raw", {}).get("osm", {}).get("amenity", "None"),
        )
        for b in nonres_buildings
    ]
    building_map_interactive.map_locations_plot_html(points, scenario_directory)
