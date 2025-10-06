"""Population validation plots"""

import json
import logging
from pathlib import Path

from matplotlib import pyplot as plt
import pandas as pd
import seaborn as sns

from cityscenariogenerator.scenario_params import ScenarioParams


def plot_population_measure_bars(
    plot_result_dir: Path, measure, scenario_stats: dict[str, int], validation
):
    data = pd.DataFrame({"Validation": validation, "Scenario": scenario_stats})
    # data_subdir = plot_result_dir / "data"
    # data_subdir.mkdir(parents=True, exist_ok=True)
    # data.to_csv(data_subdir / f"{measure}.csv")

    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    data.reset_index(names=measure, inplace=True)
    y_title = "Number of persons"
    df_long = data.melt(id_vars=measure, var_name="Dataset", value_name=y_title)

    sns.barplot(x=measure, ax=ax, y=y_title, hue="Dataset", data=df_long)
    ax.tick_params(axis="x", labelrotation=90)
    fig.align_labels()
    fig.tight_layout()
    fig.savefig(plot_result_dir / f"{measure}.svg")


def population_statistics(params: ScenarioParams, result_dir: Path):
    """Compares population statistics of the generated scenario to validation data

    :param params: scenario parameters
    :param result_dir: result directory for saving the plots
    """
    # load validation data if it exists
    validation_file = params.input_data_dir() / "validation_data/population.json"
    if not validation_file.is_file():
        logging.info("No population validation data found.")
        return
    with open(validation_file, "r", encoding="utf8") as f:
        validation_stats: dict[str, dict[str, int]] = json.load(f)

    # load the population statistics of the generated scenario
    scenario_file = params.result_directory / "statistics/person_statistics.json"
    if not scenario_file.is_file():
        logging.warning(f"Person statistics file not found: {scenario_file}")
        return
    with open(scenario_file, "r", encoding="utf8") as f:
        scenario_stats: dict[str, dict[str, int]] = json.load(f)

    plot_result_dir = result_dir / "population_validation"
    plot_result_dir.mkdir(parents=True, exist_ok=True)

    for measure, validation in validation_stats.items():
        if not isinstance(validation, dict):
            continue  # this is metadata, skip this

        if measure not in scenario_stats:
            logging.warning(f"Missing population statistics measure: {measure}")
            continue

        plot_population_measure_bars(
            plot_result_dir, measure, scenario_stats[measure], validation
        )


if __name__ == "__main__":

    result_dir = Path("R:/phd_dir/data/city_scenarios/scenario_julich")

    params = ScenarioParams({"city": "Jülich"}, result_dir, Path())
    population_statistics(params, params.result_directory / "plots")
    print("Population validation plots created.")
