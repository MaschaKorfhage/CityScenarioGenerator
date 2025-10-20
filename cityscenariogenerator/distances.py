"""Distance calculations for city scenario generation"""

import functools

import geopy.distance
from pylpg import lpgdata

from cityscenariogenerator import geoutils


def calc_distances(
    houses: dict[str, lpgdata.HouseCreationAndCalculationJob],
    pois: dict[str, lpgdata.PointOfInterestData],
):
    house_df = geoutils.housejob_to_geodf(houses)
    poi_df = geoutils.pois_to_geodf(pois)


class DistanceCalculator:
    def __init__(
        self,
        houses: dict[str, lpgdata.HouseCreationAndCalculationJob],
        pois: dict[str, lpgdata.PointOfInterestData],
    ) -> None:
        self.distances = calc_distances(houses, pois)

    @functools.lru_cache
    def calc_distance_in_km(
        self, c1: lpgdata.Coordinates, c2: lpgdata.Coordinates
    ) -> float:
        """Calculates the distance between two sets of coordinates in km"""
        p1 = (c1.Latitude, c1.Longitude)
        p2 = (c2.Latitude, c2.Longitude)
        dist = geopy.distance.distance(p1, p2)
        return dist.m / 1000  # convert to km
