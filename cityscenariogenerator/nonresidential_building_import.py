from cityscenariogenerator import builda_client_import
from cityscenariogenerator.household_data import BuildingData
from cityscenariogenerator.overpass_import import osm_data_join
from cityscenariogenerator.poi_type_mapping import AlkisMapper, BuildingWithLocationType
from cityscenariogenerator.scenario_params import ScenarioParams


def import_nonresidential_buildings_from_builda(
    params: ScenarioParams,
    residential_buildings: list[BuildingData],
) -> dict[str, BuildingWithLocationType]:

    # collect non-residential buildings
    nonres_buildings = builda_client_import.get_nonresidential_buildings(
        params.builda_query
    )

    poi_mapper = AlkisMapper()
    buildings = poi_mapper.get_locations_for_buildings(nonres_buildings)
    buildings_by_id = {b.building.id: b for b in buildings}

    # use OSM data to get more accurate building types
    osm_data_join.add_osm_location_types(params, buildings_by_id, residential_buildings)

    return buildings_by_id
