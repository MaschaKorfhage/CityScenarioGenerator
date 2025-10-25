"""Additional custom data exports"""

from collections import defaultdict
from dataclasses import dataclass
import json
import logging
from pathlib import Path
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


def create_site_planning_instance(
    name: str,
    params: ScenarioParams,
    houses: dict[str, lpgdata.HouseCreationAndCalculationJob],
    poi_ids: list[str],
    demands: dict[str, float],
    distcalc: distances.DistanceCalculator,
    capacity: float,
    cost: float = 0,
):
    """Exports person and POI information as an instance
    for site planning.

    :param params: scenario parametes
    :param houses: dict of all houses
    :param pois: dict of all POIs
    :param demands: POI demand of every person
    :param distcalc: distance calculator object
    :param capacity: constant POI capacity
    :param cost: constant POI commissioning cost
    """
    logging.info("Creating custom site export file.")
    num_persons = 0
    num_sites = len(poi_ids)

    # collect capacity and costs for every POI
    poi_lines = []
    for poi in poi_ids:
        poi_lines.append(f"{capacity} {cost}\n")

    # collect demand and cost (distance) per POI for every person
    person_lines = []
    person_ids_in_order = []
    for id, hcj in houses.items():
        assert hcj.House is not None and hcj.House.Coordinates is not None
        dists = [str(distcalc.get_distance_in_km(id, poi_id)) for poi_id in poi_ids]
        dist_line = " ".join(dists)

        for i, hh in enumerate(hcj.House.Households):
            for person, _ in hh.PointOfInterestPreferences.items():
                num_persons += 1
                person_id = f"{person}_{id}_HH{i + 1}"
                person_ids_in_order.append(person_id)
                person_demand = demands[person_id]
                person_lines.append(f"{person_demand}\n")
                person_lines.append(dist_line + "\n")

    first_line = f"{num_sites} {num_persons}\n"

    # create the result file
    filepath = params.result_directory / f"instances/{name}.txt"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf8") as f:
        f.writelines([first_line])
        f.writelines(poi_lines)
        f.writelines(person_lines)
    # create additional info to relate instance results back to POI and person IDs
    info = {"poi_ids": poi_ids, "person_ids": person_ids_in_order}
    infopath = filepath.parent / f"{name}_info.json"
    utils.create_json_file(infopath, info)


def select_random_residential_sites(
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


def site_planning_export(
    params, config_creator, poi_type: str, demands_file: Path, candidate_id_file: Path
):
    """Additional custom exports

    :param params: scenario parameters
    :param config_creator: complete config creator object, after assigning POI preferences
    """
    logging.info(f"Creating a site planning instance for {poi_type} POIs")
    assert config_creator.residential_building_weights and config_creator.distcalc

    # filter existing POIs of the selected type
    pois_of_type = {
        id: config_creator.pois[id] for id in config_creator.poi_ids_by_type[poi_type]
    }

    # generate POI candidate sites
    sizes = [10, 20, 50, 100, 200, 500, 1000]
    # select_random_residential_sites(
    #     config_creator.params,
    #     sizes,
    #     config_creator.residential_building_weights,
    #     config_creator.distcalc,
    # )

    site_ids: list[str] = list(pois_of_type.keys())

    if candidate_id_file:
        # load and add more candidate site IDs
        with open(candidate_id_file, "r", encoding="utf8") as f:
            candidate_ids = json.load(f)
        site_ids += list(candidate_ids)

    # determine POI demands of all persons
    if demands_file:
        # load demands per person from file
        with open(demands_file, "r", encoding="utf8") as f:
            demands: dict[str, float] = json.load(f)
    else:
        # use a constant demand of 1
        demands = defaultdict(float, default_factory=lambda: 1)

    # calculate maximum possible service time for a POI
    total_days = 366 / 12
    work_day_ratio = 6 / 7
    opening_hours = 10
    queues = 2
    capacity = total_days * work_day_ratio * opening_hours * 60 * queues

    # define a name for the instance
    name = f"{utils.slugify(poi_type)}_{candidate_id_file.stem}"

    # custom export for pharmacy site planning
    create_site_planning_instance(
        name,
        params,
        config_creator.houses,
        site_ids,
        demands,
        config_creator.distcalc,  # type: ignore
        capacity,
    )


def site_planning_export_multiple(
    params,
    config_creator,
    poi_type: str,
    demands_file: Path,
    candidate_id_file_dir: Path,
):
    assert candidate_id_file_dir.is_dir(), f"No directory: {candidate_id_file_dir}"
    for candidate_file in candidate_id_file_dir.iterdir():
        site_planning_export(
            params, config_creator, poi_type, demands_file, candidate_file
        )
