from cityscenariogenerator.lpg_locations import LpgLocations


def test_lpg_locations_exclusive_sets():
    """
    Test if some of the location sets are mutually exclusive.
    """
    assert LpgLocations.WORK & LpgLocations.NON_WORK == set()
    assert LpgLocations.WORK & LpgLocations.RESIDENTIAL == set()
    assert LpgLocations.WORK & LpgLocations.NO_BUILDING == set()
    assert LpgLocations.RESIDENTIAL & LpgLocations.NO_BUILDING == set()
