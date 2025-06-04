"""Generates files that give the number of persons for each template, and the
specific person names"""

from collections import defaultdict
import json
from pylpg import lpgdata

persons = [
    person
    for field in dir(lpgdata.TemplatePersons)
    if isinstance(
        (person := getattr(lpgdata.TemplatePersons, field)),
        lpgdata.TemplatePersonEntry,
    )
]

persons_by_template = defaultdict(list)
for person in persons:
    persons_by_template[person.TemplateName].append(person.PersonName)

template_sizes = {k: len(v) for k, v in persons_by_template.items()}

with open("persons_per_template.json", "w") as f:
    json.dump(template_sizes, f, indent=4)


with open("personnames_by_template.json", "w") as f:
    json.dump(persons_by_template, f, indent=4)
