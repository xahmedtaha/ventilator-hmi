from hmi.model.patient import Category, PatientProfile
from hmi.ui.screens.patient import PatientScreen


def test_patient_screen_updates_ibw_live(qapp):
    screen = PatientScreen()
    assert screen.ibw_text() == "66.0 kg"
    screen.height_adjuster.step(+1)
    assert screen.profile().height_cm == 171
    screen.sex.button("female").click()
    assert screen.ibw_text() == "62.4 kg"  # 45.5 + 0.91 x (171 - 152.4)


def test_switching_to_pediatric_resets_height(qapp):
    screen = PatientScreen()
    screen.category.button("pediatric").click()
    p = screen.profile()
    assert p.category is Category.PEDIATRIC and p.height_cm == 110
    assert screen.height_adjuster.value() == 110


def test_set_profile_round_trip(qapp):
    screen = PatientScreen()
    p = PatientProfile(category=Category.PEDIATRIC, height_cm=120, name="TEST")
    screen.set_profile(p)
    assert screen.profile() == p
