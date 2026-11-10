from scripts.generate_missing_location_queries import (
    LOCATION_SELECTORS,
    build_query,
    generate_query,
    infer_location_type,
    matching_location_types,
)


EXPECTED_MISSING_LOCATIONS = {
    "Local Recreational Area",
    "Bicycle Route",
    "Flea Market Location",
    "Singing School",
    "Fishing Location",
    "Concert House",
    "Car Wash",
    "Bow Range",
    "Hiking Location",
    "Golf Club",
    "Horse Stable",
    "Running Path",
    "Hunting Forest",
    "Fitness Studio",
    "Yoga Studio",
    "Outdoor Swimming Pool",
    "Walking Location",
    "Musical Society",
    "Festival Location",
    "Community College",
    "Soccer Practice Location",
    "Mountain Road",
}


def test_combined_query_covers_all_locations_missing_in_latest_run():
    assert set(LOCATION_SELECTORS) == EXPECTED_MISSING_LOCATIONS

    query = build_query("Bautzen")
    for location_type in EXPECTED_MISSING_LOCATIONS:
        assert f"// {location_type}" in query


def test_combined_query_searches_ways_relations_and_outputs_centers():
    query = build_query("Bautzen")

    assert "{{geocodeArea:Bautzen}}->.searchArea;" in query
    assert "(area.searchArea);" in query
    assert "nwr[" in query
    assert "relation[" in query
    assert "way[" in query
    assert "out center tags;" in query


def test_location_type_inference_handles_unique_and_ambiguous_matches():
    car_wash = {
        "id": "way/123",
        "properties": {"amenity": "car_wash"},
    }
    music_school = {
        "id": "way/456",
        "properties": {"amenity": "music_school"},
    }

    assert matching_location_types(car_wash) == {"Car Wash"}
    assert infer_location_type(car_wash) == "Car Wash"
    assert matching_location_types(music_school) == {
        "Musical Society",
    }


def test_singing_school_requires_specific_tag_and_is_not_ambiguous():
    singing_school = {
        "id": "way/789",
        "properties": {"amenity": "music_school", "subject": "singing"},
    }

    assert infer_location_type(singing_school) == "Singing School"


def test_generator_writes_one_query_file(tmp_path):
    output_path = generate_query("Bautzen", tmp_path / "missing_locations.overpassql")

    assert output_path.is_file()
    assert output_path.read_text(encoding="utf8").count("[out:json]") == 1