"""
Generates files that give the number of persons for each template, and the
specific person names.
Can also load household template statistics of a city scenario to calculate
the distribution of household sizes.
"""

from collections import defaultdict
import json
from pathlib import Path
from pylpg import lpgdata

# collect all persons from the LPG python bindings
persons = [
    person
    for field in dir(lpgdata.TemplatePersons)
    if isinstance(
        (person := getattr(lpgdata.TemplatePersons, field)),
        lpgdata.TemplatePersonEntry,
    )
]

# group the persons by template
persons_by_template = defaultdict(list)
for person in persons:
    persons_by_template[person.TemplateName].append(person.PersonName)
print(f"Number of templates: {len(persons_by_template)}")

# calculate the number of persons in each template
template_sizes = {k: len(v) for k, v in persons_by_template.items()}

# create mapping files
with open("persons_per_template.json", "w", encoding="utf8") as f:
    json.dump(template_sizes, f, indent=4)
with open("personnames_by_template.json", "w", encoding="utf8") as f:
    json.dump(persons_by_template, f, indent=4)

# load a scenario statistics file specifying how often each LPG template occurs
scenario_dir = Path("R:/phd_dir/data/city_scenarios/scenario_julich")
with open(
    scenario_dir / "statistics/household_types.json",
    "r",
) as f:
    template_frequencies: dict[str, int] = json.load(f)

# calculate the frequency of different household sizes
household_sizes = defaultdict(int)
for template, freq in template_frequencies.items():
    size = template_sizes[template]
    household_sizes[size] += freq

# sort by household size
household_sizes = dict(sorted(household_sizes.items(), key=lambda item: item[0]))

with open(scenario_dir / "statistics/household_sizes.json", "w", encoding="utf8") as f:
    json.dump(household_sizes, f, indent=4)
