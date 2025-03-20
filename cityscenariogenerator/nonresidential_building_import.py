from cityscenariogenerator import builda_client_import
from cityscenariogenerator.overpass_import import import_health_buildings
from cityscenariogenerator.poi_type_mapping import AlkisMapper, BuildingWithLocationType


def import_nonresidential_buildings_from_builda(
    builda_query: dict,
) -> dict[str, BuildingWithLocationType]:

    # collect non-residential buildings
    nonres_buildings = builda_client_import.get_nonresidential_buildings(builda_query)

    poi_mapper = AlkisMapper()
    buildings = poi_mapper.get_locations_for_buildings(nonres_buildings)
    buildings_by_id = {b.building.id: b for b in buildings}

    # use OSM data to get more accurate building types
    import_health_buildings.add_osm_location_types(buildings_by_id)

    return buildings_by_id
