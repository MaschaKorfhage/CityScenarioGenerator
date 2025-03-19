from cityscenariogenerator import builda_client_import
from cityscenariogenerator.poi_type_mapping import AlkisMapper, BuildingWithLocationType


def import_nonresidential_buildings_from_builda(
    builda_query: dict,
) -> list[BuildingWithLocationType]:

    # collect non-residential buildings
    nonres_buildings = builda_client_import.get_nonresidential_buildings(builda_query)

    poi_mapper = AlkisMapper()
    buildings = poi_mapper.get_locations_for_buildings(nonres_buildings)

    return buildings
