"""Distance calculations for city scenario generation"""

import functools
import logging

import geopy.distance
import pandas as pd
from pylpg import lpgdata
from tqdm import tqdm

from cityscenariogenerator import geoutils, utils


def calc_distances(
    houses_dict: dict[str, lpgdata.HouseCreationAndCalculationJob],
    pois_dict: dict[str, lpgdata.PointOfInterestData],
    all_distances: bool = False,
) -> pd.DataFrame:
    """Calculates a distance matrix for the specified buildings.

    :param houses_dict: the house jobs for residential buildings
    :param pois_dict: the POIs to include
    :param all_distances: if True, calculates all distances between any pair of two
                          buildings; otherwise, only calculates distances from
                          residential buildings to POIs; defaults to False
    :return: the distance matrix with distances in km
    """
    logging.info("Calculating distance matrix for all buildings")
    # creage GeoDataFrames
    houses = geoutils.housejob_to_geodf(houses_dict)
    pois = geoutils.pois_to_geodf(pois_dict)
    houses.set_index(geoutils.GeoDFColumns.BUILDA_ID, inplace=True)
    pois.set_index(geoutils.GeoDFColumns.EXT_ID, inplace=True)

    # convert to local crs
    # crs = "EPSG:3857"
    crs = "EPSG:32632"
    houses = houses.to_crs(crs)
    pois = pois.to_crs(crs)
    all_buildings = pd.concat([houses, pois])

    # determine which distances are required
    if all_distances:
        # distances between any two buildings required
        point_a = all_buildings
        point_b = all_buildings
    else:
        # only distances between a house and a POI required
        point_a = houses
        point_b = pois

    # calculate distance matrix, from all buildings to every POI
    point_b_row_list = list(point_b.iterrows())
    dist_matrix = pd.DataFrame(
        {
            poi_id: point_a.geometry.distance(poi_row.geometry)
            for poi_id, poi_row in tqdm(point_b_row_list)
        },
        index=point_a.index,
    )
    # convert from m to km
    return dist_matrix / 1000


class DistanceCalculator:
    """Calculates a distance matrix to quickly get distances between any buildings
    in the scenario"""

    def __init__(
        self,
        houses: dict[str, lpgdata.HouseCreationAndCalculationJob],
        pois: dict[str, lpgdata.PointOfInterestData],
        all_distances: bool = False,
    ) -> None:
        """Initializes the distance matrix.

        :param houses: the residential buildings to include
        :param pois: the POIs to include
        :param all_distances: if True, calculates all distances between any pair of two
                              buildings; otherwise, only calculates distances from
                              residential buildings to POIs; defaults to False
        """
        matrix_df = calc_distances(houses, pois, all_distances)
        self.distances: dict[tuple[str, str], float] = matrix_df.stack().to_dict()  # type: ignore
        self.places = {p for pair in self.distances.keys() for p in pair}
        self.all_distances = all_distances

    def get_distance_in_km(self, point_a: str, point_b: str) -> float:
        """Calculates the distance between the building (house or POI) and
        the POI.
        When all_distances had been set to False in the constructor, the first
        building must be a residential building and the second one must be a
        POI-ID.

        :param building_id: building or POI ID of the first building
        :param poi_id: building or POI ID of the second building
        :return: the distance between the buildings
        :raises KeyError: if no distance for building pair was found in the matrix
        """
        try:
            return self.distances[point_a, point_b]
        except KeyError:
            # residential POIs are not in the distance matrix, instead the building ID
            # is requried for them
            point_a_build = (
                point_a
                if point_a in self.places
                else utils.get_building_id_from_poi(point_a)
            )
            point_b_build = (
                point_b
                if point_b in self.places
                else utils.get_building_id_from_poi(point_b)
            )

            # If this also does not work, something is wrong.
            # Perhaps all_distances=True was not set for calc_distances.
            return self.distances[point_a_build, point_b_build]  # type: ignore

    @functools.lru_cache
    def calc_coordinate_distance_in_km(
        self, c1: lpgdata.Coordinates, c2: lpgdata.Coordinates
    ) -> float:
        """Calculates the distance between two sets of coordinates in km.
        This is slow when repeated often and should only be used as a fallback
        when the distance matrix cannot be used.

        :param c1: first coordinates
        :param c2: second coordinates
        :return: distance between the coordinates
        """
        p1 = (c1.Latitude, c1.Longitude)
        p2 = (c2.Latitude, c2.Longitude)
        dist = geopy.distance.distance(p1, p2)
        return dist.m / 1000  # convert to km
