"""Loads a TRY data file and converts it to a file that can directly be imported by the LPG."""

import pandas as pd

path = "TRY2015.dat"
path = r"C:\Users\David-Arbeit\Downloads\TRY Download Jülich\TRY_509244063679\TRY2015_509244063679_Jahr.dat"

data = pd.read_csv(
    path, delim_whitespace=True, skip_blank_lines=False, skiprows=[33], header=32
)

year = 2015

# the LPG always uses the last value in a date based profile, and TRY values are means for one hour each
data.index = pd.date_range(
    f"{year}-01-01 00:00:00", periods=8760, freq="H", tz="Europe/Berlin"
)

assert len(data) == 24 * 365, "Unexpected number of entries"
assert (data[["MM", "DD", "HH"]].iloc[0] == 1).all(), "Unexpected start time"

# all irradiance is given as horizontal values
global_irradiance_col = "global horizontal irradiance"
temp_col = "temperature"
# global irradiance is the sum of direct (B) and diffuse (D)
data[global_irradiance_col] = data["B"] + data["D"]
data.rename(columns={"t": temp_col}, inplace=True)
data = data[[temp_col, global_irradiance_col]]

print(data.head())

data.to_csv("TRY_for_LPG.csv", sep=";", decimal=".")
