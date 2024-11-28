from dataclasses import dataclass


@dataclass
class HouseholdData:
    household_name: str
    cars: int


@dataclass
class BuildingData:
    households: list[HouseholdData]


@dataclass
class PersonRawData:
    age: int
    gender: str
    employment: str


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
