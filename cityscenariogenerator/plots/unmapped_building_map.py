from typing import Iterable

from builda_client.dev_client import NonResidentialBuilding  # type: ignore
import pylpg.lpgpythonbindings

from cityscenariogenerator.plots import building_map_interactive


def get_building_category_osm(building: NonResidentialBuilding):
    osm = building.use.get("raw", {}).get("osm", {})
    amenity = osm.get("amenity", "No amenity")
    if amenity != "No amenity":
        return amenity
    building = osm.get("building", "<< No data >>")
    return building


def get_building_category_alkis(building: NonResidentialBuilding):
    category = (
        building.use.get("raw", {}).get("alkis", {}).get("description", "No data")
    )
    return category


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
            get_building_category_osm(b),
        )
        for b in nonres_buildings
    ]
    building_map_interactive.map_locations_plot_html(points, scenario_directory)
