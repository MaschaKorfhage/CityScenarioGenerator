"""Imports buildings from BUILDA"""

from collections import Counter
import logging
import os
from pathlib import Path
import pickle
from typing import Sequence
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
    username = os.getenv("builda_username")
    password = os.getenv("builda_password")
    if not username or not password:
        raise Exception("'builda_username' or 'builda_password' not set correctly.")
    # init the Builda API client
    return BuildaDevClient(
        proxy=False,
        username=username,
        password=password,
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
    search_args: dict, query_type: str, data: Sequence[Building]
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


def check_matching_cache_files(search_args: dict) -> None:
    """
    Check whether both matching cache files (residential/non-residential) for
    this BUILDA query exist. If not, raise an exception to avoid problems with
    building IDs.

    :param search_args: BUILDA query
    :raises Exception: if the corresponding cache file does not exist
    """
    query_types = ["res", "nonres"]
    cache_files_found = [
        get_cache_filename(search_args, query_type).exists()
        for query_type in query_types
    ]
    if any(cache_files_found) and not all(cache_files_found):
        raise Exception(
            f"For the BUILDA query {search_args}, one of the cache files exists, but not the other. "
            "This can lead to inconsistencies in case building IDs were adapted for case-insensitivity. "
            f"Please delete the unmatched cache file."
        )


def _get_nonresidential_buildings(
    search_args: dict, use_cache: bool = True
) -> list[NonResidentialBuilding]:
    # check whether the result is already cached
    if use_cache and (cached := load_builda_cache(search_args, "nonres")):
        return cached  # type: ignore[return-value]
    client = get_builda_devclient()

    nonres_buildings = client.get_non_residential_buildings(
        **search_args, exclude_auxiliary=True
    )
    logging.info(f"Non-residential buildings in {search_args}: {len(nonres_buildings)}")
    if use_cache:
        # cache the result
        cache_builda_result(search_args, "nonres", nonres_buildings)
    return nonres_buildings


def get_nonresidential_buildings(
    search_args: dict, safe_ids: bool = True, use_cache: bool = True
) -> list[NonResidentialBuilding]:
    """
    Gets non-residential buildings from BUILDA for a specific query.

    :param search_args: the BUILDA query
    :param safe_ids: if True, adapts buildings IDs to make sure they are
                     case-insensitive, defaults to True
    :param use_cache: whether to use cached BUILDA results, if available, defaults to True
    :return: the non-residential buildings retrieved from BUILDA
    """
    nonres_buildings = _get_nonresidential_buildings(search_args, use_cache)
    if safe_ids:
        builda_id_check.check_building_ids(nonres_buildings, True)
    return nonres_buildings


def _get_residential_buildings(
    search_args: dict, use_cache: bool = True
) -> list[ResidentialBuilding]:
    # check whether the result is already cached
    if use_cache and (cached := load_builda_cache(search_args, "res")):
        return cached  # type: ignore[return-value]
    client = get_builda_devclient()
    res_buildings = client.get_residential_buildings(**search_args)
    logging.info(f"Residential buildings in {search_args}: {len(res_buildings)}")
    if use_cache:
        # cache the result
        cache_builda_result(search_args, "res", res_buildings)
    return res_buildings


def get_residential_buildings(
    search_args: dict, safe_ids: bool = True, use_cache: bool = True
) -> list[ResidentialBuilding]:
    """
    Gets residential buildings from BUILDA for a specific query.

    :param search_args: the BUILDA query
    :param safe_ids: if True, adapts buildings IDs to make sure they are
                     case-insensitive, defaults to True
    :param use_cache: whether to use cached BUILDA results, if available, defaults to True
    :return: the residential buildings retrieved from BUILDA
    """
    res_buildings = _get_residential_buildings(search_args, use_cache)
    if safe_ids:
        builda_id_check.check_building_ids(res_buildings, True)
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
