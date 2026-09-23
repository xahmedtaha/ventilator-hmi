"""End-to-end smoke tests: MainWindow wiring across the full quick-start/precheck flows."""
import pytest

from hmi.core.alarms.event_log import EventLog
from hmi.core.flow import Step
from hmi.device.simulator import SimulatedDevice
from hmi.ui.dialogs.confirm import ConfirmDialog
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
    for i in range(int(seconds / 0.02)):
        device.tick()
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


def test_parse_args_defaults():
    args = parse_args([])
    assert not args.fullscreen and args.serial is None and not args.no_sound
