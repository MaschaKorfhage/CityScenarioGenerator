"""Defines dataclasses for storing household and building related information from BUILDA"""

from dataclasses import dataclass

from builda_client.dev_model import Coordinates  # type: ignore


@dataclass
class HouseholdData:
    household_name: str
    num_cars: int


@dataclass
class BuildingData:
    id: str
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
    id: str
    households: list[HouseholdRawData]
    coordinates: Coordinates
