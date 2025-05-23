from pathlib import Path
from cityscenariogenerator.city_config import LPGCityConfig

from cityscenariogenerator.scenario_params import ScenarioParams
from cityscenariogenerator.plots.population_comparison import population_statistics

from cityscenariogenerator.scenario_statistics import write_person_statistics


path = Path("R:/phd_dir/data/city_scenarios/scenario_julich")
config = LPGCityConfig.load(path)

resultpath = path / "new_statistics"
resultpath.mkdir(parents=True, exist_ok=True)
write_person_statistics(config.houses.values(), resultpath)



# params = ScenarioParams({}, path, Path())
# population_statistics(params, resultpath)