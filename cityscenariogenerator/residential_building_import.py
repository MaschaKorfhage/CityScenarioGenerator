"""
Contains functions to import residential buildings from BUILDA, and map them to the data required for the LoadProfileGenerator.
"""

import logging
from pathlib import Path
import geopandas as gpd
from builda_client.dev_model import Coordinates
from shapely import Point  # type: ignore

from cityscenariogenerator import builda_client_import
import cityscenariogenerator.builda_file_import.sampling_with_builda_data.sampling_buildings_from_builda as builda_file_sampler
import cityscenariogenerator.builda_file_import.statistical_sampling.sampling_lpg_households as lpg_household_sampler
from cityscenariogenerator.household_data import (
    BuildingData,
    BuildingRawData,
    HouseholdRawData,
)
from cityscenariogenerator.scenario_params import ScenarioParams


def import_residential_buildings_from_builda_file(
    number_of_buildings: int,
) -> list[BuildingData]:
    # get building data from builda csv file
    (
        building_ids,
        tabula_building_codes,
        conditioned_floor_areas_in_m2,
        number_of_dwellings,
        norm_heating_load_in_kw,
        postal_code,
        pv_capacities_in_kw,
        pv_generations_in_kwh,
        commodities,
        supply_levels,
        building_data_list,
    ) = builda_file_sampler.get_buildings_from_builda_file(
        number_of_random_samples=number_of_buildings
    )

    # get lpg profiles based on builda data
    buildings = lpg_household_sampler.get_lpg_households_based_on_builda_data(
        building_data_list
    )
    return buildings

def building_list_to_geodf(buildings: list[BuildingRawData]) -> gpd.GeoDataFrame:
    """Creates a GeoDataFrame out of a list of households. The GeoDataFrame
    contains the building IDs, coordinates, and the number of households.

    :param buildings: the list of building raw data objects
    :return: the GeoDataFrame
    """
    records = []
    for b in buildings:
        records.append(
            {
                "id": b.id,
                "household_num": len(b.households),
                "geometry": Point(b.coordinates.longitude, b.coordinates.latitude),
            }
        )
    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    return gdf


def apply_custom_residential_deletions(
    params: ScenarioParams, buildings: list[BuildingRawData]
) -> list[BuildingRawData]:
    """If a file with custom household deletions is specified, applies
    the deletions. Deletes enough random houses to fullfill the given
    number of households to delete.

    :param params: parameter object
    :param buildings: the full list of input buildings
    :return: the remaining buildings that were not deleted
    """
    path = params.custom_residentials_deletions_path()
    if not path.is_file():
        logging.info("No custom residential deletions specified")
        return buildings

    building_gdf = building_list_to_geodf(buildings)
    deletions = gpd.read_file(path).set_crs(4326)
    deleted = set()
    # handle each deletion area individually
    for i, entry in deletions.iterrows():
        area = entry["geometry"]
        hh_to_delete = entry["n_flats"]
        deleted_hh_count = 0

        # get all buildings in the affected area
        buildings_in_area = building_gdf.loc[building_gdf["geometry"].within(area)]
        if len(buildings_in_area) == 0:
            logging.info(f"No houses in deletion area {i}; skipping")
            continue
        # shuffle for a random order
        seed = random.randrange(2**32)
        buildings_in_area = buildings_in_area.sample(frac=1, random_state=seed)
        # mark houses for deletion until enough households are removed
        for _, building in buildings_in_area.iterrows():
            # don't delete buildings twice if areas overlap
            if building["id"] in deleted:
                continue
            # mark the house for deletion
            deleted.add(building["id"])
            deleted_hh_count += building["household_num"]
            if deleted_hh_count >= hh_to_delete:
                # deleted enough houses
                break
        if deleted_hh_count < hh_to_delete:
            logging.warning(
                f"Only found {deleted_hh_count} of {hh_to_delete} households to delete in area {i}."
            )
    # return the houses that were not deleted
    logging.info(f"Deleting {len(deleted)} of {len(buildings)} residential houses")
    return [b for b in buildings if b.id not in deleted]


def load_custom_residential_buildings(params: ScenarioParams) -> list[BuildingRawData]:
    """Parses additional custom residential buildings from a geojson file.

    :param params: the simulation parameter object
    :raises Exception: if the file had an invalid format
    :return: the parsed buildings, if any
    """
    # check if a file with additional custom buildings exists
    path = params.custom_residentials_path()
    if not path.is_file():
        logging.info("No custom residential buildings specified")
        return []

    buildings = []
    building_info = gpd.read_file(path).set_crs(4326)
    for i, row in building_info.iterrows():
        src_id = row.get("id")
        id = f"CustomRes_{src_id}{i}"
        num_hh = int(row.get("num_hh") or 1)
        num_cars: int = row["num_cars"]
        # TODO: determine number of cars per household properly
        cars_per_hh = num_cars // num_hh
        try:
            # create dummy households without any data; LPG templates will then be sampled from Zensus
            hh = [HouseholdRawData(-1, cars_per_hh, -1, -1, -1) for _ in range(num_hh)]
            point = row["geometry"]
            coordinates = Coordinates(point.y, point.x)
            building = BuildingRawData(id, hh, coordinates)
            buildings.append(building)
        except ValueError as e:
            raise Exception(
                f"Could not parse custom residential building {id} from file {path}: {e}"
            )
    logging.info(f"Parsed {len(buildings)} custom residential buildings from {path}")
    return buildings


def import_residential_buildings_from_builda(
    params: ScenarioParams,
) -> list[BuildingData]:
    # load residential buildings from BUILDA
    raw_buildings = builda_client_import.get_residential_buildings(params.builda_query)
    # parse the household data into data objects
    building_data_list = builda_file_sampler.convert_residential_buildings_from_builda(
        raw_buildings
    )

    building_data_list = apply_custom_residential_deletions(params, building_data_list)

    # optionally parse custom buildings from file and add them
    custom_buildings = load_custom_residential_buildings(params)
    building_data_list.extend(custom_buildings)

    # determine LPG households for each building
    buildings = lpg_household_sampler.get_lpg_households_based_on_builda_data(
        building_data_list, params.result_directory / "statistics/builda"
    )
    return buildings
