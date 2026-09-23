import pytest

from hmi.core.flow import InvalidTransition, ScreenFlow, Step


def test_normal_path():
    f = ScreenFlow()
    assert f.step is Step.PATIENT
    f.patient_done()
    assert f.step is Step.PRECHECK
    f.complete_precheck()
    assert f.step is Step.SETTINGS and f.precheck_passed and not f.precheck_skipped
    f.start_ventilation()
    assert f.step is Step.VENTILATING
    f.standby()
    assert f.step is Step.SETTINGS


def test_quick_start_skips_precheck():
    f = ScreenFlow()
    f.quick_start()
    assert f.step is Step.SETTINGS and f.precheck_skipped


def test_skip_precheck():
    f = ScreenFlow()
    f.patient_done()
    f.skip_precheck()
    assert f.step is Step.SETTINGS and f.precheck_skipped and not f.precheck_passed


def test_back_goes_one_step():
    f = ScreenFlow()
    f.patient_done()
    f.back()
    assert f.step is Step.PATIENT


@pytest.mark.parametrize("action", ["back", "start_ventilation", "standby", "complete_precheck"])
def test_invalid_transitions_from_patient(action):
    with pytest.raises(InvalidTransition):
        getattr(ScreenFlow(), action)()
