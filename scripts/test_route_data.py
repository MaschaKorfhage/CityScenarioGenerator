"""Analyze the route data from Ruben"""

import json
from collections import defaultdict

# Load the JSON data from the file
filepath = r"C:\Users\David-Arbeit\Downloads\Routen Ruben\output_reachability.json"
with open(filepath, "r", encoding="utf8") as file:
    data = json.load(file)

# Initialize dictionaries to count routes to and from each location
routes_from: defaultdict = defaultdict(int)
routes_to: defaultdict = defaultdict(int)

# Iterate over each route in the data
for key, route in data.items():
    origin = route["origin_id"]
    destination = route["destination_id"]

    # Increment the count for the origin and destination
    routes_from[origin] += 1
    routes_to[destination] += 1

# Print the results
print("Routes from each location:")
for location, count in routes_from.items():
    print(f"{location}: {count}")

print("\nRoutes to each location:")
for location, count in routes_to.items():
    print(f"{location}: {count}")

print("\n--- Differences:")
print(f"Only origin: {routes_from.keys() - routes_to.keys()}")
print(f"Only destination: {routes_to.keys() - routes_from.keys()}")
print("---")

num_res_buildings = len([x for x in routes_from.keys() if " " not in x])
print(f"\nNumber of residential buildings: {num_res_buildings}")
print(f"Number of non-residential buildings: {len(routes_from) - num_res_buildings}")
print(f"Number of routes: {len(data)}")
