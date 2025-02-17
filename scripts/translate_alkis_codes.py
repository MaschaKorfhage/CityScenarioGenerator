"""A script for parsing, filtering and storing the ALKIS codes in a suitable format for mapping buildings."""

import json
import pandas as pd

path = "data/alkis_codes.csv"

data = pd.read_csv(path)

# filter out residential buildings
data = data[data["type"] != "residential"]

print(data)


# create a JSON file mapping each ALKIS code to its description
d = dict(zip(data["name"], data["description"]))
with open("data/alkis_code_descriptions.json", "w+", encoding="utf8") as f:
    json.dump(d, f, indent=4, ensure_ascii=False)

d2: dict[str, list] = {v: [] for k, v in d.items()}
with open("data/alkis_codes_to_locations.json", "w+", encoding="utf8") as f:
    json.dump(d2, f, indent=4, ensure_ascii=False)
