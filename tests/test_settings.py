from hmi.model.patient import Category, PatientProfile
from hmi.model.settings import (
    Mode, VentSettings, advisories, ie_text, param_spec, switch_mode, validate_settings,
)

ADULT = PatientProfile(height_cm=170)
PED = PatientProfile(category=Category.PEDIATRIC, height_cm=110)


def test_adult_defaults_use_ibw_for_vt():
    s = VentSettings.defaults_for(ADULT)
    assert (s.mode, s.vt, s.rr, s.peep, s.fio2, s.ti, s.trigger) == (Mode.VC, 460, 14, 5, 40, 1.0, 2.0)
    assert s.pinsp == 15


def test_pediatric_defaults():
    s = VentSettings.defaults_for(PED)
    assert (s.vt, s.rr, s.ti, s.pinsp, s.trigger) == (130, 20, 0.7, 12, 1.0)


def test_ie_ratio_text():
    s = VentSettings(rr=14, ti=1.0)
    assert s.ie_text == "1:3.3"
    assert ie_text(0, 2) == "--"


def test_inverse_ratio_is_rejected():
    s = VentSettings(rr=40, ti=1.0)
    errors = validate_settings(s, Category.ADULT, ppeak_high=40)
    assert len(errors) == 1 and "inverse I:E" in errors[0]


def test_vc_flow_limit_pediatric():
    s = VentSettings(vt=500, ti=0.3, rr=20)
    errors = validate_settings(s, Category.PEDIATRIC, ppeak_high=35)
    assert any("flow" in e for e in errors)


def test_pc_pressure_must_stay_below_alarm_limit():
    s = VentSettings(mode=Mode.PC, pinsp=20, peep=20)
    errors = validate_settings(s, Category.ADULT, ppeak_high=40)
    assert any("Ppeak high" in e for e in errors)


def test_valid_defaults_have_no_errors():
    assert validate_settings(VentSettings.defaults_for(ADULT), Category.ADULT, 40) == []


def test_vt_advisory_outside_6_to_8_ml_per_kg():
    notes = advisories(VentSettings(vt=700), ADULT)
    assert "vt" in notes and "10.6 mL/kg" in notes["vt"]
    assert advisories(VentSettings(vt=460), ADULT) == {}


def test_switch_vc_to_pc_uses_last_pip():
    s = VentSettings(mode=Mode.VC, peep=5, pinsp=15)
    new = switch_mode(s, Mode.PC, Category.ADULT, last_pip=21.6)
    assert new.mode is Mode.PC and new.pinsp == 17


def test_switch_pc_to_vc_uses_last_vte_clamped():
    s = VentSettings(mode=Mode.PC, vt=460)
    new = switch_mode(s, Mode.VC, Category.ADULT, last_vte=1234)
    assert new.mode is Mode.VC and new.vt == 1000


def test_param_spec_lookup():
    assert param_spec(Category.PEDIATRIC, "vt").step == 5
