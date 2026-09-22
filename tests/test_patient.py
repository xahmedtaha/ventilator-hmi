import pytest

from hmi.model.patient import (
    Category, PatientProfile, Sex, height_spec, ideal_body_weight,
)


def test_ibw_adult_male_ardsnet():
    assert ideal_body_weight(Category.ADULT, Sex.MALE, 170) == pytest.approx(66.0, abs=0.05)


def test_ibw_adult_female_ardsnet():
    assert ideal_body_weight(Category.ADULT, Sex.FEMALE, 160) == pytest.approx(52.4, abs=0.05)


def test_ibw_pediatric_traub_ignores_sex():
    assert ideal_body_weight(Category.PEDIATRIC, Sex.MALE, 110) == pytest.approx(18.6, abs=0.05)
    assert ideal_body_weight(Category.PEDIATRIC, Sex.FEMALE, 110) == pytest.approx(18.6, abs=0.05)


def test_default_vt_is_7_ml_per_kg_rounded_to_step():
    assert PatientProfile(height_cm=170).default_vt() == 460
    ped = PatientProfile(category=Category.PEDIATRIC, height_cm=110)
    assert ped.default_vt() == 130


def test_suggested_vt_range_is_6_to_8_ml_per_kg():
    assert PatientProfile(height_cm=170).suggested_vt_range() == (396, 528)


def test_quick_start_uses_default_heights():
    assert PatientProfile.quick_start(Category.ADULT).height_cm == 170
    assert PatientProfile.quick_start(Category.PEDIATRIC).height_cm == 110


def test_height_ranges_per_category():
    assert (height_spec(Category.ADULT).minimum, height_spec(Category.ADULT).maximum) == (140, 210)
    assert (height_spec(Category.PEDIATRIC).minimum, height_spec(Category.PEDIATRIC).maximum) == (75, 150)


def test_summary_includes_name_when_given():
    p = PatientProfile(height_cm=170, name="J. SMITH")
    assert p.summary() == "Adult · IBW 66.0 kg · J. SMITH"
