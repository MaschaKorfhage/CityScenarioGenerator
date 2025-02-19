"""Imports buildings from BUILDA"""

from collections import Counter
import logging
import os
from dotenv import load_dotenv

from builda_client.dev_client import (  # type: ignore
    BuildaDevClient,
    Phase,
    ResidentialBuilding,
    NonResidentialBuilding,
)


# load credentials for the BuildaDevClient
load_dotenv()


def get_builda_devclient():
    # init the Builda API client
    return BuildaDevClient(
        proxy=False,
        username=os.getenv("username"),
        password=os.getenv("password"),
        phase=Phase.PRODUCTION,
        version="v8_20240916",
    )


def get_building_category(building: NonResidentialBuilding):
    category = (
        building.use.get("raw", "No category")
        .get("alkis")
        .get("description", "No data")
    )
    return category


def get_nonresidential_buildings(
    search_args: dict,
) -> list[NonResidentialBuilding]:
    client = get_builda_devclient()

    nonres_buildings = client.get_non_residential_buildings(
        **search_args, exclude_auxiliary=True
    )
    logging.info(f"Non-residential buildings in {search_args}: {len(nonres_buildings)}")
    return nonres_buildings


def get_residential_buildings(search_args: dict) -> list[ResidentialBuilding]:
    client = get_builda_devclient()
    res_buildings = client.get_residential_buildings(**search_args)
    logging.info(f"Residential buildings in {search_args}: {len(res_buildings)}")
    return res_buildings


if __name__ == "__main__":
    # only for testing queries
    builda_query = {"city": "Aachen"}
    nonres_buildings = get_nonresidential_buildings(builda_query)
    c = Counter(get_building_category(b) for b in nonres_buildings)
    overview = "\n".join(f"{v:3d} - {k}" for k, v in c.most_common())
    print(overview)
