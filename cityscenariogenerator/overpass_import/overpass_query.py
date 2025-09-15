import itertools
import json
from pathlib import Path

#: path to the directory containing the OSM mapping files, one per OSM key
OSM_MAPPING_PATH = Path("data/osm_mapping")
#: character used as an alternative ot a colon in OSM keys for filenames
OSM_COLON_ALT = "#"


def load_osm_mapping(key_name: str) -> dict[str, list[str]]:
    key_filename = key_name.replace(":", OSM_COLON_ALT)
    with open(OSM_MAPPING_PATH / f"{key_filename}.json", "r", encoding="utf8") as f:
        mapping = json.load(f)
    # mapping file is from LPG location to OSM key value --> invert it
    inverted = {val: loc for loc, vals in mapping.items() for val in vals}
    assert set(itertools.chain.from_iterable(mapping.values())) == set(
        inverted.keys()
    ), f"Invalid OSM mapping for key {key_name}"
    return inverted


def get_osm_keys_for_mapping() -> list[str]:
    """
    Returns a list of all OSM keys for which a mapping file exist.

    :return: list of relevant OSM keys
    """
    return [p.stem.replace(OSM_COLON_ALT, ":") for p in OSM_MAPPING_PATH.iterdir()]


def generate_key_value_list(key_name: str) -> str:
    data = load_osm_mapping(key_name)
    values = set(data.keys())
    assert len(values) > 0, f"No values found for key {key_name}"
    value_str = "|".join(values)
    return f'"{key_name}"~"^({value_str})$"'


def generate_single_key_query(key_name: str) -> str:
    key_condition = generate_key_value_list(key_name)
    return f"node[{key_condition}](area.searchArea);"


def generate_query(city: str) -> str:
    # collect all relevant values for each relevant key
    key_queries = []
    for key in get_osm_keys_for_mapping():
        key_query = generate_single_key_query(key)
        key_queries.append(key_query)
    key_query_str = "\n  ".join(key_queries)
    # combine all subqueries into a single query
    query = f"""area[name="{city}"]->.searchArea;
(
  {key_query_str}
); out;"""
    return query


if __name__ == "__main__":
    query = generate_query("Aachen")
    print(query)
