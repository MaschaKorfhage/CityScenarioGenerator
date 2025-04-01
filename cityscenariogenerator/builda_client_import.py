"""Imports buildings from BUILDA"""

from collections import Counter
import logging
import os
from pathlib import Path
import pickle
import dotenv

from builda_client.dev_client import (  # type: ignore
    BuildaDevClient,
    Phase,
    Building,
    ResidentialBuilding,
    NonResidentialBuilding,
)

from cityscenariogenerator import builda_id_check, utils


# load credentials for the BuildaDevClient
dotenv.load_dotenv()


def get_builda_devclient():
    # init the Builda API client
    return BuildaDevClient(
        proxy=False,
        username=os.getenv("username"),
        password=os.getenv("password"),
        phase=Phase.PRODUCTION,
        version="v8_20240916",
    )


def get_cache_filename(search_args, query_type) -> Path:
    """
    Determine the cache filename for a given query.

    :param search_args: BUILDA query
    :param query_type: type of query
    :return: cache filename
    """
    query_text = utils.descriptive_query_text(search_args)
    cache_file = Path("cache") / f"{query_type}_{query_text}.pkl"
    return cache_file


def cache_builda_result(
    search_args: dict, query_type: str, data: list[Building]
) -> None:
    """
    Caches the result of a BUILDA query in a local pickle file.

    :param search_args: BUILDA query
    :param query_type: the type of query, e.g., 'residential'
    :param data: the result of the query that will be cached
    """
    cache_file = get_cache_filename(search_args, query_type)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    if cache_file.exists():
        logging.debug(f"Overwriting BUILDA cache file: {cache_file}")
    with open(cache_file, "wb") as f:
        pickle.dump(data, f)


def load_builda_cache(search_args: dict, query_type: str) -> list[Building] | None:
    """
    Loads a cached BUILDA query result from a local pickle file.

    :param search_args: BUILDA query
    :param query_type: type of the query
    :return: the cached result objects
    """
    cache_file = get_cache_filename(search_args, query_type)
    try:
        with open(cache_file, "rb") as f:
            data = pickle.load(f)
            return data
    except FileNotFoundError:
        logging.debug(f"No cache file found: {cache_file}")
        return None


def get_nonresidential_buildings(
    search_args: dict, use_cache: bool = True
) -> list[NonResidentialBuilding]:
    # check whether the result is already cached
    if use_cache and (cached := load_builda_cache(search_args, "nonres")):
        return cached
    client = get_builda_devclient()

    nonres_buildings = client.get_non_residential_buildings(
        **search_args, exclude_auxiliary=True
    )
    logging.info(f"Non-residential buildings in {search_args}: {len(nonres_buildings)}")
    builda_id_check.check_building_ids(nonres_buildings)
    if use_cache:
        # cache the result
        cache_builda_result(search_args, "nonres", nonres_buildings)
    return nonres_buildings


def get_residential_buildings(
    search_args: dict, use_cache: bool = True
) -> list[ResidentialBuilding]:
    # check whether the result is already cached
    if use_cache and (cached := load_builda_cache(search_args, "res")):
        return cached
    client = get_builda_devclient()
    res_buildings = client.get_residential_buildings(**search_args)
    logging.info(f"Residential buildings in {search_args}: {len(res_buildings)}")
    builda_id_check.check_building_ids(res_buildings)
    if use_cache:
        # cache the result
        cache_builda_result(search_args, "res", res_buildings)
    return res_buildings


if __name__ == "__main__":
    # only for testing queries

    import cityscenariogenerator.plots.unmapped_building_map as buil_map

    builda_query = {"city": "Wedel"}
    nonres_buildings = get_nonresidential_buildings(builda_query)
    c = Counter(buil_map.get_building_category_osm(b) for b in nonres_buildings)
    overview = "\n".join(f"{v:3d} - {k}" for k, v in c.most_common())
    buil_map.alkis_type_map_plot(Path.cwd(), nonres_buildings)
    print(overview)
