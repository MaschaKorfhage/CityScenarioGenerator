"""A script for parsing, filtering and storing the nace codes in a suitable format for mapping buildings."""

import json
import pandas as pd

path = "data/nace_codes.txt"

data = pd.read_csv(path, sep=" - ", header=1)

# remove leading letters
data.iloc[:, 0] = data.iloc[:, 0].map(lambda s: s[1:] if len(s) > 1 else s)

# remove all but the pure letter codes and single number codes
data = data.loc[~data["Code"].str.contains(".", regex=False)]
data = data.loc[data["Code"] != ""]

print(data)

# create a JSON file mapping each nace to its description
d = dict(zip(data["Code"], data["Description"]))
with open("data/nace_code_descriptions.json", "w+") as f:
    json.dump(d, f, indent=4)

d2: dict[str, list] = {v: [] for k, v in d.items() if k.isdigit()}
with open("data/nace_codes_to_locations.json", "w+") as f:
    json.dump(d2, f, indent=4)

# data.to_csv("nace_codes_filtered.txt", index=False)
