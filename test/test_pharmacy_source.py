from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cityscenariogenerator import create_lpg_configs
from cityscenariogenerator.lpg_config_creator import LPGConfigCreator


@pytest.mark.parametrize(
    ("source", "city_pharmacy_count", "excluded_custom_types"),
    [
        ("city", 1, {"Pharmacy"}),
        ("custom", 0, None),
    ],
)
def test_pharmacy_source_selects_only_one_source(
    monkeypatch, source, city_pharmacy_count, excluded_custom_types
):
    creator = MagicMock()
    monkeypatch.setattr(
        create_lpg_configs.lpg_config_creator, "LPGConfigCreator", lambda params: creator
    )
    pharmacy = SimpleNamespace(
        location_type=SimpleNamespace(non_work_locations={"Pharmacy"})
    )
    shop = SimpleNamespace(
        location_type=SimpleNamespace(non_work_locations={"Shopping"})
    )

    create_lpg_configs.create_configs_from_buildings(
        MagicMock(), [], {"pharmacy": pharmacy, "shop": shop}, pharmacy_source=source
    )

    assert creator.add_poi.call_count == city_pharmacy_count + 1
    creator.add_poi.assert_any_call(shop)
    if city_pharmacy_count:
        creator.add_poi.assert_any_call(pharmacy)
    creator.load_and_add_custom_pois.assert_called_once_with(
        exclude_location_types=excluded_custom_types
    )


@pytest.mark.parametrize(
    ("excluded_types", "expected_ids"),
    [({"Pharmacy"}, {"shop"}), (None, {"pharmacy", "shop"})],
)
def test_custom_poi_loader_filters_pharmacies_only(
    monkeypatch, tmp_path, excluded_types, expected_ids
):
    custom_pois = tmp_path / "custom_pois.json"
    custom_pois.write_text("{}", encoding="utf8")
    pois = {
        "pharmacy": SimpleNamespace(LocationType="Pharmacy"),
        "shop": SimpleNamespace(LocationType="Supermarket"),
    }
    monkeypatch.setattr(
        "cityscenariogenerator.lpg_config_creator.lpgdata.CityData.from_json",
        lambda text: SimpleNamespace(PointsOfInterest=pois),
    )
    creator = LPGConfigCreator.__new__(LPGConfigCreator)
    creator.params = SimpleNamespace(custom_poi_path=lambda: custom_pois)
    creator.pois = {}
    creator.poi_ids_by_type = defaultdict(list)

    creator.load_and_add_custom_pois(exclude_location_types=excluded_types)

    assert set(creator.pois) == expected_ids
    assert creator.poi_ids_by_type["Supermarket"] == ["shop"]
    assert creator.poi_ids_by_type.get("Pharmacy", []) == (
        ["pharmacy"] if excluded_types is None else []
    )