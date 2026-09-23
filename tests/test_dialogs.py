"""Tests for Modes, Alarms and Demo Panel dialogs."""
from datetime import datetime

from hmi.core.alarms.engine import AlarmEngine
from hmi.core.alarms.event_log import EventLog
from hmi.device.messages import Sample
from hmi.device.simulator import SimulatedDevice
from hmi.model.alarm_limits import AlarmLimits
from hmi.model.patient import PatientProfile
from hmi.model.settings import Mode, VentSettings
from hmi.ui.dialogs.alarms import AlarmsDialog
from hmi.ui.dialogs.demo_panel import DemoPanel
from hmi.ui.dialogs.modes import ModesDialog

PATIENT = PatientProfile()


def test_modes_dialog_disables_current_mode(qapp):
    dialog = ModesDialog(None, Mode.VC)
    assert not dialog.buttons[Mode.VC].isEnabled()
    dialog.buttons[Mode.PC].click()
    assert dialog.selected is Mode.PC


def test_alarms_dialog_lists_active_alarms_and_log(qapp):
    settings, limits = VentSettings.defaults_for(PATIENT), AlarmLimits.defaults_for(PATIENT)
    engine = AlarmEngine(settings, limits)
    engine.set_ventilating(True, 0.0)
    engine.on_sample(Sample(0, 45.0, 0.0, 0.0, "I"), 1.0)
    log = EventLog(None, clock=lambda: datetime(2026, 9, 22, 12, 0, 0))
    log.add("SETTING", key="vt", old=460, new=500)
    log.add("ALARM_ON", alarm_id="HIGH_PRESSURE", priority="HIGH", detail="45.0 > 40 cmH2O")
    dialog = AlarmsDialog(None, engine, log, PATIENT, settings, limits, clock=lambda: 11.0)
    assert dialog.active_list.count() == 1
    assert "HIGH PRESSURE" in dialog.active_list.item(0).text()
    assert dialog.log_table.rowCount() == 2
    assert dialog.log_table.item(0, 1).text() == "ALARM_ON"
    seen = []
    dialog.reset_requested.connect(lambda: seen.append(True))
    dialog.reset_button.click()
    assert seen == [True]


def test_log_tab_refreshes_on_timer_only_when_entry_count_changed(qapp, monkeypatch):
    settings, limits = VentSettings.defaults_for(PATIENT), AlarmLimits.defaults_for(PATIENT)
    engine = AlarmEngine(settings, limits)
    log = EventLog(None, clock=lambda: datetime(2026, 9, 22, 12, 0, 0))
    dialog = AlarmsDialog(None, engine, log, PATIENT, settings, limits, clock=lambda: 11.0)
    calls = []
    real_fill = dialog._fill_log

    def spy(entries):
        calls.append(len(entries))
        real_fill(entries)

    monkeypatch.setattr(dialog, "_fill_log", spy)
    dialog._timer.timeout.emit()
    assert calls == []  # 0 entries, same as the initial (empty) table: no refresh needed
    log.add("SETTING", key="vt", old=460, new=500)
    dialog._timer.timeout.emit()
    assert calls == [1]
    assert dialog.log_table.rowCount() == 1
    dialog._timer.timeout.emit()
    assert calls == [1]  # unchanged count: no second refresh


def test_demo_panel_injects_and_resets_faults(qapp):
    device = SimulatedDevice(seed=1, sound=False)
    panel = DemoPanel(None, device)
    panel.checks["leak"].setChecked(True)
    panel.checks["link"].setChecked(True)
    panel.force_fail_box.setCurrentText("LEAK")
    assert device.lung.faults.leak_fraction == 0.5 and device.link_lost and device.force_fail == "LEAK"
    panel.reset_all()
    assert device.lung.faults.leak_fraction == 0.0 and not device.link_lost and device.force_fail is None
    assert not panel.checks["leak"].isChecked()
