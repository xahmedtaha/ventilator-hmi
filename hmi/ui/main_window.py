"""MainWindow: builds the screens and wires the device, breath analyzer, alarm engine and event log.

Data flow (see docs/03-architecture.md):
  device samples -> waveforms + breath analyzer -> alarm engine -> banner, readout colors, buzzer
  operator action -> confirmation -> new settings -> device + alarm engine + event log
"""
from __future__ import annotations

import time

from hmi.core.alarms.engine import AlarmEngine
from hmi.core.alarms.event_log import EventLog
from hmi.core.breath_analyzer import BreathAnalyzer, BreathResult
from hmi.core.flow import ScreenFlow, Step
from hmi.device.base import DeviceLink
from hmi.device.messages import MonitorStatus, Sample
from hmi.device.simulator import SimulatedDevice
from hmi.model.alarm_limits import AlarmLimits, validate_limits
from hmi.model.patient import PatientProfile
from hmi.model.settings import MODE_PARAMS, VentSettings, param_spec, switch_mode, validate_settings
from hmi.qt import QShortcut, QtCore, QtGui, QtWidgets
from hmi.ui.dialogs.alarms import AlarmsDialog
from hmi.ui.dialogs.confirm import ConfirmDialog
from hmi.ui.dialogs.demo_panel import DemoPanel
from hmi.ui.dialogs.modes import ModesDialog
from hmi.ui.screens.monitoring import MonitoringScreen
from hmi.ui.screens.patient import PatientScreen
from hmi.ui.screens.precheck import PrecheckScreen
from hmi.ui.screens.settings import SettingsScreen
from hmi.ui.setting_edit import edit_setting
from hmi.ui.top_bar import TopBar
from hmi.ui.widgets.step_indicator import StepIndicator

ALARM_TICK_MS = 200


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, device: DeviceLink, log: EventLog, clock=time.monotonic):
        super().__init__()
        self.setWindowTitle("Ventilator HMI")
        self.device, self.log, self.clock = device, log, clock
        self.flow = ScreenFlow()
        self.patient = PatientProfile()
        self.settings = VentSettings.defaults_for(self.patient)
        self.limits = AlarmLimits.defaults_for(self.patient)
        self.engine = AlarmEngine(self.settings, self.limits)
        self.analyzer = BreathAnalyzer()
        self.last_breath: BreathResult | None = None
        self._fault_codes: set[str] = set()
        self._buzzer_state: tuple[int, bool] | None = None
        self._demo_panel: DemoPanel | None = None

        self.top_bar = TopBar()
        self.steps = StepIndicator()
        self.patient_screen = PatientScreen()
        self.precheck_screen = PrecheckScreen(device)
        self.settings_screen = SettingsScreen()
        self.monitoring_screen = MonitoringScreen()
        self.stack = QtWidgets.QStackedWidget()
        for screen in (self.patient_screen, self.precheck_screen, self.settings_screen, self.monitoring_screen):
            self.stack.addWidget(screen)
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.top_bar)
        layout.addWidget(self.steps)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self._alarm_timer = QtCore.QTimer(self)
        self._alarm_timer.timeout.connect(self.update_alarms)
        shortcut = QShortcut(QtGui.QKeySequence("F12"), self)
        shortcut.activated.connect(self.open_demo_panel)
        self._connect()
        self.settings_screen.load(self.patient, self.settings, self.limits)
        self.monitoring_screen.load(self.patient, self.settings, self.limits)
        self._show_step()

    def start(self) -> None:
        self.device.open()
        self._alarm_timer.start(ALARM_TICK_MS)
        self.log.add("APP_START")

    # ----- wiring --------------------------------------------------------------------------------
    def _connect(self) -> None:
        d = self.device
        d.sample_received.connect(self._on_sample)
        d.status_received.connect(self._on_status)
        d.fault_changed.connect(self._on_fault)
        d.link_changed.connect(self._on_link)
        tb = self.top_bar
        tb.logo_long_pressed.connect(self.open_demo_panel)
        tb.banner_clicked.connect(self.open_alarms)
        tb.audio_pause_clicked.connect(self._audio_pause)
        tb.alarm_reset_clicked.connect(self._alarm_reset)
        self.patient_screen.next_requested.connect(self._patient_next)
        self.patient_screen.quick_start_requested.connect(self._quick_start)
        pc = self.precheck_screen
        pc.back_requested.connect(self._back)
        pc.skip_requested.connect(self._skip_precheck)
        pc.continue_requested.connect(self._precheck_done)
        pc.check_finished.connect(lambda k, ok, detail: self.log.add("PRECHECK_TEST", test=k, passed=ok, detail=detail))
        ss = self.settings_screen
        ss.back_requested.connect(self._back)
        ss.start_requested.connect(self._start_ventilation)
        ss.setting_changed.connect(lambda k, old, new: self.log.add("SETTING", key=k, old=old, new=new))
        ss.limit_changed.connect(lambda k, old, new: self.log.add("ALARM_LIMIT", key=k, old=old, new=new))
        ms = self.monitoring_screen
        ms.edit_setting_requested.connect(self._edit_setting)
        ms.modes_requested.connect(self._change_mode)
        ms.alarms_requested.connect(self.open_alarms)
        ms.standby_requested.connect(self._standby)

    # ----- device signals ------------------------------------------------------------------------
    def _ventilating(self) -> bool:
        return self.flow.step is Step.VENTILATING

    def _on_sample(self, s: Sample) -> None:
        now = self.clock()
        self.engine.on_sample(s, now)
        if self._ventilating():
            self.monitoring_screen.add_sample(s)
        result = self.analyzer.add(s)
        if result is not None:
            self.last_breath = result
            self.engine.on_breath(result, now)
            if self._ventilating():
                self.monitoring_screen.show_breath(result)

    def _on_status(self, m: MonitorStatus) -> None:
        self.engine.on_status(m, self.clock())
        self.top_bar.set_power(m.on_battery, m.battery_pct)
        self.monitoring_screen.show_fio2(m.fio2)

    def _on_fault(self, code: str, active: bool) -> None:
        if active:
            self._fault_codes.add(code)
        else:
            self._fault_codes.discard(code)
        self.engine.set_condition("DEVICE_FAULT", bool(self._fault_codes), self.clock(),
                                  " · ".join(sorted(self._fault_codes)))
        self.log.add("DEVICE_FAULT", code=code, active=active)

    def _on_link(self, ok: bool) -> None:
        self.engine.set_condition("LINK_LOST", not ok, self.clock())
        self.log.add("MCU_LINK", ok=ok)

    def update_alarms(self) -> None:
        """Every 200 ms: advance the alarm engine, log events, refresh the banner and the buzzer."""
        now = self.clock()
        self.engine.tick(now)
        for event in self.engine.drain_events():
            self.log.add(event.kind, alarm_id=event.alarm_id, priority=event.priority, detail=event.detail)
        states = self.engine.alarms()
        self.top_bar.banner.show_alarm(states[0] if states else None, max(0, len(states) - 1))
        paused = self.engine.audio_paused(now)
        self.top_bar.set_audio_paused(self.engine.audio_pause_remaining(now) if paused else None)
        self.monitoring_screen.show_alarm_colors(self.engine.readout_priorities())
        buzzer = (int(self.engine.audible_priority()), paused)
        if buzzer != self._buzzer_state:
            self._buzzer_state = buzzer
            self.device.set_buzzer(*buzzer)

    # ----- navigation ----------------------------------------------------------------------------
    def _show_step(self) -> None:
        step = self.flow.step
        self.stack.setCurrentIndex(int(step) - 1)
        skipped = frozenset({Step.PRECHECK}) if self.flow.precheck_skipped else frozenset()
        self.steps.set_step(step, skipped=skipped)
        self.steps.setVisible(step is not Step.VENTILATING)
        self.top_bar.set_mode(self.settings.mode.value if step is Step.VENTILATING else "STANDBY")
        self.top_bar.set_patient(self.patient.summary())

    def _set_patient(self, patient: PatientProfile) -> None:
        self.patient = patient
        self.settings = VentSettings.defaults_for(patient)
        self.limits = AlarmLimits.defaults_for(patient)
        self.engine.update_context(self.settings, self.limits)
        self.device.set_patient(patient.category)
        self.settings_screen.load(patient, self.settings, self.limits)
        self.monitoring_screen.load(patient, self.settings, self.limits)
        self.log.add("PATIENT", category=patient.category.value, sex=patient.sex.value,
                     height_cm=patient.height_cm, ibw_kg=patient.ibw_kg, name=patient.name, patient_id=patient.patient_id)

    def _patient_next(self) -> None:
        self._set_patient(self.patient_screen.profile())
        self.flow.patient_done()
        self.precheck_screen.reset()
        self._show_step()

    def _quick_start(self) -> None:
        if not ConfirmDialog.ask(self, "Quick start",
                                 "Skip the pre-use check and use the default settings for this patient?\n"
                                 "A 'Pre-use check not performed' alarm will stay on.",
                                 confirm_text="Quick start", role="danger"):
            return
        self._set_patient(self.patient_screen.profile())
        self.flow.quick_start()
        self._mark_precheck_skipped()
        self._show_step()

    def _skip_precheck(self) -> None:
        if not ConfirmDialog.ask(self, "Skip pre-use check",
                                 "The ventilator has not been verified.\n"
                                 "A 'Pre-use check not performed' alarm will stay on.",
                                 confirm_text="Skip check", role="danger"):
            return
        self.flow.skip_precheck()
        self._mark_precheck_skipped()
        self._show_step()

    def _mark_precheck_skipped(self) -> None:
        self.engine.set_condition("NO_PRECHECK", True, self.clock())
        self.log.add("PRECHECK_SKIPPED")

    def _precheck_done(self) -> None:
        self.flow.complete_precheck()
        self.engine.set_condition("NO_PRECHECK", False, self.clock())
        self.log.add("PRECHECK_PASSED")
        self._show_step()

    def _back(self) -> None:
        self.flow.back()
        self._show_step()

    def _settings_summary(self, s: VentSettings) -> str:
        parts = []
        for key in MODE_PARAMS[s.mode]:
            spec = param_spec(self.patient.category, key)
            parts.append(f"{spec.label} {spec.fmt(s.get(key))} {spec.unit}")
        return " · ".join(parts)

    def _start_ventilation(self) -> None:
        settings, limits = self.settings_screen.settings(), self.settings_screen.limits()
        errors = validate_settings(settings, self.patient.category, limits.ppeak_high) + validate_limits(limits)
        if errors:
            ConfirmDialog.inform(self, "Cannot start", "\n".join(errors))
            return
        summary = self._settings_summary(settings)
        if not ConfirmDialog.ask(self, "Start ventilation", f"Start {settings.mode.long_name} ventilation?\n\n{summary}",
                                 confirm_text="Start", role="go"):
            return
        self._apply(settings, limits)
        self.analyzer.reset()
        self.last_breath = None
        self.monitoring_screen.reset_values()
        self.device.start_ventilation()
        self.engine.set_ventilating(True, self.clock())
        self.flow.start_ventilation()
        self.log.add("VENTILATION_START", mode=settings.mode.value, settings=summary)
        self._show_step()

    def _apply(self, settings: VentSettings, limits: AlarmLimits) -> None:
        self.settings, self.limits = settings, limits
        self.engine.update_context(settings, limits)
        self.device.apply_settings(settings, limits.ppeak_high)
        self.monitoring_screen.load(self.patient, settings, limits)
        self.settings_screen.load(self.patient, settings, limits)
        if self._ventilating():
            self.top_bar.set_mode(settings.mode.value)

    # ----- actions while ventilating -------------------------------------------------------------
    def _edit_setting(self, key: str) -> None:
        new = edit_setting(self, self.patient, self.settings, self.limits, key)
        if new is None:
            return
        self.log.add("SETTING", key=key, old=self.settings.get(key), new=new.get(key))
        self._apply(new, self.limits)

    def _change_mode(self) -> None:
        mode = ModesDialog.ask(self, self.settings.mode)
        if mode is None:
            return
        last = self.last_breath
        new = switch_mode(self.settings, mode, self.patient.category,
                          last_pip=last.pip if last else None, last_vte=last.vte if last else None)
        errors = validate_settings(new, self.patient.category, self.limits.ppeak_high)
        if errors:
            ConfirmDialog.inform(self, "Cannot switch mode", "\n".join(errors))
            return
        if not ConfirmDialog.ask(self, "Change mode", f"Switch to {mode.long_name}?\n\n{self._settings_summary(new)}",
                                 confirm_text=f"Switch to {mode.value}"):
            return
        self.log.add("MODE", key="mode", old=self.settings.mode.value, new=mode.value)
        self._apply(new, self.limits)

    def open_alarms(self) -> None:
        dialog = AlarmsDialog(self, self.engine, self.log, self.patient, self.settings, self.limits, self.clock)
        dialog.limit_changed.connect(self._on_dialog_limit_changed)
        dialog.reset_requested.connect(self._alarm_reset)
        dialog.exec()

    def _on_dialog_limit_changed(self, key: str, old: float, new: float) -> None:
        self.log.add("ALARM_LIMIT", key=key, old=old, new=new)
        self._apply(self.settings, self.limits.with_value(key, new))

    def _audio_pause(self) -> None:
        self.engine.audio_pause(self.clock())
        self.update_alarms()

    def _alarm_reset(self) -> None:
        self.engine.reset(self.clock())
        self.update_alarms()

    def _standby(self) -> None:
        if not ConfirmDialog.ask(self, "Standby", "Stop ventilation?\nThe patient will NOT be ventilated.",
                                 confirm_text="Stop ventilation", role="danger"):
            return
        self.device.standby()
        self.engine.set_ventilating(False, self.clock())
        self.flow.standby()
        self.log.add("STANDBY")
        self._show_step()

    def open_demo_panel(self) -> None:
        if not isinstance(self.device, SimulatedDevice):
            return
        if self._demo_panel is None:
            self._demo_panel = DemoPanel(self, self.device)
        self._demo_panel.sync()
        self._demo_panel.show()
        self._demo_panel.raise_()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._alarm_timer.stop()
        self.device.close()
        self.log.add("APP_STOP")
        super().closeEvent(event)
