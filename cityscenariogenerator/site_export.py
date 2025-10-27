"""Additional custom data exports"""

from collections import defaultdict
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from dataclasses_json import dataclass_json
import numpy as np
from pylpg import lpgdata

from cityscenariogenerator import distances, utils
from cityscenariogenerator.lpg_config_creator import (
    LPGConfigCreator,
    ResidentialBuildingList,
)
from cityscenariogenerator.scenario_params import ScenarioParams


@dataclass
class PersonId:
    """Scenario-wide unique ID object for a person"""

    house: str
    hh_index: int
    name: str


def get_person_id_str(house_id: str, hh_index: int, person_name: str) -> str:
    """Returns a person ID str matching the style of ActivityAssure
    activity profile filenames, e.g., "CHR42 Jessica_DEA_DENW40AL10000B7u-0_HH1"

    :param house_id: house id
    :param hh_index: index of the household in the house, zero-based
    :param person_name: person name
    :return: person ID str
    """
    return f"{person_name}_{house_id}_HH{hh_index + 1}"


def parse_person_id(person_id: str) -> PersonId:
    """Parses person ID strs in the format "CHR42 Jessica_DEA_DENW40AL10000B7u-0_HH1".

    :param person_id: the person ID str
    :returns: the person ID object
    """
    # components are separated by an underscore; name is first, HH number last
    parts = person_id.split("_")
    name = parts[0]
    hh = parts[-1]
    hh_index = int(hh.removeprefix("HH"))
    # the rest is the house ID
    house = "_".join(parts[1:-1])
    return PersonId(house, hh_index, name)


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
                person_id = get_person_id_str(id, i, person)
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
    params: ScenarioParams,
    config_creator: LPGConfigCreator,
    poi_type: str,
    demands_file: Path,
    candidate_id_file: Path,
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
    # sizes = [10, 20, 50, 100, 200, 500, 1000]
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
    params: ScenarioParams,
    config_creator: LPGConfigCreator,
    poi_type: str,
    demands_file: Path,
    candidate_id_file_dir: Path,
):
    assert candidate_id_file_dir.is_dir(), f"No directory: {candidate_id_file_dir}"
    for candidate_file in candidate_id_file_dir.iterdir():
        site_planning_export(
            params, config_creator, poi_type, demands_file, candidate_file
        )


def create_pharmacy_instances(params: ScenarioParams, config_creator: LPGConfigCreator):
    """Example to create instances for pharmacy site planning"""
    poi_type = "Pharmacy"
    subdir = params.input_data_dir() / utils.slugify(poi_type)
    demands_file = subdir / "demands.json"
    candidate_file_dir = subdir / "site_candidates/random_residential_unweighted"
    if not demands_file.is_file() or not candidate_file_dir.is_dir():
        logging.warning(f"No data for {poi_type} instace generation.")
        return

    site_planning_export_multiple(
        params, config_creator, poi_type, demands_file, candidate_file_dir
    )


@dataclass_json
@dataclass
class SitePlanningResult:
    """Stores result of a site planning model run. These results
    must be taken into account when creating POIs of the affected type
    for a scenario."""

    #: the poi type the planning results affect
    poi_type: str
    #: the selected building/POI IDs for sites, can be residential or non-residential
    selected_sites: list[str]
    site_preferences: dict[str, str]


def get_selected_sites(
    poi_type: str, instance_info_file: Path, result_file: Path
) -> SitePlanningResult:
    """Loads and returns the results of a site planning model run.

    :param poi_type: the affected POI type
    :param instance_info_file: the path to the instance info file
    :param result_file: the path to the model result file
    :return: the model results with selected POIs and person preferences
    """
    with open(result_file, "r", encoding="utf8") as f:
        results = json.load(f)
    with open(instance_info_file, "r", encoding="utf8") as f:
        info = json.load(f)

    # get the list of site candidates
    candidate_ids = info["poi_ids"]
    person_ids = info["person_ids"]
    assert isinstance(candidate_ids, list) and isinstance(person_ids, list), (
        f"Unexpected instance info file format: {instance_info_file}"
    )

    # get the IDs of the sites selected by the model; the model provides the indices
    # of the selected sites in the original site candidate list
    selected_indices = results["solution"]["incumbent"]
    assert selected_indices != "infeasible", "The instance was infeasible"
    selected_sites = [candidate_ids[i] for i in selected_indices]

    # get the person preferences; the model provides a list, each item specifying the
    # preference of the person at the same index in the original person list; the
    # preference is again given as index of the site in the candidate list
    preference_indices = results["solution"]["assignments"]
    preferences = {
        person_ids[i]: candidate_ids[i_pref]
        for i, i_pref in enumerate(preference_indices)
    }
    assert set(preferences.values()) == set(selected_sites), "Model result format error"

    return SitePlanningResult(poi_type, selected_sites, preferences)


def apply_site_planning_results(
    config_creator: LPGConfigCreator, results: SitePlanningResult
):
    """Applies the site planning resulst by removing not selected POIs
    and creating new custom POIs for any new selected sites.
    Must be called after config_creator.create_poi_preferences.
    Assumes no POI preferences have been set for the affected POI
    type yet (and so does not delete any existing preferences, just adds
    new ones).

    :param config_creator: config creator object
    :param results: site planning result object
    """
    # remove all POIs of the affected type that have not been selected
    for poi_id in config_creator.poi_ids_by_type[results.poi_type]:
        if poi_id not in results.selected_sites:
            config_creator.remove_poi(poi_id)
            # global city definition might not contain the POI, so use pop instead of del
            x = config_creator.global_city_definition.PointsOfInterest.pop(poi_id, None)
            if x is None:
                logging.warning(
                    f"Could not find unselected POI {poi_id} in global city definition"
                )

    # store the POI ID corresponding to each site ID
    site_poi_map: dict[str, str] = {}
    kept_pois = 0
    # create custom POIs for all sites that are not contained as POIs yet
    for site in results.selected_sites:
        if site in config_creator.pois:
            # site is an existing POI that was decided to keep
            site_poi_map[site] = site
            kept_pois += 1
            continue
        # the site is a residential building - create a custom POI
        house = config_creator.houses[site]
        new_poi = lpgdata.PointOfInterestData(results.poi_type, house.House.Coordinates)  # type: ignore
        poi_id = utils.create_poi_id(site, results.poi_type)
        config_creator._add_poi_object(poi_id, new_poi)
        config_creator.global_city_definition.PointsOfInterest[poi_id] = new_poi
        site_poi_map[site] = poi_id
    logging.info(f"Kept {kept_pois} of the original {results.poi_type} POIs")

    # apply the person preferences
    for house_id, house in config_creator.houses.items():
        # remove the subset of relevant POIs
        house.City = None
        assert house.House
        for hh_index, hh in enumerate(house.House.Households):
            for person, prefs in hh.PointOfInterestPreferences.items():
                # remove all existing POI preferences for the affected POI type
                existing_pref_ids = list(prefs.PoiWeights.keys())
                for poi_id in existing_pref_ids:
                    if results.poi_type in poi_id:
                        del prefs.PoiWeights[poi_id]

                # set the new POI preference
                person_id = get_person_id_str(house_id, hh_index, person)
                pref_site = results.site_preferences[person_id]
                new_pref_poi = site_poi_map[pref_site]
                prefs.PoiWeights[new_pref_poi] = 1


def apply_eplpo_pharmacy_results(
    params: ScenarioParams, config_creator: LPGConfigCreator
):
    """Applies pharmacy site planning results from the eplpo mode.
    Must be called after config_creator.create_poi_preferences()

    :param config_creator: config creator object
    """
    name = "pharmacy_random_residential_sites_10"
    model_type = 0
    eplpo_data_dir = Path("/fast/home/d-neuroth/phd_dir/pharmacy_data")
    instance_dir = eplpo_data_dir / "instances"
    result_file = eplpo_data_dir / "results" / f"{name}_{model_type}_IPsolution.json"
    # instance_file = instance_dir / f"{name}.txt"
    instance_info = instance_dir / f"{name}_info.json"
    logging.info(f"Applying result of site planning: {name}")
    results = get_selected_sites("Pharmacy", instance_info, result_file)

    # store the model results with proper IDs in a separate file
    results_path = (
        params.result_directory / f"instances/results/results_{name}_{model_type}.json"
    )
    utils.create_json_file(results_path, results.to_dict())  # type: ignore

    logging.info(f"Site planning selected {len(results.selected_sites)} sites")
    apply_site_planning_results(config_creator, results)
