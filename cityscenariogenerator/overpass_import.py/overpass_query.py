import itertools
import json
from pathlib import Path


OSM_MAPPING_PATH = Path("data/osm_mapping")


def load_osm_mapping(key_name: str) -> dict[str, list[str]]:
    with open(OSM_MAPPING_PATH / f"{key_name}.json", "r") as f:
        return json.load(f)


def generate_key_value_list(key_name: str) -> str:
    data = load_osm_mapping(key_name)
    values = set(itertools.chain.from_iterable(data.values()))
    assert len(values) > 0, f"No values found for key {key_name}"
    value_str = "|".join(values)
    return f'"{key_name}"~"{value_str}"'


def generate_single_key_query(key_name: str) -> str:
    key_condition = generate_key_value_list(key_name)
    return f"node[{key_condition}](area.searchArea);"


def generate_query(city: str) -> str:
    # collect all relevant values for each relevant key
    key_queries = []
    OSM_KEYS = ["amenity", "healthcare", "office"]
    for key in OSM_KEYS:
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
