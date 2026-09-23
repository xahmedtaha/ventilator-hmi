"""SimulatedDevice: a fake ventilator MCU for the demo (implements DeviceLink).

Every 20 ms (50 Hz) it advances the lung model and emits a Sample; every second it emits a
MonitorStatus (FiO2, battery, O2 supply). It answers pre-use tests after a realistic delay and
plays the alarm buzzer on the computer speaker. The Demo Panel changes its faults at runtime
(see docs/04-simulator.md for the list and the alarms each fault causes).
"""
from __future__ import annotations

import random

from hmi.device.base import DeviceLink
from hmi.device.buzzer_sound import BuzzerSound
from hmi.device.lung_model import DEFAULT_LUNGS, LungFaults, LungSimulator
from hmi.device.messages import MonitorStatus, TestResult
from hmi.model.patient import Category
from hmi.model.settings import VentSettings
from hmi.qt import QtCore

TICK_S = 0.02
STATUS_EVERY_TICKS = 50
FIO2_TAU_S = 10.0
BATTERY_DEMO_START_PCT = 25.0
BATTERY_DRAIN_PER_S = 0.5
TEST_DURATION_S = {"SELF": 2.0, "LEAK": 3.0, "COMP": 3.0, "CAL": 2.5, "ALARM": 3.0}


class SimulatedDevice(DeviceLink):
    def __init__(self, parent: QtCore.QObject | None = None, seed: int | None = None, sound: bool = True):
        super().__init__(parent)
        self._rng = random.Random(seed)
        self.lung = LungSimulator(noise=1.0, seed=seed)
        self.buzzer = BuzzerSound(self, enabled=sound)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(int(TICK_S * 1000))
        self._timer.timeout.connect(self.tick)
        self._ticks = 0
        self.fio2_measured = 21.0
        self.battery_pct = 100.0
        self.on_battery = False
        self.o2_supply_ok = True
        self.link_lost = False
        self.force_fail: str | None = None
        self._pending_tests: list[tuple[float, str]] = []

    @property
    def sim_time(self) -> float:
        return self.lung.t

    # ----- DeviceLink ----------------------------------------------------------------------------
    def open(self) -> None:
        self._timer.start()
        self.link_changed.emit(True)

    def close(self) -> None:
        self._timer.stop()
        self.buzzer.shutdown()

    def set_patient(self, category: Category) -> None:
        self.lung.params = DEFAULT_LUNGS[category]

    def apply_settings(self, settings: VentSettings, pmax: float) -> None:
        self.lung.apply(settings, pmax)

    def start_ventilation(self) -> None:
        self.lung.start()

    def standby(self) -> None:
        self.lung.stop()

    def run_test(self, test: str) -> None:
        self._pending_tests.append((self.sim_time + TEST_DURATION_S[test], test))
        if test == "ALARM" and not self.link_lost and self.force_fail != "ALARM":
            self.buzzer.play_test()

    def set_buzzer(self, priority: int, paused: bool) -> None:
        if not self.link_lost:
            self.buzzer.update(priority, paused)

    # ----- Demo Panel controls -------------------------------------------------------------------
    def set_o2_supply(self, ok: bool) -> None:
        self.o2_supply_ok = ok

    def set_battery_mode(self, on: bool) -> None:
        self.on_battery = on
        self.battery_pct = min(self.battery_pct, BATTERY_DEMO_START_PCT) if on else 100.0

    def set_link_lost(self, lost: bool) -> None:
        if lost == self.link_lost:
            return
        self.link_lost = lost
        if lost:
            self.buzzer.update(0, False)  # a dead MCU cannot sound its buzzer
        self.link_changed.emit(not lost)

    def reset_faults(self) -> None:
        self.lung.faults = LungFaults()
        self.set_o2_supply(True)
        self.set_battery_mode(False)
        self.set_link_lost(False)
        self.force_fail = None

    # ----- simulation ----------------------------------------------------------------------------
    def tick(self) -> None:
        sample = self.lung.step(TICK_S)
        self._ticks += 1
        target = self.lung.settings.fio2 if (self.lung.running and self.o2_supply_ok) else 21.0
        self.fio2_measured += (target - self.fio2_measured) * TICK_S / FIO2_TAU_S
        if self.on_battery:
            self.battery_pct = max(0.0, self.battery_pct - BATTERY_DRAIN_PER_S * TICK_S)
        due = [t for t in self._pending_tests if t[0] <= self.sim_time]
        self._pending_tests = [t for t in self._pending_tests if t[0] > self.sim_time]
        if self.link_lost:
            return
        for _, test in due:
            self.test_finished.emit(self._result_for(test))
        self.sample_received.emit(sample)
        if self._ticks % STATUS_EVERY_TICKS == 0:
            self.status_received.emit(MonitorStatus(
                fio2=round(self.fio2_measured + self._rng.uniform(-0.3, 0.3), 1),
                battery_pct=round(self.battery_pct),
                on_battery=self.on_battery,
                o2_supply_ok=self.o2_supply_ok,
            ))

    def _result_for(self, test: str) -> TestResult:
        """Realistic pre-use test answers. Details never contain commas (serial protocol rule)."""
        fail = self.force_fail == test
        r = self._rng
        if test == "SELF":
            if not fail and self.battery_pct < 20:
                return TestResult(test, False, f"Battery {self.battery_pct:.0f} % (needs at least 20 %)")
            if fail:
                return TestResult(test, False, "Flow sensor not responding")
            return TestResult(test, True, f"MCU link · sensors · valves OK · battery {self.battery_pct:.0f} %")
        if test == "LEAK":
            leak = r.randint(300, 450) if fail else r.randint(30, 80)
            return TestResult(test, not fail, f"Leak {leak} mL/min (limit < 200)")
        if test == "COMP":
            if fail:
                return TestResult(test, False, f"C {r.uniform(7.5, 8.5):.1f} mL/cmH2O (limit 0.5–5.0)")
            return TestResult(test, True, f"C {r.uniform(1.8, 2.6):.1f} mL/cmH2O · R {r.uniform(2.8, 4.2):.1f} cmH2O/(L/s)")
        if test == "CAL":
            if fail:
                return TestResult(test, False, "O2 cell reads 14.8 % on air (expected 21 ± 2)")
            return TestResult(test, True, f"O2 {r.uniform(20.6, 21.6):.1f} % on air · flow zero {r.uniform(0.0, 0.2):.1f} L/min")
        if test == "ALARM":
            return TestResult(test, not fail, "Buzzer driver fault" if fail else "Buzzer burst played")
        return TestResult(test, False, f"Unknown test {test}")
