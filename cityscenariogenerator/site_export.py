"""Additional custom data exports"""

import logging
from pylpg import lpgdata

from cityscenariogenerator import distances
from cityscenariogenerator.scenario_params import ScenarioParams


def location_site_export(
    params: ScenarioParams,
    houses: dict[str, lpgdata.HouseCreationAndCalculationJob],
    pois: dict[str, lpgdata.PointOfInterestData],
    distcalc: distances.DistanceCalculator,
):
    logging.info("Creating custom site export file.")
    num_persons = 0
    num_sites = len(pois)

    # collect capacity and costs for every POI
    poi_lines = []
    for poi in pois:
        capacity = 5000
        cost = 10e6
        poi_lines.append(f"{capacity} {cost}\n")

    # collect demand and cost (distance) per POI for every person
    person_lines = []
    for id, hcj in houses.items():
        assert hcj.House is not None and hcj.House.Coordinates is not None
        dists = [str(distcalc.get_distance_in_km(id, poi_id)) for poi_id in pois.keys()]
        dist_line = " ".join(dists)

        for hh in hcj.House.Households:
            for person, _ in hh.PointOfInterestPreferences.items():
                num_persons += 1
                person_demand = 1  # Todo: after first city simulation, number of POI visits per person can be used here
                person_lines.append(f"{person_demand}\n")
                person_lines.append(dist_line + "\n")

    first_line = f"{num_sites} {num_persons}\n"

    # create the result file
    filepath = params.result_directory / "custom_export/sites.txt"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf8") as f:
        f.writelines([first_line])
        f.writelines(poi_lines)
        f.writelines(person_lines)


def custom_export(params, config_creator):
    """Additional custom exports

    :param params: scenario parameters
    :param config_creator: complete config creator object, after assigning POI preferences
    """
    # custom export for pharmacy site planning
    location_site_export(
        params,
        config_creator.houses,
        {
            id: config_creator.pois[id]
            for id in config_creator.poi_ids_by_type["Pharmacy"]
        },
        config_creator.distcalc,  # type: ignore
    )
