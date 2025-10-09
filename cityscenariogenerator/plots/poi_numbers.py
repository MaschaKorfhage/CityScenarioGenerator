"""Plot that shows the number of each type of POI in the scenario"""

import json
import logging
from pathlib import Path
from matplotlib import pyplot as plt
import seaborn as sns
import pandas as pd

from pylpg import lpgdata

from cityscenariogenerator.scenario_params import ScenarioParams

from cityscenariogenerator import utils


def plot_poi_numbers(params: ScenarioParams, result_dir: Path):
    """Creates bar charts showing the numbers of each POI type, split into
    frequent and less frequent POIs.

    :param params: scenario parameters
    :param result_dir: plot result directory
    """
    poi_types_file = params.result_directory / "statistics/poi_types_all.json"
    if not poi_types_file.is_file():
        logging.warning(f"POI type statistics file not found: {poi_types_file}")
        return
    with open(poi_types_file, "r", encoding="utf8") as f:
        pois: dict[str, int] = json.load(f)

    # load the custom POIs from file
    with open(params.custom_poi_path(), "r", encoding="utf8") as f:
        json_str = f.read()
        custom_pois: dict[str, lpgdata.PointOfInterestData] = (
            lpgdata.CityData.from_json(json_str).PointsOfInterest  # type: ignore
        )
    custom_poi_locations = {str(p.LocationType) for p in custom_pois.values()}

    # filter out custom POIs
    filtered = {k: v for k, v in pois.items() if k not in custom_poi_locations}

    # split into more and less frequent POIs, for better readability of the charts
    limit = 100
    frequent = {k: v for k, v in filtered.items() if v >= limit}
    rare = {k: v for k, v in filtered.items() if v < limit}

    # sort for readability
    plot_poi_numbers_bars(
        result_dir / "poi_numbers_small.svg",
        rare,
    )
    plot_poi_numbers_bars(result_dir / "poi_numbers_large.svg", frequent)


def plot_poi_numbers_bars(
    plot_path: Path, poi_numbers: dict[str, int], log: bool = False
):
    """Create a bar chart for the POI numbers

    :param plot_path: _description_
    :param filtered: _description_
    :param log: _description_, defaults to False
    """
    poi_numbers = utils.sort_by_val(poi_numbers, True)
    df = pd.DataFrame(list(poi_numbers.items()), columns=["Location", "Anzahl"])

    # plot
    sns.set_theme()

    fig = plt.figure(figsize=(8, 6))
    ax = sns.barplot(data=df, y="Location", x="Anzahl")
    if log:
        ax.set_xscale("log")

    plt.tight_layout()

    fig.savefig(plot_path)


if __name__ == "__main__":
    result_dir = Path(
        "C:/Home/Git-Repositories/cityscenariogenerator/scenarios/scenario_julich"
    )
    params = ScenarioParams({"city": "Jülich"}, result_dir, Path())
    plot_poi_numbers(params, params.result_directory / "plots")
