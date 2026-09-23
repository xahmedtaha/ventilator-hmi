"""DeviceLink: the one interface the UI uses to talk to the ventilator.

Two implementations exist: SimulatedDevice (demo) and SerialDevice (real MCU over USB/UART).
Switching between them is a single line in main.py (or the --serial option), because the UI only
ever uses the signals and methods below.
"""
from __future__ import annotations

from hmi.model.patient import Category
from hmi.model.settings import VentSettings
from hmi.qt import QtCore, Signal


class DeviceLink(QtCore.QObject):
    sample_received = Signal(object)  # Sample, 50 Hz
    status_received = Signal(object)  # MonitorStatus, 1 Hz
    test_finished = Signal(object)    # TestResult
    fault_changed = Signal(str, bool)  # fault code, active
    link_changed = Signal(bool)       # True = MCU heartbeat OK

    def open(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def set_patient(self, category: Category) -> None:
        """Optional: the real MCU does not need the patient category."""

    def apply_settings(self, settings: VentSettings, pmax: float) -> None:
        raise NotImplementedError

    def start_ventilation(self) -> None:
        raise NotImplementedError

    def standby(self) -> None:
        raise NotImplementedError

    def run_test(self, test: str) -> None:
        raise NotImplementedError

    def set_buzzer(self, priority: int, paused: bool) -> None:
        raise NotImplementedError
