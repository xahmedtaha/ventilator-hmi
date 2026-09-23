"""End-to-end smoke tests: MainWindow wiring across the full quick-start/precheck flows."""
import pytest

from hmi.core.alarms.event_log import EventLog
from hmi.core.flow import Step
from hmi.device.simulator import SimulatedDevice
from hmi.model.settings import Mode, param_spec
from hmi.ui.dialogs.confirm import ConfirmDialog
from hmi.ui.dialogs.modes import ModesDialog
from hmi.ui.main_window import MainWindow
from main import parse_args


@pytest.fixture
def window(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ConfirmDialog, "ask", staticmethod(lambda *a, **k: True))
    device = SimulatedDevice(seed=3, sound=False)
    win = MainWindow(device, EventLog(tmp_path), clock=lambda: device.sim_time)
    yield win, device
    device.close()


def run(win, device, seconds):
    from hmi.qt import QtWidgets

    qapp = QtWidgets.QApplication.instance()
    for i in range(int(seconds / 0.02)):
        device.tick()
        qapp.processEvents()  # flush deferred (singleShot(0, ...)) dialogs, e.g. the alarm test
        if i % 10 == 0:
            win.update_alarms()


def test_quick_start_to_ventilation_and_standby(window):
    win, device = window
    win.patient_screen.quick_start_requested.emit()
    assert win.flow.step is Step.SETTINGS
    win.settings_screen.start_requested.emit()
    assert win.flow.step is Step.VENTILATING
    run(win, device, 45)
    assert win.monitoring_screen.readouts["pip"].value_text() != "--"
    assert [s.id for s in win.engine.alarms()] == ["NO_PRECHECK"]
    win.monitoring_screen.standby_requested.emit()
    assert win.flow.step is Step.SETTINGS
    assert win.engine.alarms()[0].id == "NO_PRECHECK"


def test_full_pre_use_check_then_ventilate_without_alarms(window):
    win, device = window
    win.patient_screen.next_requested.emit()
    assert win.flow.step is Step.PRECHECK
    win.precheck_screen.run_all()
    run(win, device, 16)
    assert win.precheck_screen.all_passed()
    win.precheck_screen.continue_requested.emit()
    win.settings_screen.start_requested.emit()
    run(win, device, 45)
    assert win.engine.alarms() == []


def test_disconnection_reaches_the_banner(window):
    win, device = window
    win.patient_screen.quick_start_requested.emit()
    win.settings_screen.start_requested.emit()
    run(win, device, 35)
    device.lung.faults.disconnected = True
    run(win, device, 15)
    assert "LOW PRESSURE" in win.top_bar.banner.message_text()
    assert win.top_bar.banner.is_flashing()


def test_quick_start_shows_precheck_skipped_in_step_indicator(window):
    win, device = window
    win.patient_screen.quick_start_requested.emit()
    assert win.flow.precheck_skipped
    assert win.steps.text_of(Step.PRECHECK) == "✖ Pre-use check skipped"


def test_change_mode_while_ventilating_updates_settings_and_device(window, monkeypatch):
    win, device = window
    win.patient_screen.quick_start_requested.emit()
    win.settings_screen.start_requested.emit()
    run(win, device, 10)
    assert win.last_breath is not None
    peep = win.settings.peep
    expected_pinsp = param_spec(win.patient.category, "pinsp").clamp(win.last_breath.pip - peep)
    monkeypatch.setattr(ModesDialog, "ask", staticmethod(lambda *a, **k: Mode.PC))
    win._change_mode()
    assert win.settings.mode is Mode.PC
    assert win.settings.pinsp == expected_pinsp
    assert not win.monitoring_screen.tiles["pinsp"].isHidden()
    assert device.lung.settings.mode is Mode.PC
    assert device.lung.settings.pinsp == expected_pinsp


def test_alarms_dialog_from_settings_screen_does_not_discard_unsaved_edits(window, monkeypatch):
    from hmi.ui.dialogs.value_adjust import ValueAdjustDialog

    win, device = window
    win.patient_screen.quick_start_requested.emit()
    assert win.flow.step is Step.SETTINGS
    monkeypatch.setattr(ValueAdjustDialog, "ask", staticmethod(lambda *a, **k: 500))
    win.settings_screen.tiles["vt"].click()  # unsaved edit, not yet applied to win.settings
    assert win.settings_screen.settings().vt == 500
    assert win.settings.vt != 500

    dialog = win._make_alarms_dialog()
    dialog.limit_changed.emit("ppeak_high", 40, 45)

    assert win.settings_screen.settings().vt == 500  # the VT edit must survive
    assert win.settings_screen.limits().ppeak_high == 45
    assert win.limits.ppeak_high != 45  # MainWindow's own (not-yet-started) context is untouched
    dialog.close()


def test_alarm_limit_change_from_dialog_updates_everything(window):
    win, device = window
    win.patient_screen.quick_start_requested.emit()
    win.settings_screen.start_requested.emit()
    before = len(win.log.recent())
    win._on_dialog_limit_changed("ppeak_high", 40, 45)
    assert win.limits.ppeak_high == 45
    assert win.engine.limits.ppeak_high == 45
    assert win.settings_screen.limits().ppeak_high == 45
    assert device.lung.pmax == 45
    entries = win.log.recent()
    assert len(entries) == before + 1
    assert entries[0]["kind"] == "ALARM_LIMIT" and entries[0]["key"] == "ppeak_high"


def test_buzzer_resent_after_link_restored(window):
    win, device = window
    win.patient_screen.quick_start_requested.emit()
    win.settings_screen.start_requested.emit()
    device.set_o2_supply(False)
    run(win, device, 2)
    assert device.buzzer.state_text == "HIGH burst every 5 s"
    device.set_link_lost(True)
    win.update_alarms()
    assert device.buzzer.state_text == "silent"
    device.set_link_lost(False)
    run(win, device, 1)
    assert device.buzzer.state_text == "HIGH burst every 5 s"


def test_analyzer_not_fed_in_standby_and_reset_on_standby(window):
    win, device = window
    win.patient_screen.quick_start_requested.emit()
    win.settings_screen.start_requested.emit()
    run(win, device, 10)
    assert win.analyzer._samples != [] or win.last_breath is not None
    win.monitoring_screen.standby_requested.emit()
    assert win.flow.step is Step.SETTINGS
    assert win.analyzer._samples == []
    assert win.analyzer._started is False
    before = win.last_breath
    run(win, device, 5)  # ticking the device while in standby must not accumulate samples
    assert win.analyzer._samples == []
    assert win.last_breath is before


def test_quick_start_resets_stale_precheck_screen(window):
    win, device = window
    win.precheck_screen.rows["SELF"].set_status("passed", "stale pass")
    win.precheck_screen._cal_detail = "stale cal detail"
    win.patient_screen.quick_start_requested.emit()
    assert win.precheck_screen.rows["SELF"].status == "pending"
    assert win.precheck_screen._cal_detail == ""
    assert not win.precheck_screen.all_passed()


def test_open_demo_panel_creates_once_and_reuses(window):
    win, device = window
    win.open_demo_panel()
    panel = win._demo_panel
    assert panel is not None
    win.open_demo_panel()
    assert win._demo_panel is panel
    panel.hide()


def test_parse_args_defaults():
    args = parse_args([])
    assert not args.fullscreen and args.serial is None and not args.no_sound
