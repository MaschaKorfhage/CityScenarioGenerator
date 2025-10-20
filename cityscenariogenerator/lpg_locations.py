"""
A module for loading the locations used in the LoadProfileGenerator.
"""

from pathlib import Path

from cityscenariogenerator.deterrence import ActivityType

#: directory containing the location files
LOCATION_DIR = Path("data/lpg_locations")


def load_location_set(path: Path) -> set[str]:
    """
    Loads a list of LoadProfileGenerator locations from a text file.

    :param path: path to the file
    :return: set of location names
    """
    with open(path, "r", encoding="utf8") as f:
        all_locations = f.read()

    return set(line for line in all_locations.splitlines() if not line.startswith("#"))


class LpgLocations:
    """
    Stores different sets of LPG locations, according to different categories.
    Some of the sets are not mutually exclusive.
    """

    ALL = load_location_set(LOCATION_DIR / "all_remote.txt")
    WORK = load_location_set(LOCATION_DIR / "work.txt")
    NO_WORK = ALL - WORK
    RESIDENTIAL = load_location_set(LOCATION_DIR / "residential.txt")
    NON_RESIDENTIAL = ALL - RESIDENTIAL
    NO_BUILDING = load_location_set(LOCATION_DIR / "no_building.txt")
    NONRES_BUILDING = ALL - RESIDENTIAL - NO_BUILDING
    NONRES_BUILD_NO_WORK = NONRES_BUILDING & NO_WORK
    SPECIAL = load_location_set(LOCATION_DIR / "special.txt")
    RES_AND_SPECIAL = RESIDENTIAL | SPECIAL

    SHOPPING = load_location_set(LOCATION_DIR / "shopping.txt")
    SCHOOL = load_location_set(LOCATION_DIR / "school.txt")


def location_to_omod_activity_type(location: str) -> ActivityType:
    """Determines the matching OMOD activity type for an LPG location.
    Can be used in the OMOD deterrence function.

    :param location: the LPG location
    :return: the matching activity type
    """
    if location in LpgLocations.WORK:
        return ActivityType.work
    if location in LpgLocations.SCHOOL:
        return ActivityType.school
    if location in LpgLocations.SHOPPING:
        return ActivityType.shopping
    return ActivityType.other
