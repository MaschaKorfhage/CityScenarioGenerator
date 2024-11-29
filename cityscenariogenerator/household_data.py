"""Defines dataclasses for storing household and building related information from BUILDA"""

from dataclasses import dataclass

from builda_client.model import Coordinates


@dataclass
class HouseholdData:
    household_name: str
    num_cars: int


@dataclass
class BuildingData:
    households: list[HouseholdData]
    coordinates: Coordinates


@dataclass
class HouseholdRawData:
    num_persons: int
    num_cars: int
    working_ratio: float
    female_ratio: float
    senior_ratio: float


@dataclass
class BuildingRawData:
    households: list[HouseholdRawData]
    coordinates: Coordinates
