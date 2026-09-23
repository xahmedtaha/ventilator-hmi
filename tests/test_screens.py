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


import pytest

from hmi.device.simulator import SimulatedDevice
from hmi.ui.dialogs.confirm import ConfirmDialog
from hmi.ui.screens.precheck import FAILED, PASSED, PENDING, RUNNING, PrecheckScreen


@pytest.fixture
def always_confirm(monkeypatch):
    monkeypatch.setattr(ConfirmDialog, "ask", staticmethod(lambda *a, **k: True))


def tick(device, seconds):
    for _ in range(int(seconds / 0.02)):
        device.tick()


def test_precheck_runs_all_four_tests(qapp, always_confirm):
    device = SimulatedDevice(seed=2, sound=False)
    screen = PrecheckScreen(device)
    assert not screen.continue_button.isEnabled()
    screen.run_all()
    tick(device, 16)
    assert screen.all_passed() and screen.continue_button.isEnabled()
    assert "alarm confirmed" in screen.rows["CAL"].detail_text()


def test_precheck_stops_at_first_failure_and_offers_retry(qapp, always_confirm):
    device = SimulatedDevice(seed=2, sound=False)
    screen = PrecheckScreen(device)
    device.force_fail = "LEAK"
    screen.run_all()
    tick(device, 16)
    assert screen.rows["SELF"].status == PASSED
    assert screen.rows["LEAK"].status == FAILED and not screen.rows["LEAK"].retry_button.isHidden()
    assert screen.rows["COMP"].status == PENDING
    device.force_fail = None
    screen.retry("LEAK")
    tick(device, 4)
    assert screen.rows["LEAK"].status == PASSED


def test_operator_not_hearing_alarm_fails_the_test(qapp, monkeypatch):
    answers = iter([True, True, False])  # block Y-piece, unblock Y-piece, alarm "Not heard"
    monkeypatch.setattr(ConfirmDialog, "ask", staticmethod(lambda *a, **k: next(answers, True)))
    device = SimulatedDevice(seed=2, sound=False)
    screen = PrecheckScreen(device)
    screen.run_all()
    tick(device, 16)
    assert screen.rows["CAL"].status == FAILED


def test_precheck_timeout_fails_the_running_test(qapp, always_confirm):
    device = SimulatedDevice(seed=2, sound=False)
    device.set_link_lost(True)  # a dead MCU never answers
    screen = PrecheckScreen(device)
    screen.run_all()
    assert screen.rows["SELF"].status == RUNNING
    screen._timeout.timeout.emit()  # trigger the timeout deterministically, no sleep
    assert screen.rows["SELF"].status == FAILED
    assert screen.rows["SELF"].detail_text() == "No response from the device"
    assert screen.rows["LEAK"].status == PENDING
    assert screen.rows["COMP"].status == PENDING
    assert screen.run_button.isEnabled()


from hmi.model.alarm_limits import AlarmLimits
from hmi.model.settings import Mode, VentSettings
from hmi.ui.dialogs.value_adjust import ValueAdjustDialog
from hmi.ui.screens.settings import SettingsScreen

ADULT = PatientProfile(height_cm=170)


def load_settings_screen():
    screen = SettingsScreen()
    screen.load(ADULT, VentSettings.defaults_for(ADULT), AlarmLimits.defaults_for(ADULT))
    return screen


def test_mode_switch_swaps_vt_for_pinsp(qapp):
    screen = load_settings_screen()
    seen = []
    screen.setting_changed.connect(lambda *args: seen.append(args))
    assert not screen.tiles["vt"].isHidden() and screen.tiles["pinsp"].isHidden()
    screen.mode.button("PC").click()
    assert screen.tiles["vt"].isHidden() and not screen.tiles["pinsp"].isHidden()
    assert screen.settings().mode is Mode.PC and seen == [("mode", "VC", "PC")]


def test_editing_vt_shows_advisory(qapp, monkeypatch):
    monkeypatch.setattr(ValueAdjustDialog, "ask", staticmethod(lambda *a, **k: 700))
    screen = load_settings_screen()
    screen.tiles["vt"].click()
    assert screen.settings().vt == 700
    assert "mL/kg" in screen.tiles["vt"].note_text()


def test_editing_a_limit_updates_panel(qapp, monkeypatch):
    monkeypatch.setattr(ValueAdjustDialog, "ask", staticmethod(lambda *a, **k: 45))
    screen = load_settings_screen()
    seen = []
    screen.limit_changed.connect(lambda *args: seen.append(args))
    screen.limits_panel.tiles["ppeak_high"].click()
    assert screen.limits().ppeak_high == 45 and seen == [("ppeak_high", 40, 45)]


def test_restore_defaults_emits_each_changed_limit(qapp, monkeypatch):
    monkeypatch.setattr(ValueAdjustDialog, "ask", staticmethod(lambda *a, **k: 45))
    screen = load_settings_screen()
    screen.limits_panel.tiles["ppeak_high"].click()
    assert screen.limits().ppeak_high == 45
    seen = []
    screen.limit_changed.connect(lambda *args: seen.append(args))
    monkeypatch.setattr(ConfirmDialog, "ask", staticmethod(lambda *a, **k: True))
    screen.limits_panel._restore()
    assert screen.limits().ppeak_high == 40
    assert seen[-1] == ("ppeak_high", 45, 40)


from hmi.core.alarms.definitions import Priority
from hmi.core.breath_analyzer import BreathResult
from hmi.ui.screens.monitoring import MonitoringScreen


def test_monitoring_shows_breath_values_and_alarm_colors(qapp):
    screen = MonitoringScreen()
    screen.load(ADULT, VentSettings.defaults_for(ADULT), AlarmLimits.defaults_for(ADULT))
    screen.show_breath(BreathResult(0, 20.4, 5.02, 9.6, 460, 455, 1.0, 3.3, 14.0, 6.37))
    assert screen.readouts["pip"].value_text() == "20"
    assert screen.readouts["vte"].value_text() == "455"
    assert screen.readouts["ie"].value_text() == "1:3.3"
    screen.show_alarm_colors({"pip": Priority.HIGH})
    assert screen.readouts["pip"].alarm_priority is Priority.HIGH
    assert screen.readouts["vte"].alarm_priority is Priority.NONE
    screen.reset_values()
    assert screen.readouts["pip"].value_text() == "--"


def test_monitoring_bottom_bar_follows_mode(qapp):
    screen = MonitoringScreen()
    screen.load(ADULT, VentSettings.defaults_for(ADULT).with_mode(Mode.PC), AlarmLimits.defaults_for(ADULT))
    assert screen.tiles["vt"].isHidden() and not screen.tiles["pinsp"].isHidden()
    seen = []
    screen.edit_setting_requested.connect(seen.append)
    screen.tiles["rr"].click()
    assert seen == ["rr"]
