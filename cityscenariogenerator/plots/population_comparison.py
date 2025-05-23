"""Population validation plots"""

import json
import logging
from pathlib import Path

from matplotlib import pyplot as plt
import pandas as pd
import seaborn as sns

from cityscenariogenerator.scenario_params import ScenarioParams


def population_statistics(params: ScenarioParams, result_dir: Path):
    """Compares population statistics of the generated scenario to validation data

    :param params: scenario parameters
    :param result_dir: result directory for saving the plots
    """
    # load validation data if it exists
    validation_file = params.input_data_dir() / "validation_data/population.json"
    if not validation_file.is_file():
        logging.info(f"No population validation data found.")
        return
    with open(validation_file, "r") as f:
        validation_stats: dict[str, dict[str, int]] = json.load(f)
    
    # load the population statistics of the generated scenario
    scenario_file = params.result_directory / "statistics/person_statistics.json"
    with open(scenario_file, "r") as f:
        scenario_stats: dict[str, dict[str, int]] = json.load(f)

    for measure, validation in validation_stats.items():
        if not isinstance(validation, dict):
            continue # this is metadata, skip this
        
        if not measure in scenario_stats:
            logging.warning(f"Missing population statistics measure: {measure}")
            continue
        
        data = pd.DataFrame({
            'Validation': validation,
            'Scenario': scenario_stats[measure]
        })
        data_subdir = result_dir / "population_validation"
        data_subdir.mkdir(parents=True, exist_ok=True)
        data.to_csv(data_subdir / f"{measure}.csv")

        fig = plt.figure()
        ax = fig.add_subplot(1, 1, 1)
        data.reset_index(names=measure, inplace=True)
        y_title = "Number of persons"
        df_long = data.melt(id_vars=measure, var_name="Dataset", value_name=y_title)

        sns.barplot(x=measure, ax=ax, y=y_title, hue="Dataset", data=df_long)
        ax.tick_params(axis='x', labelrotation=90)
        fig.align_labels()
        fig.tight_layout()
        fig.savefig(result_dir / f"population_validation_{measure}.svg")