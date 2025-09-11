"""
Implements the deterrence function for destination choice as used in the OMOD mobility
tool. The values returned by the function can be used as weights for destination choice.

Source: Strobel, Leo, und Marco Pruckner. „OMOD: An open-source tool for creating
disaggregated mobility demand based on OpenStreetMap“. Computers, Environment and Urban
Systems 106 (Dezember 2023): 102029. https://doi.org/10.1016/j.compenvurbsys.2023.102029.
"""

from enum import Enum
import math


class ActivityType(Enum):
    """
    Activity types to categorize destinations.
    For each type, a specific deterrence function
    is used.
    """

    work = 0
    school = 1
    shopping = 2
    other = 3


def _ln_det_pe(d: float, coeff: list[float]) -> float:
    """Deterece function in power & exponential form (PE)"""
    return coeff[0] * d + coeff[1] * math.log(d)


def _ln_det_l(d: float, coeff: list[float]) -> float:
    """Deterece function in lognormal form (L)"""
    return coeff[0] * math.log(d) ** 2 + coeff[1] * math.log(d)


def _ln_det_le(d: float, coeff: list[float]) -> float:
    """Deterece function in lognormal & exponential form (LE)"""
    return coeff[0] * math.log(d) ** 2 + coeff[1] * math.log(d) + coeff[2] * d


#: coefficients for the deterrence functions, depending on the type; source: Table 3
COEFFICIENTS = {
    ActivityType.work: [-0.035, -0.919],
    ActivityType.school: [-0.235, -1.176, 0.005],
    ActivityType.shopping: [-0.215, -1.414],
    ActivityType.other: [-0.180, -1.067],
}

#: different deterrence functions, depending on the activity type
FUNC_FORMS = {
    ActivityType.work: _ln_det_pe,
    ActivityType.school: _ln_det_le,
    ActivityType.shopping: _ln_det_l,
    ActivityType.other: _ln_det_l,
}


def omod_deterrence(distance_in_km: float, type: ActivityType) -> float:
    """The deterrence function used in the OMOD tool.
    Chooses the correct coefficients and function form depending
    on the passed activity type.

    :param distance_in_km: distance to the destination in km
    :param type: type of activity carried out at the destination
    :return: deterrence value, which can be used as a probabilistic
             weight for destination choice
    """
    deterrence_func = FUNC_FORMS[type]
    coefficients = COEFFICIENTS[type]
    return math.exp(deterrence_func(distance_in_km, coefficients))
