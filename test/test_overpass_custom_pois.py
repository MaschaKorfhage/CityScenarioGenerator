from pathlib import Path

from scripts.import_overpass_custom_pois import (
    PoiCandidate,
    candidate_from_feature,
    candidates_from_feature,
    default_output_path,
    merge_candidates,
)
from scripts.generate_missing_location_queries import (
    infer_location_type,
    infer_location_types,
)


def _kindergarten_feature(
    osm_id: str, longitude: float, latitude: float, name: str
) -> dict:
    return {
        "type": "Feature",
        "id": osm_id,
        "properties": {"amenity": "kindergarten", "name": name},
        "geometry": {
            "type": "Point",
            "coordinates": [longitude, latitude],
        },
    }


def test_maps_kindergarten_way_and_converts_coordinate_order():
    candidate = candidate_from_feature(
        _kindergarten_feature(
            "way/49916448", 14.4470813, 51.1939963, "DRK Findikus"
        ),
        {"amenity": {"kindergarten": {"Kindergarden"}}},
        {"Kindergarden"},
    )

    assert candidate.location_type == "Kindergarden"
    assert candidate.latitude == 51.1939963
    assert candidate.longitude == 14.4470813
    assert candidate.custom_poi_id == "OSM_drk_findikus_way_49916448"


def test_explicit_location_type_handles_unmapped_childcare_tag():
    feature = _kindergarten_feature(
        "way/104729185", 14.4350935, 51.1793481, "Kinderkrippe Weigangstraße"
    )
    feature["properties"] = {"amenity": "childcare", "name": "Kinderkrippe"}

    candidate = candidate_from_feature(
        feature,
        {"amenity": {"kindergarten": {"Kindergarden"}}},
        {"Kindergarden"},
        location_type_override="Kindergarden",
    )

    assert candidate.location_type == "Kindergarden"


def test_combined_import_reports_ambiguous_location_type():
    feature = {
        "id": "way/123",
        "properties": {"leisure": "fitness_centre", "sport": "yoga"},
    }

    try:
        infer_location_type(feature)
    except ValueError as error:
        assert "ambiguous missing LPG location type" in str(error)
    else:
        raise AssertionError("Expected an ambiguous feature to be reported")


def test_combined_import_keeps_all_matching_types_and_is_idempotent():
    feature = {
        "id": "node/6186304266",
        "properties": {
            "leisure": "fitness_centre",
            "sport": "yoga",
            "name": "Example Fitness",
        },
        "geometry": {
            "type": "Point",
            "coordinates": [14.42, 51.18],
        },
    }
    location_types = infer_location_types(feature)

    candidates = candidates_from_feature(
        feature,
        {},
        set(location_types),
        infer_missing_location_types=True,
    )

    assert location_types == ("Fitness Studio", "Yoga Studio")
    assert {candidate.location_type for candidate in candidates} == set(location_types)
    assert len({candidate.custom_poi_id for candidate in candidates}) == 2

    merged, added, updated, duplicates = merge_candidates(
        {"PointsOfInterest": {}}, candidates
    )
    assert (added, updated, duplicates) == (2, 0, 0)

    rerun, added, updated, duplicates = merge_candidates(merged, candidates)
    assert (added, updated, duplicates) == (0, 0, 2)
    assert rerun == merged


def test_default_output_uses_scenario_root_for_nested_input():
    input_path = Path(
        "/workspace/scenario_inputs/49661/extra_custom_pois/overpass_queries/"
        "cloppenburg_extra.geojson"
    )

    assert default_output_path([input_path]) == Path(
        "/workspace/scenario_inputs/49661/custom_pois.json"
    )


def test_merge_keeps_one_nearby_same_named_osm_poi_and_preserves_existing():
    existing_poi = {
        "LocationType": "Cafe",
        "Coordinates": {"Latitude": 51.18, "Longitude": 14.42},
        "TimeLimit": None,
    }
    payload = {"PointsOfInterest": {"Existing cafe": existing_poi}}
    first = PoiCandidate(
        "way/49916448",
        "Kindergarden",
        51.1939963,
        14.4470813,
        "DRK Findikus",
        {"amenity": "kindergarten", "name": "DRK Findikus"},
    )
    duplicate = PoiCandidate(
        "way/104001496",
        "Kindergarden",
        51.1940318,
        14.4472407,
        "DRK Findikus",
        {"amenity": "kindergarten", "name": "DRK Findikus"},
    )

    merged, added, updated, duplicates = merge_candidates(
        payload, [duplicate, first]
    )

    assert added == 1
    assert updated == 0
    assert duplicates == 1
    assert merged["PointsOfInterest"]["Existing cafe"] == existing_poi
    assert len(merged["PointsOfInterest"]) == 2


def test_rerunning_same_osm_feature_is_idempotent():
    candidate = PoiCandidate(
        "way/49916448",
        "Kindergarden",
        51.1939963,
        14.4470813,
        "DRK Findikus",
        {"amenity": "kindergarten", "name": "DRK Findikus"},
    )
    first, _, _, _ = merge_candidates({"PointsOfInterest": {}}, [candidate])

    merged, added, updated, duplicates = merge_candidates(first, [candidate])

    assert added == 0
    assert updated == 0
    assert duplicates == 1
    assert merged == first