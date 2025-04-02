"""
Simple script for parsing POIs from text copied out of address book sites such as GelbeSeiten.
Also looks up coordinates by address and creates a custom POI file that can be imported.
"""

from pathlib import Path

import parse_dasörtliche as parse_do


def create_entry(lines: list[str]) -> parse_do.Entry:
    assert len(lines) >= 4
    name = lines[0]
    address = lines[1].split(", ")
    assert 2 <= len(address) <= 3, f"Unknown address format: {address}"
    street_num, code_city = address[:2]
    street, number = parse_do.get_street_number(street_num)
    postal, city = parse_do.get_postal_and_city(code_city)
    category = ""
    for line in lines[2:]:
        if line.startswith("Branche: "):
            category = line.replace("Branche: ", "")
    assert category, f"Could not determine category for {name}"
    return parse_do.Entry(name, category, street, number, city, postal)


def parse_dastelefonbuch(lines: list[str]) -> list[parse_do.Entry]:
    entries: list[parse_do.Entry] = []
    current_entry_lines: list[str] = []
    for line in lines:
        line = line.strip()
        if not line or line == "*":
            continue
        if line.startswith("Mehr Details"):
            entry = create_entry(current_entry_lines)
            entries.append(entry)
            current_entry_lines = []
            continue
        current_entry_lines.append(line.strip())
    return entries


def main():
    path = Path("data/raw/address_book_texts_jülich/dastelefonbuch.txt")

    with open(path, "r", encoding="utf8") as f:
        lines = f.readlines()
    # skip header line
    lines = lines[1:]

    all_entries = parse_dastelefonbuch(lines)
    print(f"Found {len(all_entries)} suitable entries.")

    # filter out unsuitable entries
    entries, wrong_city = parse_do.filter_entries(
        all_entries, lambda e: e.city == "Jülich"
    )
    entries, vets = parse_do.filter_entries(
        entries, lambda e: "Tier" not in e.name and "Tier" not in e.category
    )
    print(
        f"Ignored: {len(wrong_city)} entries (wrong city), {len(vets)} entries (vets).\n"
        f"{len(entries)} suitable entries remain."
    )

    # find locations with the same address
    parse_do.print_duplicate_addresses(entries)

    resultpath = path.parent / (f"custom_pois_{path.stem}.json")
    parse_do.write_to_poi_file(resultpath, entries)


if __name__ == "__main__":
    main()
