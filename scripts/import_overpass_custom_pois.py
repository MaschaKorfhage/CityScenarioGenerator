"""Merge Overpass Turbo GeoJSON exports into an LPG custom_pois.json file."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from typing import Any

if __package__:
    from scripts.generate_missing_location_queries import infer_location_type
else:
    from generate_missing_location_queries import infer_location_type


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "scenario_inputs/02625/custom_pois.json"
OSM_MAPPING_DIR = PROJECT_ROOT / "data/osm_mapping"
LPG_LOCATIONS_PATH = PROJECT_ROOT / "data/lpg_locations/all_remote.txt"


@dataclass(frozen=True)
class PoiCandidate:
    source_id: str
    location_type: str
    latitude: float
    longitude: float
    name: str
    properties: dict[str, Any]

    @property
    def custom_poi_id(self) -> str:
        name_part = slug_component(self.name or self.location_type)
        source_part = slug_component(self.source_id)
        return f"OSM_{name_part}_{source_part}"

    def to_custom_poi(self) -> dict[str, Any]:
        return {
            "LocationType": self.location_type,
            "Coordinates": {
                "Latitude": self.latitude,
                "Longitude": self.longitude,
            },
            "TimeLimit": None,
        }


def slug_component(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "_", ascii_value).strip("_").lower() or "unnamed"


def normalize_name(value: str) -> str:
    return slug_component(value).replace("_", " ")


def load_osm_mappings(mapping_dir: Path = OSM_MAPPING_DIR) -> dict[str, dict[str, set[str]]]:
    mappings: dict[str, dict[str, set[str]]] = {}
    for mapping_path in sorted(mapping_dir.glob("*.json")):
        key = mapping_path.stem.replace("#", ":")
        mapping_data = json.loads(mapping_path.read_text(encoding="utf8"))
        if not isinstance(mapping_data, dict):
            raise ValueError(f"Invalid OSM mapping file: {mapping_path}")
        value_to_locations: dict[str, set[str]] = {}
        for location_type, values in mapping_data.items():
            if not isinstance(values, list):
                raise ValueError(f"Invalid OSM mapping entry in {mapping_path}")
            for value in values:
                value_to_locations.setdefault(str(value), set()).add(str(location_type))
        mappings[key] = value_to_locations
    return mappings


def load_lpg_locations(path: Path = LPG_LOCATIONS_PATH) -> set[str]:
    return {
        line.strip()
        for line in path.read_text(encoding="utf8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def _source_id(
    feature: dict[str, Any],
    properties: dict[str, Any],
    location_type: str,
    name: str,
    latitude: float,
    longitude: float,
) -> str:
    osm_id = feature.get("id") or properties.get("@id") or properties.get("id")
    if osm_id is not None:
        return str(osm_id)
    fingerprint = json.dumps(
        [location_type, normalize_name(name), round(latitude, 7), round(longitude, 7)],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(fingerprint.encode("utf8")).hexdigest()[:16]
    return f"feature/{digest}"


def candidate_from_feature(
    feature: dict[str, Any],
    mappings: dict[str, dict[str, set[str]]],
    valid_locations: set[str],
    location_type_override: str | None = None,
) -> PoiCandidate:
    properties = feature.get("properties")
    geometry = feature.get("geometry")
    if not isinstance(properties, dict) or not isinstance(geometry, dict):
        raise ValueError("missing properties or geometry")

    if any(
        str(properties.get(tag, "")).casefold() in {"yes", "true", "1"}
        for tag in ("disused", "abandoned", "demolished")
    ):
        raise ValueError("marked disused, abandoned, or demolished")

    if geometry.get("type") != "Point":
        raise ValueError("geometry is not a Point; export Overpass results with 'out center'")
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        raise ValueError("invalid Point coordinates")
    try:
        longitude = float(coordinates[0])
        latitude = float(coordinates[1])
    except (TypeError, ValueError) as error:
        raise ValueError("coordinates are not numeric") from error
    if (
        not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        raise ValueError("coordinates are outside valid latitude/longitude ranges")

    if location_type_override:
        location_type = location_type_override
    else:
        mapped_types: set[str] = set()
        for key, value_to_locations in mappings.items():
            value = properties.get(key)
            if isinstance(value, str):
                mapped_types.update(value_to_locations.get(value, set()))
        if not mapped_types:
            raise ValueError("no matching OSM-to-LPG mapping; specify --location-type")
        if len(mapped_types) > 1:
            raise ValueError(
                "OSM tags map to multiple LPG types: " + ", ".join(sorted(mapped_types))
            )
        location_type = next(iter(mapped_types))

    if location_type not in valid_locations:
        raise ValueError(f"unknown LPG location type: {location_type}")

    name = ""
    for property_name in ("name", "official_name", "short_name", "brand"):
        value = properties.get(property_name)
        if isinstance(value, str) and value.strip():
            name = value.strip()
            break

    return PoiCandidate(
        source_id=_source_id(
            feature, properties, location_type, name, latitude, longitude
        ),
        location_type=location_type,
        latitude=latitude,
        longitude=longitude,
        name=name,
        properties=properties,
    )


def distance_meters(first: PoiCandidate, second: PoiCandidate) -> float:
    earth_radius_m = 6_371_000
    lat1 = math.radians(first.latitude)
    lat2 = math.radians(second.latitude)
    delta_lat = lat2 - lat1
    delta_lon = math.radians(second.longitude - first.longitude)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * earth_radius_m * math.asin(min(1.0, math.sqrt(haversine)))


def are_duplicates(
    first: PoiCandidate, second: PoiCandidate, dedupe_distance_m: float
) -> bool:
    if first.location_type != second.location_type:
        return False
    if first.custom_poi_id == second.custom_poi_id:
        return True

    distance = distance_meters(first, second)
    if distance <= 1:
        return True
    first_name = normalize_name(first.name)
    second_name = normalize_name(second.name)
    if first_name and first_name == second_name and distance <= dedupe_distance_m:
        return True
    return not first_name and not second_name and distance <= 5


def _candidate_from_custom_poi(
    poi_id: str, poi: dict[str, Any]
) -> PoiCandidate | None:
    try:
        coordinates = poi["Coordinates"]
        latitude = float(coordinates["Latitude"])
        longitude = float(coordinates["Longitude"])
        location_type = str(poi["LocationType"])
    except (KeyError, TypeError, ValueError):
        return None

    name = poi_id
    if poi_id.startswith("OSM_"):
        remainder = poi_id[4:]
        for marker in ("_node_", "_way_", "_relation_", "_feature_"):
            marker_position = remainder.rfind(marker)
            if marker_position > 0:
                name = remainder[:marker_position].replace("_", " ")
                break
        else:
            name = ""
    return PoiCandidate(
        source_id=poi_id,
        location_type=location_type,
        latitude=latitude,
        longitude=longitude,
        name=name,
        properties={},
    )


def merge_candidates(
    payload: dict[str, Any],
    candidates: list[PoiCandidate],
    dedupe_distance_m: float = 30,
) -> tuple[dict[str, Any], int, int, int]:
    merged = deepcopy(payload)
    points = dict(merged["PointsOfInterest"])
    existing_candidates = [
        candidate
        for poi_id, poi in points.items()
        if isinstance(poi, dict)
        and (candidate := _candidate_from_custom_poi(str(poi_id), poi)) is not None
    ]

    ordered_candidates = sorted(
        candidates,
        key=lambda candidate: (
            -int(bool(candidate.name)),
            -int(bool(candidate.properties.get("amenity") or candidate.properties.get("building"))),
            -len(candidate.properties),
            candidate.source_id,
        ),
    )
    added = 0
    updated = 0
    duplicates = 0
    for candidate in ordered_candidates:
        poi_id = candidate.custom_poi_id
        poi_data = candidate.to_custom_poi()
        if poi_id in points:
            if points[poi_id] == poi_data:
                duplicates += 1
            else:
                points[poi_id] = poi_data
                updated += 1
            continue

        if any(
            are_duplicates(candidate, existing, dedupe_distance_m)
            for existing in existing_candidates
        ):
            duplicates += 1
            continue

        points[poi_id] = poi_data
        existing_candidates.append(candidate)
        added += 1

    merged["PointsOfInterest"] = points
    return merged, added, updated, duplicates


def load_custom_pois(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"PointsOfInterest": {}}
    text = path.read_text(encoding="utf8")
    if not text.strip():
        raise ValueError(f"Custom-POI-Datei ist leer: {path}")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"Ungültiges JSON in {path}: {error}") from error
    if not isinstance(payload, dict) or not isinstance(
        payload.get("PointsOfInterest"), dict
    ):
        raise ValueError(f"{path} muss ein Objekt mit 'PointsOfInterest' enthalten")
    return payload


def load_feature_collection(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Ungültiges GeoJSON in {path}: {error}") from error
    if payload.get("type") != "FeatureCollection" or not isinstance(
        payload.get("features"), list
    ):
        raise ValueError(f"{path} ist keine GeoJSON FeatureCollection")
    return [feature for feature in payload["features"] if isinstance(feature, dict)]


def write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf8", dir=path.parent, delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(payload, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(
                description="Overpass-Turbo-GeoJSON sicher in custom_pois.json übernehmen.",
                epilog="""Combined-query example (run from the project root):
    Preview without writing:
                ./.cityvenv/bin/python scripts/import_overpass_custom_pois.py --input scenario_inputs/02625/extra_custom_pois/overpass_queries/missing_locations.geojson --infer-missing-location-types --dry-run

    Write all unambiguous matches to custom_pois.json:
                ./.cityvenv/bin/python scripts/import_overpass_custom_pois.py --input scenario_inputs/02625/extra_custom_pois/overpass_queries/missing_locations.geojson --infer-missing-location-types --output scenario_inputs/02625/custom_pois.json""",
                formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        action="append",
        type=Path,
        required=True,
        help="Overpass-Turbo-GeoJSON; mehrfach verwendbar",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Ziel-JSON (Standard: {DEFAULT_OUTPUT})",
    )
    location_group = parser.add_mutually_exclusive_group()
    location_group.add_argument(
        "--location-type",
        help=(
            "LPG-Typ für alle Features dieser Eingabe. Nur für eine geprüfte, "
            "einzelne Kategorie verwenden; sonst wird anhand der OSM-Mappings zugeordnet."
        ),
    )
    location_group.add_argument(
        "--infer-missing-location-types",
        action="store_true",
        help="LPG-Typen aus der gemeinsamen Missing-Locations-Abfrage ableiten",
    )
    parser.add_argument(
        "--dedupe-distance-m",
        type=float,
        default=30,
        help="Duplikatabstand für gleiche Namen und Typen in Metern (Standard: 30)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur Vorschau ausgeben und die Zieldatei nicht ändern",
    )
    args = parser.parse_args()

    if args.dedupe_distance_m < 0:
        parser.error("--dedupe-distance-m darf nicht negativ sein")

    mappings = load_osm_mappings()
    valid_locations = load_lpg_locations()
    if args.location_type and args.location_type not in valid_locations:
        parser.error(f"Unbekannter LPG-Typ: {args.location_type}")

    candidates: list[PoiCandidate] = []
    skipped: Counter[str] = Counter()
    skipped_examples: list[str] = []
    feature_count = 0
    for input_path in args.input:
        resolved_input = resolve_path(input_path)
        try:
            features = load_feature_collection(resolved_input)
        except (OSError, ValueError) as error:
            parser.error(str(error))
        feature_count += len(features)
        for feature in features:
            try:
                location_type = args.location_type
                if args.infer_missing_location_types:
                    location_type = infer_location_type(feature)
                candidates.append(
                    candidate_from_feature(
                        feature,
                        mappings,
                        valid_locations,
                        location_type,
                    )
                )
            except ValueError as error:
                reason = str(error)
                skipped[reason] += 1
                if len(skipped_examples) < 8:
                    properties = feature.get("properties", {})
                    skipped_examples.append(
                        f"{feature.get('id') or properties.get('@id') or '<ohne OSM-ID>'}: {reason}"
                    )

    output_path = resolve_path(args.output)
    try:
        payload = load_custom_pois(output_path)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    merged, added, updated, duplicates = merge_candidates(
        payload, candidates, args.dedupe_distance_m
    )

    print(f"GeoJSON-Features gelesen: {feature_count}")
    print(f"Features mit zugeordnetem LPG-Typ: {len(candidates)}")
    print(f"Neu: {added}; aktualisiert: {updated}; Duplikate: {duplicates}")
    print(f"Übersprungen: {sum(skipped.values())}")
    for reason, count in sorted(skipped.items()):
        print(f"  {count} x {reason}")
    for example in skipped_examples:
        print(f"  Beispiel: {example}")

    if args.dry_run:
        print(f"Vorschau; Datei nicht geändert: {output_path}")
    else:
        write_json_atomically(output_path, merged)
        print(f"Custom-POIs geschrieben: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())