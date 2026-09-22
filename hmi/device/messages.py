"""Data exchanged between the HMI and the ventilator microcontroller (MCU). No Qt imports.

Units: pressure cmH2O, flow L/min (positive = into the patient), volume mL, time ms.
"""
from __future__ import annotations

from dataclasses import dataclass

TESTS = ("SELF", "LEAK", "COMP", "CAL", "ALARM")


@dataclass(frozen=True)
class Sample:
    t_ms: int
    pressure: float
    flow: float
    volume: float
    phase: str  # "I" = inspiration, "E" = expiration


@dataclass(frozen=True)
class MonitorStatus:
    fio2: float
    battery_pct: float
    on_battery: bool
    o2_supply_ok: bool


@dataclass(frozen=True)
class TestResult:
    __test__ = False  # not a pytest test class

    test: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class Fault:
    code: str
    active: bool


@dataclass(frozen=True)
class Ack:
    command: str
    ok: bool
    reason: str


@dataclass(frozen=True)
class Heartbeat:
    seq: int
