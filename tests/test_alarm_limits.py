from hmi.model.alarm_limits import (
    AlarmLimits, fio2_limits, limit_spec, peep_limits, validate_limits,
)
from hmi.model.patient import Category, PatientProfile


def test_adult_defaults_from_ibw():
    lim = AlarmLimits.defaults_for(PatientProfile(height_cm=170))  # IBW 66.0
    assert (lim.ppeak_high, lim.ppeak_low) == (40, 8)
    assert (lim.vte_high, lim.vte_low) == (660, 260)
    assert (lim.mve_high, lim.mve_low, lim.rr_high, lim.apnea_time) == (15, 3, 35, 20)


def test_pediatric_defaults_from_ibw():
    lim = AlarmLimits.defaults_for(PatientProfile(category=Category.PEDIATRIC, height_cm=110))  # 18.6
    assert (lim.ppeak_high, lim.ppeak_low) == (35, 6)
    assert (lim.vte_high, lim.vte_low) == (185, 75)
    assert (lim.mve_high, lim.mve_low, lim.rr_high, lim.apnea_time) == (8, 1, 50, 15)


def test_low_must_be_below_high():
    lim = AlarmLimits.defaults_for(PatientProfile()).with_value("vte_low", 700)
    errors = validate_limits(lim)
    assert errors == ["Vte low must be lower than Vte high."]


def test_automatic_fio2_limits_follow_setting():
    assert fio2_limits(40) == (34, 46)
    assert fio2_limits(21) == (18, 27)


def test_automatic_peep_limits_follow_setting():
    assert peep_limits(5) == (2, 10)
    assert peep_limits(0) == (0, 5)


def test_limit_spec_lookup():
    assert limit_spec(Category.PEDIATRIC, "mve_low").step == 0.1
