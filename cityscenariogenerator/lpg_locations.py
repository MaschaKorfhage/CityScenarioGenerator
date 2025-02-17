"""
A module for loading the locations used in the LoadProfileGenerator.
"""

from pathlib import Path

#: directory containing the location files
LOCATION_DIR = Path("data/lpg_locations")


def load_location_set(path: Path) -> set[str]:
    """
    Loads a list of LoadProfileGenerator locations from a text file.

    :param path: path to the file
    :return: set of location names
    """
    with open(path, "r") as f:
        all_locations = f.read()
    return set(all_locations.splitlines())


class LpgLocations:
    """
    Stores different sets of LPG locations, according to different categories.
    Some of the sets are not mutually exclusive.
    """

    ALL = load_location_set(LOCATION_DIR / "all_remote.txt")
    WORK = load_location_set(LOCATION_DIR / "work.txt")
    NON_WORK = ALL - WORK
    RESIDENTIAL = load_location_set(LOCATION_DIR / "residential.txt")
    NO_BUILDING = load_location_set(LOCATION_DIR / "no_building.txt")
