"""
Checks BUILDA building IDs and replaces them if necessary to make them case-insensitive.
"""

import logging
from typing import Iterable


class BuildingIdChecker:
    """
    A class for checking BUILDA IDs and possibly changing them if they
    need to be unique even without case, e.g. for Windows filenames.
    """

    def __init__(self) -> None:
        # store which BUILDA IDs were replaced with new, case-insensitive ones
        self.id_replacements: dict[str, str] = {}
        self.building_counter = 0

    def add_counter_to_ids(self, buildings: Iterable) -> None:
        """
        Adds a counter to the IDs of the buildings to make them unique.

        :param buildings: the buildings whose IDs to adapt
        """
        for b in buildings:
            if new_id := self.id_replacements.get(b.id):
                # replaced the ID before, use the same replacement
                b.id = new_id
            else:
                # choose a new ID using the global building counter
                new_id = f"{b.id}-{self.building_counter}"
                self.id_replacements[b.id] = new_id
                b.id = new_id
                self.building_counter += 1


def check_building_ids(buildings, always_adapt: bool = False):
    """
    Checks if there are building IDs that only differ in case. If so,
    the IDs are adapted to make them unique without case.

    :param buildings: the buildings whose IDs to check
    :param always_adapt: if True, always adapts the IDs
    """
    building_ids = {building.id.lower() for building in buildings}
    case_sensitive_ids = len(building_ids) != len(buildings)
    if always_adapt or case_sensitive_ids:
        message = ""
        if case_sensitive_ids:
            message = "Some building IDs only differ in case. "
        builda_id_checker.add_counter_to_ids(buildings)
        message += "Added a counter to make IDs unique without case."
        logging.info(message)


#: global BUILDA id checker instance
builda_id_checker = BuildingIdChecker()
