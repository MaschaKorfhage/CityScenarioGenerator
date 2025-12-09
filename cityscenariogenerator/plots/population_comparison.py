"""Population validation plots"""

import json
import logging
from pathlib import Path

from matplotlib import pyplot as plt
import pandas as pd
import seaborn as sns

from cityscenariogenerator.scenario_params import ScenarioParams

#: key for the label string in the validation data JSON files
LABEL_KEY = "label"

#: label for the generated scenario data
SCENARIO_LABEL = "Generiertes Szenario"


def plot_population_measure_stacked_bars(
    plot_result_dir: Path, measure: str, data: pd.DataFrame
):
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    ax.set_ylabel("Number of persons")
    data.T.plot(
        kind="bar",
        stacked=True,
        ax=ax,
    )

    if "total" in data.index:
        # plot the "total"  bar in grey and hatched
        pos_total = data.index.get_loc("total")
        bars = ax.containers[pos_total]
        for bar in bars:
            bar.set_hatch("//")  # type: ignore
            bar.set_facecolor("grey")  # type: ignore

    ax.tick_params(axis="x", labelrotation=0)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(plot_result_dir / f"{measure}.svg")


def plot_population_measure_bars(
    plot_result_dir: Path, measure: str, data: pd.DataFrame
):
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

    # check for an optional extra validation file with a different validation data set
    extra_validation_file = params.input_data_dir() / "validation_data/population2.json"
    extra_validation_stats = {}
    if extra_validation_file.is_file():
        with open(extra_validation_file, "r", encoding="utf8") as f:
            extra_validation_stats: dict[str, dict[str, int]] = json.load(f)

    # load the population statistics of the generated scenario
    scenario_file = params.result_directory / "statistics/person_statistics.json"
    if not scenario_file.is_file():
        logging.warning(f"Person statistics file not found: {scenario_file}")
        return
    with open(scenario_file, "r", encoding="utf8") as f:
        scenario_stats: dict[str, dict[str, int]] = json.load(f)

    plot_result_dir = result_dir / "population_validation"
    plot_result_dir.mkdir(parents=True, exist_ok=True)

    label_val: str = validation_stats[LABEL_KEY]  # type: ignore
    label_val2: str = extra_validation_stats.get(LABEL_KEY)  # type: ignore
    assert label_val != label_val2

    # process and plot statistics for each population measure (e.g., sex) individually
    for measure, validation in validation_stats.items():
        if not isinstance(validation, dict):
            continue  # this is metadata, skip this

        if measure not in scenario_stats:
            logging.warning(f"Missing population statistics measure: {measure}")
            continue

        extra_data = extra_validation_stats.get(measure)

        # build a dataframe out of the available validation and scenario data
        data_dict = {label_val: validation, SCENARIO_LABEL: scenario_stats[measure]}
        if extra_data:
            data_dict[label_val2] = extra_data
        data = pd.DataFrame(data_dict)

        # store data as a single csv file
        # data_subdir = plot_result_dir / "data"
        # data_subdir.mkdir(parents=True, exist_ok=True)
        # data.to_csv(data_subdir / f"{measure}.csv")

        sns.set_theme()
        plot_population_measure_stacked_bars(plot_result_dir, measure, data)


if __name__ == "__main__":
    result_dir = Path("R:/phd_dir/city_scenarios/scenario_juelich_04_baseline")

    params = ScenarioParams({"city": "Jülich"}, result_dir, Path())
    population_statistics(params, params.result_directory / "plots")
    print("Population validation plots created.")
