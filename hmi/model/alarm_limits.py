"""Alarm limits the operator can adjust, and their defaults per patient.

Vte limits default to 4 and 10 mL/kg IBW. FiO2 and PEEP limits are automatic: they follow the set
value (FiO2 +/- 6 percentage points, never below 18 %; PEEP -3 / +5 cmH2O). No Qt imports.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from hmi.model.patient import Category, PatientProfile
from hmi.model.spec import NumericSpec

LIMIT_KEYS = ("ppeak_high", "ppeak_low", "vte_high", "vte_low", "mve_high", "mve_low", "rr_high", "apnea_time")

LIMIT_SPECS: dict[Category, dict[str, NumericSpec]] = {
    Category.ADULT: {
        "ppeak_high": NumericSpec("ppeak_high", "Ppeak high", "cmH2O", 10, 60, 1),
        "ppeak_low": NumericSpec("ppeak_low", "Ppeak low", "cmH2O", 3, 40, 1),
        "vte_high": NumericSpec("vte_high", "Vte high", "mL", 50, 2000, 10),
        "vte_low": NumericSpec("vte_low", "Vte low", "mL", 20, 1500, 10),
        "mve_high": NumericSpec("mve_high", "MVe high", "L/min", 2, 40, 0.5, 1),
        "mve_low": NumericSpec("mve_low", "MVe low", "L/min", 0.5, 30, 0.5, 1),
        "rr_high": NumericSpec("rr_high", "RR high", "bpm", 10, 70, 1),
        "apnea_time": NumericSpec("apnea_time", "Apnea time", "s", 10, 60, 1),
    },
    Category.PEDIATRIC: {
        "ppeak_high": NumericSpec("ppeak_high", "Ppeak high", "cmH2O", 10, 50, 1),
        "ppeak_low": NumericSpec("ppeak_low", "Ppeak low", "cmH2O", 3, 35, 1),
        "vte_high": NumericSpec("vte_high", "Vte high", "mL", 20, 1000, 5),
        "vte_low": NumericSpec("vte_low", "Vte low", "mL", 10, 800, 5),
        "mve_high": NumericSpec("mve_high", "MVe high", "L/min", 1, 25, 0.5, 1),
        "mve_low": NumericSpec("mve_low", "MVe low", "L/min", 0.2, 15, 0.1, 1),
        "rr_high": NumericSpec("rr_high", "RR high", "bpm", 15, 90, 1),
        "apnea_time": NumericSpec("apnea_time", "Apnea time", "s", 10, 60, 1),
    },
}
_FIXED_DEFAULTS = {
    Category.ADULT: {"ppeak_high": 40, "ppeak_low": 8, "mve_high": 15, "mve_low": 3, "rr_high": 35, "apnea_time": 20},
    Category.PEDIATRIC: {"ppeak_high": 35, "ppeak_low": 6, "mve_high": 8, "mve_low": 1, "rr_high": 50, "apnea_time": 15},
}
LIMIT_PAIRS = (("ppeak_low", "ppeak_high"), ("vte_low", "vte_high"), ("mve_low", "mve_high"))


def limit_spec(category: Category, key: str) -> NumericSpec:
    return LIMIT_SPECS[category][key]


@dataclass(frozen=True)
class AlarmLimits:
    ppeak_high: float
    ppeak_low: float
    vte_high: float
    vte_low: float
    mve_high: float
    mve_low: float
    rr_high: float
    apnea_time: float

    @classmethod
    def defaults_for(cls, patient: PatientProfile) -> "AlarmLimits":
        cat = patient.category
        values = dict(_FIXED_DEFAULTS[cat])
        values["vte_high"] = limit_spec(cat, "vte_high").clamp(10 * patient.ibw_kg)
        values["vte_low"] = limit_spec(cat, "vte_low").clamp(4 * patient.ibw_kg)
        return cls(**values)

    def get(self, key: str) -> float:
        return getattr(self, key)

    def with_value(self, key: str, value: float) -> "AlarmLimits":
        return replace(self, **{key: value})


def validate_limits(limits: AlarmLimits) -> list[str]:
    errors = []
    for low, high in LIMIT_PAIRS:
        if limits.get(low) >= limits.get(high):
            low_label = LIMIT_SPECS[Category.ADULT][low].label
            high_label = LIMIT_SPECS[Category.ADULT][high].label
            errors.append(f"{low_label} must be lower than {high_label}.")
    return errors


def fio2_limits(set_fio2: float) -> tuple[float, float]:
    return max(18.0, set_fio2 - 6.0), set_fio2 + 6.0


def peep_limits(set_peep: float) -> tuple[float, float]:
    return max(0.0, set_peep - 3.0), set_peep + 5.0
