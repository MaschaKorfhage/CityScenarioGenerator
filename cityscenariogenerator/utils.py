"""
Various utility functions
"""

import json
import logging
from pathlib import Path
import random
import shutil
import sys
from typing import Any
import unicodedata
import re

import numpy
from pylpg import lpgdata


#: name of the logfile produced in each scenario generation
LOGFILENAME = "log.txt"


def replace_umlauts(s: str) -> str:
    """Replaces any German umlauts in the passed str
    with their common replacements.

    :param s: the str to adapt
    :return: the adapted str without umlauts
    """
    umlaut_map = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
    }
    for k, v in umlaut_map.items():
        s = s.replace(k, v)
    return s


def slugify(value, allow_unicode=False):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
    else:
        # custom replacement for umlauts
        value = replace_umlauts(value)

        value = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")


def clean_builda_query(query: dict) -> dict:
    """Removes empty arguments from a BUILDA query.

    :param query: the BUILDA query dict
    :return: _description_
    """
    filtered_query = {k: v for k, v in query.items() if v}
    return filtered_query


def descriptive_query_text(query: dict) -> str:
    """returns a text describing a builda query in a format suitable for filenames"""
    filtered_query = list(clean_builda_query(query).values())
    return slugify(str(filtered_query))


def configure_log_handler(handler):
    """
    Configures a log handler with the default settings

    :param handler: the handler to configure
    """
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
    formatter.datefmt = "%Y-%m-%d %H:%M:%S"
    handler.setFormatter(formatter)


def init_logging(directory: Path | None = None):
    """
    Sets up logging with two handlers: one for the console and one for a log file.

    :param directory: output directory; if None, no log file will be created
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # remove the default handler
    logger.handlers.clear()

    # add a handler writing to the console
    console_handler = logging.StreamHandler(sys.stdout)
    configure_log_handler(console_handler)
    logger.addHandler(console_handler)

    if directory:
        # add a handler writing to a log file in the specified directory
        directory.mkdir(parents=True, exist_ok=True)
        logfile_handler = logging.FileHandler(directory / LOGFILENAME, "w", "utf-8")
        configure_log_handler(logfile_handler)
        logger.addHandler(logfile_handler)


def clear_directory(path: Path):
    """
    Clears the specified directory if it already exists.

    :param path: the directory to clear
    """
    if path.is_dir():
        logging.info(f"Clearing directory: {path}")
        shutil.rmtree(path)


def create_json_file(filepath: Path, data: Any) -> None:
    """Saves data, e.g. a dict, to a json file.

    :param filepath: path for the json file
    :param data: the data to save
    """
    if not filepath.suffix == ".json":
        filepath = Path(f"{filepath}.json")
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf8") as f:
        json.dump(data, f, indent=4)


def sort_by_key(data: dict, reverse: bool = False) -> dict:
    """Sort a dict by its keys.

    :param data: the dict to sort
    :return: the new, sorted dict
    """
    return dict(sorted(data.items(), key=lambda item: item[0], reverse=reverse))


def sort_by_val(data: dict, reverse: bool = False) -> dict:
    """Sort a dict by its values.

    :param data: the dict to sort
    :return: the new, sorted dict
    """
    return dict(sorted(data.items(), key=lambda item: item[1], reverse=reverse))


def set_rng_seed(seed=None):
    """Sets the specified random seed. Also sets a random
    numpy seed that depends on the given seed.

    :param seed: the seed to set; if None, chooses a random seed
    """
    if seed is None:
        # no seed given, choose a random one
        seed = random.randrange(sys.maxsize)

    random.seed(seed)
    logging.info(f"Using RNG seed {seed}")

    # set numpy random seed depending on the main seed
    numpy_seed = random.randrange(2**32)
    logging.info(f"Using numpy RNG seed {numpy_seed}")
    numpy.random.seed(numpy_seed)


def create_poi_id(building_id: str, location: str) -> str:
    """Creates a new POI ID out of a building ID and an LPG location.

    :param building_id: the building ID
    :param location: the location name of the POI
    :return: the new POI ID
    """
    # if there are spaces in building IDs, the below function might produce errors
    assert " " not in building_id, (
        "CityScenarioGenerator relies on there not being any spaces in building IDs"
    )
    return f"{location} {building_id}"


def create_hh_id(building_id: str, hh_index: int) -> str:
    """Creates the household ID for a household.

    :param building_id: ID of the house the household belongs to
    :param hh_index: 0-based index of the household within the house
    :return: the ID of the household, as used in the city simulation
    """
    return f"{building_id}_HH{hh_index + 1}"


def get_building_id_from_poi(poi_id: str) -> str:
    """Extracts the building ID out of a POI ID. This
    assumes that no building ID ever includes a space.

    :param poi_id: the full POI ID
    :return: the contained building ID
    """
    return poi_id.split(" ")[-1]


def get_jsonref_name(json_ref: str | lpgdata.JsonReference) -> str:
    """Returns a JsonReference as a str. Returns the name, or if that
    is empty, the Guid.

    :param json_ref: the JsonReference
    :return: the str representing the JsonReference
    """
    if isinstance(json_ref, str):
        return json_ref
    if json_ref.Name:
        return json_ref.Name
    assert json_ref.Guid and json_ref.Guid.StrVal
    return json_ref.Guid.StrVal
