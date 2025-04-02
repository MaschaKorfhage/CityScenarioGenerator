"""
Simple script for parsing POIs from text copied out of address book sites such as GelbeSeiten.
Also looks up coordinates by address and creates a custom POI file that can be imported.
"""

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from dataclasses_json import dataclass_json
from geopy.geocoders import Nominatim  # type: ignore
from pylpg import lpgdata
import requests

#: the geolocating service to use
GEOLOCATOR = Nominatim(user_agent="address-lookup-citysim")


def lookup_coordinates_nominatim(address: str) -> lpgdata.Coordinates:
    loc = GEOLOCATOR.geocode(address, timeout=30)
    return lpgdata.Coordinates(loc.latitude, loc.longitude)


def lookup_coordinates_geoapify(address: str) -> lpgdata.Coordinates:
    API_KEY = "bdbbdacf3a344299ae6556b621dd69f0"
    # Build the API URL
    url = f"https://api.geoapify.com/v1/geocode/search?text={address}&limit=1&apiKey={API_KEY}"

    # Send the API request and get the response
    response = requests.get(url)

    # Check the response status code
    if response.status_code == 200:
        # Parse the JSON data from the response
        data = response.json()
        # Extract the first result from the data
        result = data["features"][0]
        # Extract the latitude and longitude of the result
        latitude = result["geometry"]["coordinates"][1]
        longitude = result["geometry"]["coordinates"][0]
        return lpgdata.Coordinates(latitude, longitude)
    else:
        raise Exception(f"Request failed with status code {response.status_code}")


@dataclass_json
@dataclass
class Entry:
    name: str
    category: str
    street: str
    number: str
    city: str
    postal_code: int

    def address(self) -> str:
        assert self.street and self.city and self.postal_code
        return f"{self.street} {self.number}, {self.postal_code} {self.city}"

    def lookup_coordinates(self) -> lpgdata.Coordinates:
        return lookup_coordinates_nominatim(self.address())

    def create_poi(self) -> lpgdata.PointOfInterestData:
        location = self.category
        coordinates = self.lookup_coordinates()
        return lpgdata.PointOfInterestData(location, coordinates)


def get_street_number(s: str) -> tuple[str, str]:
    "string in format 'Kurfürstenstr. 15', sometimes without number"
    parts = s.split(" ")
    if len(parts) == 1:
        return s, ""
    number = parts[-1]
    street = " ".join(parts[:-1])
    return street, number


def get_postal_and_city(s: str) -> tuple[int, str]:
    "string in format '52351 Düren', sometimes followed by a city area"
    if ", " in s:
        i = s.find(",")
        s = s[:i]
    parts = s.split(" ")
    assert len(parts) == 2, f"Unexpected format: {s}"
    postal = int(parts[0])
    city = parts[1]
    return postal, city


def create_entry(lines: list[str]) -> Entry:
    assert len(lines) > 4
    name = lines[0]
    category = lines[1]
    street, number = get_street_number(lines[2])
    postal, city = get_postal_and_city(lines[3])
    return Entry(name, category, street, number, city, postal)


def print_duplicate_addresses(entries: list[Entry]):
    """
    Prints all entries that have the same address.

    :param entries: location entries to check
    """
    locations = defaultdict(list)
    for entry in entries:
        addr = entry.address()
        locations[addr].append(entry.name)
    for addr, namelist in locations.items():
        if len(namelist) > 1:
            print(f"{addr}\n{namelist}\n")


def write_to_poi_file(path: Path, entries: list[Entry]):
    """
    Converts the entries to POI objects and stores them
    in a JSON file.

    :param path: path for the JSON file
    :param entries: the entries to convert
    """
    pois = {e.name: e.create_poi() for e in entries}
    assert len(pois) == len(entries), "Name conflict"
    citydata = lpgdata.CityData(pois)
    json_str = citydata.to_json(indent=4)  # type: ignore
    with open(path, "w", encoding="utf8") as f:
        f.write(json_str)


def filter_entries(
    entries: list[Entry], condition: Callable[[Entry], bool]
) -> tuple[list[Entry], list[Entry]]:
    """
    Separates entries into two lists, depending on whether they fulfill
    a condition or not.

    :param entries: the full list of entries
    :param condition: the condition to group by
    :return: the list of entries that fulfill the condition, and the list of
             the remaining entries
    """
    fulfilled = []
    not_fulfilled = []
    for entry in entries:
        if condition(entry):
            fulfilled.append(entry)
        else:
            not_fulfilled.append(entry)
    return fulfilled, not_fulfilled


def parse_dasoertliche(lines) -> list[Entry]:
    entries: list[Entry] = []
    current_entry_lines: list[str] = []
    for line in lines:
        if line.startswith("Details anzeigen"):
            entry = create_entry(current_entry_lines)
            entries.append(entry)
            current_entry_lines = []
            continue
        current_entry_lines.append(line.strip())
    return entries


def main():
    path = Path("data/raw/address_book_texts_jülich/dasörtliche.txt")
    # path = Path("data/raw/address_book_texts_jülich/dastelefonbuch.txt")
    # path = Path("data/raw/address_book_texts_jülich/gelbeseiten.txt")

    with open(path, "r", encoding="utf8") as f:
        lines = f.readlines()
    # skip header line
    lines = lines[1:]

    all_entries = parse_dasoertliche(lines)
    print(f"Found {len(all_entries)} suitable entries.")

    # filter out unsuitable entries
    entries, wrong_city = filter_entries(all_entries, lambda e: e.city == "Jülich")
    entries, vets = filter_entries(
        entries, lambda e: "Tier" not in e.name and "Tier" not in e.category
    )
    print(
        f"Ignored: {len(wrong_city)} entries (wrong city), {len(vets)} entries (vets).\n"
        f"{len(entries)} suitable entries remain."
    )

    # find locations with the same address
    print_duplicate_addresses(entries)

    resultpath = path.parent / (f"custom_pois_{path.stem}.json")
    write_to_poi_file(resultpath, entries)
    # resultpath = path.parent / (f"{resultpath.stem}_wrong_city.json")
    # write_to_poi_file(resultpath, wrong_city)


if __name__ == "__main__":
    main()
