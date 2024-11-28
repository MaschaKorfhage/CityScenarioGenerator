"""Generates a city scenario for the LPG from BUILDA data"""

# from cityscenariogenerator.builda_file_import.config_sample_generation import ConfigSamplingMode, SamplingModeEnum
import builda_file_import.sampling_with_builda_data.sampling_buildings_from_builda as builda_file_sampler
import builda_file_import.statistical_sampling.sampling_lpg_households as lpg_household_sampler


def import_buildings_from_builda_file():
    # get building data from builda csv file
    (
        building_ids,
        tabula_building_codes,
        conditioned_floor_areas_in_m2,
        number_of_dwellings,
        norm_heating_load_in_kw,
        postal_code,
        pv_capacities_in_kw,
        pv_generations_in_kwh,
        commodities,
        supply_levels,
        number_of_persons_per_building,
        working_status_per_building,
        female_status_per_building,
        senior_status_per_building,
    ) = builda_file_sampler.get_buildings_from_builda(number_of_random_samples=2)

    # get lpg profiles based on builda data
    dict_lpg_households = lpg_household_sampler.get_lpg_households_based_on_builda_data(
        list_dwellings_per_building=number_of_dwellings,
        list_number_of_persons_per_building=number_of_persons_per_building,
        list_working_status_per_building=working_status_per_building,
        list_female_status_per_building=female_status_per_building,
        list_senior_status_per_building=senior_status_per_building,
    )
    print(building_ids)
    print(dict_lpg_households)


if __name__ == "__main__":
    import_buildings_from_builda_file()
