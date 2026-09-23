"""Open the adjuster for one setting or alarm limit, with the safety cross-checks as validator.

Used by the Settings screen, the Monitoring bottom bar and the Alarms dialog, so every change goes
through the same checks.
"""
from __future__ import annotations

from hmi.model.alarm_limits import AlarmLimits, limit_spec, validate_limits
from hmi.model.patient import PatientProfile
from hmi.model.settings import VentSettings, param_spec, validate_settings
from hmi.ui.dialogs.value_adjust import ValueAdjustDialog


def edit_setting(parent, patient: PatientProfile, settings: VentSettings, limits: AlarmLimits,
                 key: str) -> VentSettings | None:
    spec = param_spec(patient.category, key)

    def validator(value: float) -> str | None:
        errors = validate_settings(settings.with_value(key, value), patient.category, limits.ppeak_high)
        return errors[0] if errors else None

    hint = ""
    if key == "vt":
        low, high = patient.suggested_vt_range()
        hint = f"Lung-protective range for IBW {patient.ibw_kg:.1f} kg: {low}–{high} mL (6–8 mL/kg)"
    value = ValueAdjustDialog.ask(parent, spec, settings.get(key), validator=validator, hint=hint)
    if value is None or value == settings.get(key):
        return None
    return settings.with_value(key, value)


def edit_limit(parent, patient: PatientProfile, settings: VentSettings, limits: AlarmLimits,
               key: str) -> AlarmLimits | None:
    spec = limit_spec(patient.category, key)

    def validator(value: float) -> str | None:
        candidate = limits.with_value(key, value)
        errors = validate_limits(candidate) + validate_settings(settings, patient.category, candidate.ppeak_high)
        return errors[0] if errors else None

    value = ValueAdjustDialog.ask(parent, spec, limits.get(key), title=f"Alarm limit: {spec.label}",
                                  validator=validator)
    if value is None or value == limits.get(key):
        return None
    return limits.with_value(key, value)
