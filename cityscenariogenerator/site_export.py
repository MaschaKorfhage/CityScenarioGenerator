"""Additional custom data exports"""

from dataclasses import dataclass
import logging
import numpy as np
from pylpg import lpgdata

from cityscenariogenerator import distances, utils
from cityscenariogenerator.scenario_params import ScenarioParams


@dataclass
class ResidentialBuildingList:
    """Simple class to store IDs and corresponding weights
    for sampling residential POIs"""

    ids: list[str]
    weights: list[float]


def location_site_export(
    params: ScenarioParams,
    houses: dict[str, lpgdata.HouseCreationAndCalculationJob],
    pois: dict[str, lpgdata.PointOfInterestData],
    distcalc: distances.DistanceCalculator,
):
    """Exports person and POI information as an instance
    for site planning.

    :param params: scenario parametes
    :param houses: dict of all houses
    :param pois: dict of all POIs
    :param distcalc: distance calculator object
    """
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
    filepath = params.result_directory / "custom_export/site_planning_instance.txt"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf8") as f:
        f.writelines([first_line])
        f.writelines(poi_lines)
        f.writelines(person_lines)


def random_residential_sites(
    params: ScenarioParams,
    sizes: list[int],
    res_building_list: ResidentialBuildingList,
    distcalc: distances.DistanceCalculator,
    min_dist_in_km: float = 0.1,
):
    """Randomly select a set of residential buildings, optionally
    wheighted by number of households.

    :param params: scenario parameters
    :param sizes: list of sizes; for every size, a set of houses of this
                  size is drawn randomly
    :param res_building_list: list of building with weights to choose from
    :param distcalc: distance calculator object to exclude houses that are
                     too close to each other
    :param min_dist_in_km: minimum distance between houses, defaults to 0.1 km
    """
    for n in sizes:
        # select n random houses, wheighted by household count
        selected_houses = np.random.choice(
            res_building_list.ids,
            n,
            # p=res_building_list.weights,
        )

        # order by weight descendingly
        weight_dict = {
            id: res_building_list.weights[i]
            for i, id in enumerate(res_building_list.ids)
        }
        by_weight = sorted(
            selected_houses, key=lambda id: weight_dict[id], reverse=True
        )

        # remove sites that are too close by
        to_remove = set()
        for i, id in enumerate(selected_houses):
            if id in to_remove:
                continue
            for other in selected_houses[i + 1 :]:
                if other in to_remove:
                    continue
                d = distcalc.get_distance_in_km(id, other)
                if d < min_dist_in_km:
                    # too close: remove the second house
                    to_remove.add(other)
        kept = [id for id in by_weight if id not in to_remove]

        # store the selected sites
        logging.info(f"Selected {len(kept)} possible sites")
        filepath = (
            params.result_directory / f"custom_export/random_residential_sites_{n}.json"
        )
        utils.create_json_file(filepath, kept)


def custom_export(params, config_creator):
    """Additional custom exports

    :param params: scenario parameters
    :param config_creator: complete config creator object, after assigning POI preferences
    """
    assert config_creator.residential_buildings and config_creator.distcalc
    random_residential_sites(
        config_creator.params,
        [10, 20, 50, 100, 200, 500, 1000],
        config_creator.residential_buildings,
        config_creator.distcalc,
    )

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
