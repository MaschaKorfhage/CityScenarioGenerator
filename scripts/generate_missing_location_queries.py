"""Generate Overpass Turbo queries for missing LPG locations."""


from __future__ import annotations

import argparse
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CITY = "Bautzen"
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT
    / "scenario_inputs/02625/extra_custom_pois/overpass_queries/missing_locations.overpassql"
)

Selector = tuple[str, tuple[tuple[str, str], ...]]

# These are candidate OSM tags, not definitive semantic classifications.
LOCATION_SELECTORS: dict[str, tuple[Selector, ...]] = {
    "Local Recreational Area": (
        ("nwr", (("leisure", "park"),)),
        ("nwr", (("leisure", "recreation_ground"),)),
    ),
    "Bicycle Route": (("relation", (("route", "bicycle"),)),),
    "Flea Market Location": (
        ("nwr", (("marketplace", "flea_market"),)),
        ("nwr", (("shop", "flea_market"),)),
    ),
    "Singing School": (
        ("nwr", (("amenity", "music_school"), ("subject", "singing"))),
    ),
    "Fishing Location": (
        ("nwr", (("leisure", "fishing"),)),
        ("nwr", (("sport", "fishing"),)),
    ),
    "Concert House": (
        ("nwr", (("amenity", "concert_hall"),)),
        ("nwr", (("building", "concert_hall"),)),
    ),
    "Car Wash": (("nwr", (("amenity", "car_wash"),)),),
    "Bow Range": (
        ("nwr", (("leisure", "archery"),)),
        ("nwr", (("sport", "archery"),)),
    ),
    "Hiking Location": (("relation", (("route", "hiking"),)),),
    "Golf Club": (("nwr", (("leisure", "golf_course"),)),),
    "Horse Stable": (
        ("nwr", (("leisure", "horse_riding"),)),
        ("nwr", (("building", "stable"),)),
        ("nwr", (("building", "riding_hall"),)),
    ),
    "Running Path": (
        ("relation", (("route", "running"),)),
        ("nwr", (("sport", "running"),)),
    ),
    "Hunting Forest": (
        ("nwr", (("landuse", "forest"), ("hunting", "yes"))),
    ),
    "Fitness Studio": (
        ("nwr", (("leisure", "fitness_centre"),)),
        ("nwr", (("amenity", "gym"),)),
    ),
    "Yoga Studio": (
        ("nwr", (("sport", "yoga"),)),
        ("nwr", (("leisure", "yoga"),)),
    ),
    "Outdoor Swimming Pool": (("nwr", (("leisure", "swimming_pool"),)),),
    "Walking Location": (
        ("relation", (("route", "foot"),)),
        ("relation", (("route", "walking"),)),
    ),
    "Musical Society": (
        ("nwr", (("amenity", "music_school"),)),
        ("nwr", (("club", "music"),)),
    ),
    "Festival Location": (
        ("nwr", (("leisure", "festival_grounds"),)),
        ("nwr", (("amenity", "events_venue"),)),
    ),
    "Community College": (
        ("nwr", (("amenity", "college"),)),
        ("nwr", (("building", "college"),)),
    ),
    "Soccer Practice Location": (
        ("nwr", (("leisure", "pitch"), ("sport", "soccer"))),
        ("nwr", (("leisure", "sports_centre"), ("sport", "soccer"))),
    ),
    "Mountain Road": (
        ("relation", (("route", "mtb"),)),
        ("way", (("highway", "track"),)),
    ),
}


def build_query(city: str) -> str:
    """Build one query containing candidate tags for every missing location."""
    lines = [
        "[out:json][timeout:60];",
        f"{{{{geocodeArea:{city}}}}}->.searchArea;",
        "(",
    ]
    emitted_selectors: set[Selector] = set()
    for location_type, selectors in LOCATION_SELECTORS.items():
        lines.append(f"  // {location_type}")
        for selector in selectors:
            if selector in emitted_selectors:
                continue
            emitted_selectors.add(selector)
            element_type, tags = selector
            tag_filters = "".join(f'[{key}="{value}"]' for key, value in tags)
            lines.append(f"  {element_type}{tag_filters}(area.searchArea);")
    lines.extend((");", "out center tags;"))
    return "\n".join(lines) + "\n"


def matching_location_types(feature: dict[str, object]) -> set[str]:
    properties = feature.get("properties")
    if not isinstance(properties, dict):
        return set()

    osm_id = feature.get("id") or properties.get("@id")
    element_type = osm_id.partition("/")[0] if isinstance(osm_id, str) else ""
    matches: dict[str, int] = {}
    for location_type, selectors in LOCATION_SELECTORS.items():
        for selector_type, tags in selectors:
            if selector_type != "nwr" and selector_type != element_type:
                continue
            if all(properties.get(key) == value for key, value in tags):
                matches[location_type] = max(
                    matches.get(location_type, 0), len(tags)
                )
    if not matches:
        return set()
    most_specific = max(matches.values())
    return {
        location_type
        for location_type, specificity in matches.items()
        if specificity == most_specific
    }


def infer_location_types(feature: dict[str, object]) -> tuple[str, ...]:
    matches = matching_location_types(feature)
    if not matches:
        raise ValueError("no matching missing-location tags")
    return tuple(sorted(matches))


def infer_location_type(feature: dict[str, object]) -> str:
    matches = infer_location_types(feature)
    if len(matches) > 1:
        raise ValueError(
            "ambiguous missing LPG location type: " + ", ".join(sorted(matches))
        )
    return matches[0]


def generate_query(city: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "// Combined candidate query; review OSM tags before importing.\n"
        + build_query(city),
        encoding="utf8",
    )
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create one combined Overpass Turbo query for missing LPG locations.",
        epilog="""Example workflow (run from the project root):
  ./.cityvenv/bin/python scripts/generate_missing_location_queries.py --city Bautzen

Run the generated .overpassql file in Overpass Turbo and export it as
scenario_inputs/02625/extra_custom_pois/overpass_queries/missing_locations.geojson.
Preview the import with --dry-run, then rerun without --dry-run to write custom_pois.json.
See scripts/import_overpass_custom_pois.py --help for the import commands.""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--city", default=DEFAULT_CITY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    output_path = (
        args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    )
    generated_path = generate_query(args.city, output_path)
    print(f"Generated combined query: {generated_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())