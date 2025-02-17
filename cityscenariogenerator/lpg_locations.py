"""
A module for loading the locations used in the LoadProfileGenerator.
"""

from pathlib import Path


LOCATION_DIR = Path("data/lpg_locations")


def load_location_set(path: Path) -> set[str]:
    with open(path, "r") as f:
        all_locations = f.read()
    return set(all_locations.splitlines())


def get_lpg_remote_locations() -> set[str]:
    """
    Returns a list of all LPG locations that are not at home,
    and that therefore requrire a POI.

    :return: set of location names
    """
    return load_location_set(LOCATION_DIR / "all_remote.txt")


def get_lpg_work_locations() -> set[str]:
    """
    Returns a list of all LPG locations that are used for
    work activities, including volunteer work, but excluding
    home office. This is a subset of all LPG remote locations.

    :return: set of location names
    """
    return load_location_set(LOCATION_DIR / "work.txt")


class LpgLocations:
    ALL = get_lpg_remote_locations()
    WORK = get_lpg_work_locations()
    NON_WORK = ALL - WORK
