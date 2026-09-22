"""Ventilation settings (VC and PC modes), their ranges, defaults and safety cross-checks.

VC = Volume Control: the machine delivers a set tidal volume (VT) with constant flow VT/Ti.
PC = Pressure Control: the machine holds PEEP + Pinsp during Ti; the volume depends on the lungs.
No Qt imports.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from hmi.model.patient import Category, PatientProfile
from hmi.model.spec import NumericSpec


class Mode(str, Enum):
    VC = "VC"
    PC = "PC"

    @property
    def long_name(self) -> str:
        return "Volume Control" if self is Mode.VC else "Pressure Control"


PARAM_KEYS = ("vt", "pinsp", "rr", "peep", "fio2", "ti", "trigger")
MODE_PARAMS = {
    Mode.VC: ("vt", "rr", "peep", "fio2", "ti", "trigger"),
    Mode.PC: ("pinsp", "rr", "peep", "fio2", "ti", "trigger"),
}

PARAM_SPECS: dict[Category, dict[str, NumericSpec]] = {
    Category.ADULT: {
        "vt": NumericSpec("vt", "VT", "mL", 200, 1000, 10),
        "pinsp": NumericSpec("pinsp", "Pinsp", "cmH2O", 5, 40, 1),
        "rr": NumericSpec("rr", "RR", "bpm", 5, 40, 1),
        "peep": NumericSpec("peep", "PEEP", "cmH2O", 0, 20, 1),
        "fio2": NumericSpec("fio2", "FiO2", "%", 21, 100, 1),
        "ti": NumericSpec("ti", "Ti", "s", 0.5, 2.5, 0.1, 1),
        "trigger": NumericSpec("trigger", "Trigger", "L/min", 1, 10, 0.5, 1),
    },
    Category.PEDIATRIC: {
        "vt": NumericSpec("vt", "VT", "mL", 50, 500, 5),
        "pinsp": NumericSpec("pinsp", "Pinsp", "cmH2O", 5, 35, 1),
        "rr": NumericSpec("rr", "RR", "bpm", 10, 60, 1),
        "peep": NumericSpec("peep", "PEEP", "cmH2O", 0, 15, 1),
        "fio2": NumericSpec("fio2", "FiO2", "%", 21, 100, 1),
        "ti": NumericSpec("ti", "Ti", "s", 0.3, 1.5, 0.1, 1),
        "trigger": NumericSpec("trigger", "Trigger", "L/min", 0.5, 5, 0.5, 1),
    },
}
PARAM_DEFAULTS = {
    Category.ADULT: {"vt": 500, "pinsp": 15, "rr": 14, "peep": 5, "fio2": 40, "ti": 1.0, "trigger": 2.0},
    Category.PEDIATRIC: {"vt": 150, "pinsp": 12, "rr": 20, "peep": 5, "fio2": 40, "ti": 0.7, "trigger": 1.0},
}
MAX_VC_FLOW_LPM = {Category.ADULT: 120.0, Category.PEDIATRIC: 60.0}
_EPS = 1e-9


def param_spec(category: Category, key: str) -> NumericSpec:
    return PARAM_SPECS[category][key]


def ie_text(ti: float, te: float) -> str:
    """I:E written as 1:x (e.g. '1:3.3')."""
    if ti <= 0:
        return "--"
    return f"1:{te / ti:.1f}"


@dataclass(frozen=True)
class VentSettings:
    mode: Mode = Mode.VC
    vt: float = 500.0
    pinsp: float = 15.0
    rr: float = 14.0
    peep: float = 5.0
    fio2: float = 40.0
    ti: float = 1.0
    trigger: float = 2.0

    @classmethod
    def defaults_for(cls, patient: PatientProfile) -> "VentSettings":
        values = dict(PARAM_DEFAULTS[patient.category])
        values["vt"] = param_spec(patient.category, "vt").clamp(patient.default_vt())
        return cls(**values)

    def get(self, key: str) -> float:
        return getattr(self, key)

    def with_value(self, key: str, value: float) -> "VentSettings":
        return replace(self, **{key: value})

    def with_mode(self, mode: Mode) -> "VentSettings":
        return replace(self, mode=mode)

    @property
    def cycle_s(self) -> float:
        return 60.0 / self.rr

    @property
    def te(self) -> float:
        return self.cycle_s - self.ti

    @property
    def ie_text(self) -> str:
        return ie_text(self.ti, self.te)

    @property
    def inspiratory_flow_lpm(self) -> float:
        return self.vt / 1000.0 / self.ti * 60.0


def validate_settings(settings: VentSettings, category: Category, ppeak_high: float) -> list[str]:
    """Safety cross-checks. An empty list means the settings may be applied."""
    errors: list[str] = []
    max_ti = 0.5 * settings.cycle_s
    if settings.ti > max_ti + _EPS:
        errors.append(
            f"Ti {settings.ti:.1f} s is too long for RR {settings.rr:.0f}: inverse I:E is not allowed "
            f"(max Ti {max_ti:.2f} s)."
        )
    if settings.mode is Mode.VC:
        flow = settings.inspiratory_flow_lpm
        limit = MAX_VC_FLOW_LPM[category]
        if flow > limit + _EPS:
            errors.append(f"Inspiratory flow {flow:.0f} L/min is above the {limit:.0f} L/min limit (VT / Ti).")
    if settings.mode is Mode.PC and settings.peep + settings.pinsp > ppeak_high - 2 + _EPS:
        errors.append(
            f"PEEP + Pinsp = {settings.peep + settings.pinsp:.0f} cmH2O must be at least 2 below "
            f"the Ppeak high alarm limit ({ppeak_high:.0f})."
        )
    return errors


def advisories(settings: VentSettings, patient: PatientProfile) -> dict[str, str]:
    """Non-blocking notes shown with an orange border (not alarms)."""
    notes: dict[str, str] = {}
    if settings.mode is Mode.VC:
        per_kg = settings.vt / patient.ibw_kg
        if not 6.0 <= per_kg <= 8.0:
            notes["vt"] = f"{per_kg:.1f} mL/kg IBW (lung-protective: 6–8)"
    return notes


def switch_mode(
    settings: VentSettings,
    mode: Mode,
    category: Category,
    last_pip: float | None = None,
    last_vte: float | None = None,
) -> VentSettings:
    """Change mode while keeping ventilation similar: VC->PC uses the last PIP, PC->VC the last Vte."""
    new = settings.with_mode(mode)
    if mode is Mode.PC and last_pip is not None:
        new = new.with_value("pinsp", param_spec(category, "pinsp").clamp(last_pip - settings.peep))
    if mode is Mode.VC and last_vte is not None:
        new = new.with_value("vt", param_spec(category, "vt").clamp(last_vte))
    return new
