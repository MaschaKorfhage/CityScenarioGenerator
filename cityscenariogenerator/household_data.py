"""Defines dataclasses for storing household and building related information from BUILDA"""

from dataclasses import dataclass

from builda_client.dev_model import Coordinates  # type: ignore


@dataclass(frozen=True)
class HouseholdData:
    household_name: str
    num_cars: int


@dataclass(frozen=True)
class BuildingData:
    id: str
    households: list[HouseholdData]
    coordinates: Coordinates


@dataclass(frozen=True)
class HouseholdRawData:
    num_persons: int
    num_cars: int
    working_ratio: float
    female_ratio: float
    senior_ratio: float


@dataclass(frozen=True)
class BuildingRawData:
    id: str
    households: list[HouseholdRawData]
    coordinates: Coordinates
