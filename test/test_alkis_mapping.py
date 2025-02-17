"""Tests the ALKIS code to location mapping"""

import pytest
from cityscenariogenerator.lpg_locations import LpgLocations
from cityscenariogenerator.poi_type_mapping import AlkisMapper, LocationType


@pytest.fixture
def alkis_mapping():
    """Returns the ALKIS code to location mapping"""
    return AlkisMapper.load_alkis_location_mapping()


def test_alkis_mapping_complete(alkis_mapping: dict[str, LocationType]):
    """Checks whether all relevant locations are covered in the mapping"""
    print("\nLocations that are not covered yet:")
    work = {x for val in alkis_mapping.values() for x in val.work_locations}
    nonwork = {x for val in alkis_mapping.values() for x in val.non_work_locations}
    assert (
        work == LpgLocations.WORK
    ), f"Missing work locations: {", ".join(LpgLocations.WORK - work)}"
    assert (
        nonwork == LpgLocations.NONRES_BUILD_NO_WORK
    ), f"Missing non-work locations: {", ".join(LpgLocations.NONRES_BUILD_NO_WORK - nonwork)}"


def test_incorrect_locations(alkis_mapping: dict[str, LocationType]):
    """Tests whether all location names are correct"""
    print("\nWrong location names:")
    wrong_work = []
    wrong_nonwork = []
    for k, loc_type in alkis_mapping.items():
        for loc in loc_type.work_locations:
            if loc not in LpgLocations.WORK:
                wrong_work.append(loc)
        for loc in loc_type.non_work_locations:
            # only locations that belong to non-residential buildings are allowed
            if loc not in LpgLocations.NONRES_BUILD_NO_WORK:
                wrong_nonwork.append(loc)
    assert len(wrong_work) == 0, f"Wrong work locations: {", ".join(wrong_work)}"
    assert (
        len(wrong_nonwork) == 0
    ), f"Wrong non-work locations: {", ".join(wrong_nonwork)}"
