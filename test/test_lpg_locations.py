from cityscenariogenerator.lpg_locations import LpgLocations


def test_lpg_locations_exclusive_sets():
    """
    Test if some of the location sets are mutually exclusive.
    """
    assert LpgLocations.WORK & LpgLocations.NO_WORK == set()
    assert LpgLocations.WORK & LpgLocations.RESIDENTIAL == set()
    assert LpgLocations.WORK & LpgLocations.NO_BUILDING == set()
    assert LpgLocations.RESIDENTIAL & LpgLocations.NO_BUILDING == set()
    assert LpgLocations.RESIDENTIAL & LpgLocations.NONRES_BUILDING == set()
    assert LpgLocations.NO_BUILDING & LpgLocations.NONRES_BUILDING == set()


def test_lpg_locations_not_empty():
    """
    Test that none of the location subsets are empty.
    """
    for subset in (attr for attr in dir(LpgLocations) if not attr.startswith("__")):
        assert (
            len(getattr(LpgLocations, subset)) > 0
        ), f"Location subset {subset} is empty."
