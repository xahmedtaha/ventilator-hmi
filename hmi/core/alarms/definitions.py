"""The one table of every alarm the HMI can raise. No Qt imports.

Each alarm has: priority (IEC 60601-1-8 high/medium/low), whether it latches, how long the
condition must last before the alarm is raised (N breaths or N seconds), whether it is
physiological (only evaluated while ventilating) and whether it is ignored during the 30 s
start-up grace period. `readout` names the measured value that turns the alarm color.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Priority(IntEnum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


PRIORITY_MARK = {Priority.HIGH: "!!!", Priority.MEDIUM: "!!", Priority.LOW: "!"}


@dataclass(frozen=True)
class AlarmDef:
    id: str
    title: str
    priority: Priority
    latching: bool
    physiological: bool = True
    delay_breaths: int = 0
    delay_s: float = 0.0
    grace: bool = False
    readout: str | None = None


_H, _M, _L = Priority.HIGH, Priority.MEDIUM, Priority.LOW

ALARMS: dict[str, AlarmDef] = {d.id: d for d in (
    AlarmDef("HIGH_PRESSURE", "HIGH PRESSURE", _H, True, readout="pip"),
    AlarmDef("LOW_PRESSURE", "LOW PRESSURE / DISCONNECT", _H, True, delay_breaths=2, readout="pip"),
    AlarmDef("SUSTAINED_PRESSURE", "SUSTAINED HIGH PRESSURE", _H, True, delay_s=15.0, readout="pip"),
    AlarmDef("APNEA", "APNEA", _H, True, readout="rr"),
    AlarmDef("LOW_FIO2", "LOW FiO2", _H, True, delay_s=30.0, grace=True, readout="fio2"),
    AlarmDef("HIGH_FIO2", "HIGH FiO2", _M, False, delay_s=30.0, grace=True, readout="fio2"),
    AlarmDef("LOW_VTE", "LOW Vte", _M, False, delay_breaths=3, grace=True, readout="vte"),
    AlarmDef("HIGH_VTE", "HIGH Vte", _M, False, delay_breaths=3, grace=True, readout="vte"),
    AlarmDef("LOW_MVE", "LOW MINUTE VOLUME", _M, False, delay_s=10.0, grace=True, readout="mve"),
    AlarmDef("HIGH_MVE", "HIGH MINUTE VOLUME", _M, False, delay_s=10.0, grace=True, readout="mve"),
    AlarmDef("HIGH_RR", "HIGH RESP. RATE", _M, False, delay_s=10.0, grace=True, readout="rr"),
    AlarmDef("LOW_PEEP", "LOW PEEP", _M, False, delay_breaths=3, grace=True, readout="peep"),
    AlarmDef("HIGH_PEEP", "HIGH PEEP", _M, False, delay_breaths=3, grace=True, readout="peep"),
    AlarmDef("O2_SUPPLY", "O2 SUPPLY FAILURE", _H, True, physiological=False),
    AlarmDef("LINK_LOST", "MCU COMMUNICATION LOST", _H, True, physiological=False),
    AlarmDef("DEVICE_FAULT", "DEVICE FAULT", _H, True, physiological=False),
    AlarmDef("ON_BATTERY", "RUNNING ON BATTERY", _L, False, physiological=False),
    AlarmDef("BATTERY_LOW", "BATTERY LOW", _M, False, physiological=False),
    AlarmDef("BATTERY_DEPLETED", "BATTERY DEPLETED", _H, True, physiological=False),
    AlarmDef("NO_PRECHECK", "PRE-USE CHECK NOT PERFORMED", _L, False, physiological=False),
)}
