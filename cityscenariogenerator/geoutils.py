from typing import Iterable

import geopandas as gpd
from shapely import Point
from pylpg import lpgdata
from builda_client.dev_model import Building

from cityscenariogenerator.household_data import BuildingData

class GeoDFColumns:
    """Column names used in GeoDataFrames for handling
    POI data from different sources."""

    BUILDA_ID = "id_builda"
    EXT_ID = "id"

    DISTANCE = "distance"
    CATEGORY = "category"


def builda_to_geodf(buildings: Iterable[Building | BuildingData]) -> gpd.GeoDataFrame:
    # store in list to allow iterating multiple times
    building_list = list(buildings)
    # Convert to GeoDataFrame
    geometry = [
        Point(b.coordinates.longitude, b.coordinates.latitude) for b in building_list
    ]
    data = {GeoDFColumns.BUILDA_ID: [b.id for b in building_list]}
    df = gpd.GeoDataFrame(data, geometry=geometry)
    df.set_crs("EPSG:4326", inplace=True)
    return df


def pois_to_geodf(pois: dict[str, lpgdata.PointOfInterestData]) -> gpd.GeoDataFrame:
    geometry = [
        Point(poi.Coordinates.Longitude, poi.Coordinates.Latitude)  # type: ignore
        for poi in pois.values()
    ]
    data = {
        GeoDFColumns.EXT_ID: list(pois.keys()),
        GeoDFColumns.CATEGORY: [str(p.LocationType) for p in pois.values()],
    }
    df = gpd.GeoDataFrame(data, geometry=geometry)
    df.set_crs("EPSG:4326", inplace=True)
    return df
