# ETHOS.CityScenarioGenerator
ETHOS.CityScenarioGenerator is a tool designed to create city scenarios for an integrated city simulation with the [LoadProfileGenerator](https://www.loadprofilegenerator.de/).
It extracts residential and non-residential buildings from the building database [ETHOS.BUILDA](https://github.com/FZJ-IEK3-VSA/ethos-builda-client) and optionally other sources, such as OpenStreetMap, maps them to corresponding categories in the LoadProfileGenerator model, and saves everything as a directory of config files. This directory can then be used as input for the LoadProfileGenerator city simulation to simulate behavior, transportation, entreprise visits times and energy demands for a whole city.

## Installation
To set up the ETHOS.CityScenarioGenerator for usage, clone this repository and install it, e.g. with pip:

    pip install -e .


## Usage
To generate a scenario, run cityscenariogenerator/main.py, e.g. like this:

    python cityscenariogenerator/main.py --city "Jülich" --street "Große Rurstr."

This will generate a scenario directory in the output folder ("./scenario" by default). This scenario directory can then be used to start a city simulation with the LoadProfileGenerator.

To get more information about the available parameters, run the following command:

    python cityscenariogenerator/main.py --help
