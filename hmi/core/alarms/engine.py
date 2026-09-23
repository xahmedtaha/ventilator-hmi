"""Alarm engine: decides which alarms are active. No Qt imports.

The caller passes the current time `now` (seconds, monotonic) into every method, which keeps the
behavior deterministic and easy to test. Rules (see docs/02-alarms.md):
- An alarm is raised only after its delay (N consecutive breaths or N continuous seconds).
- High-priority alarms latch: when the condition ends they stay listed as "resolved" until Alarm Reset.
- Audio Paused silences the buzzer for 120 s; any new alarm ends the pause.
- Physiological alarms are evaluated only while ventilating; volume, rate, PEEP and FiO2 alarms
  are ignored during the first 30 s after Start (grace period).
- Only alarms whose condition is still true sound; resolved (latched) alarms are visual only.
"""
from __future__ import annotations

from dataclasses import dataclass

from hmi.core.alarms.definitions import ALARMS, PRIORITY_MARK, AlarmDef, Priority
from hmi.core.breath_analyzer import BreathResult
from hmi.device.messages import MonitorStatus, Sample
from hmi.model.alarm_limits import AlarmLimits, fio2_limits, peep_limits
from hmi.model.settings import VentSettings

GRACE_S = 30.0
AUDIO_PAUSE_S = 120.0
SUSTAINED_MARGIN_CMH2O = 15.0
BATTERY_LOW_PCT = 20.0
BATTERY_DEPLETED_PCT = 5.0


@dataclass
class AlarmState:
    definition: AlarmDef
    onset: float
    detail: str = ""
    active: bool = True  # False = condition ended, kept only because the alarm latches

    @property
    def id(self) -> str:
        return self.definition.id

    @property
    def priority(self) -> Priority:
        return self.definition.priority

    @property
    def message(self) -> str:
        text = f"{PRIORITY_MARK[self.priority]} {self.definition.title}"
        if self.detail:
            text += f"  {self.detail}"
        if not self.active:
            text += "  (resolved)"
        return text


@dataclass(frozen=True)
class AlarmEvent:
    kind: str  # ALARM_ON | ALARM_OFF | ALARM_RESET | AUDIO_PAUSED
    alarm_id: str = ""
    priority: str = ""
    detail: str = ""


class AlarmEngine:
    def __init__(self, settings: VentSettings, limits: AlarmLimits):
        self.settings = settings
        self.limits = limits
        self._ventilating = False
        self._vent_start = 0.0
        self._last_breath: float | None = None
        self._states: dict[str, AlarmState] = {}
        self._pending: dict[str, float] = {}  # breath count or first-true time, per alarm
        self._pause_until: float | None = None
        self._events: list[AlarmEvent] = []

    # ----- context -------------------------------------------------------------------------------
    def update_context(self, settings: VentSettings, limits: AlarmLimits) -> None:
        self.settings = settings
        self.limits = limits

    @property
    def ventilating(self) -> bool:
        return self._ventilating

    def set_ventilating(self, on: bool, now: float) -> None:
        if on == self._ventilating:
            return
        self._ventilating = on
        if on:
            self._vent_start = now
            self._last_breath = now
            return
        self._last_breath = None
        for alarm_id in [a for a, s in self._states.items() if s.definition.physiological]:
            del self._states[alarm_id]
        for alarm_id in [a for a in self._pending if ALARMS[a].physiological]:
            del self._pending[alarm_id]

    # ----- inputs --------------------------------------------------------------------------------
    def on_sample(self, s: Sample, now: float) -> None:
        high = self.limits.ppeak_high
        if s.pressure > high:
            self._evaluate("HIGH_PRESSURE", True, now, f"{s.pressure:.1f} > {high:.0f} cmH2O")
        threshold = self.settings.peep + SUSTAINED_MARGIN_CMH2O
        self._evaluate("SUSTAINED_PRESSURE", s.pressure > threshold, now, f"above {threshold:.0f} cmH2O")

    def on_breath(self, r: BreathResult, now: float) -> None:
        self._last_breath = now
        lim = self.limits
        checks = (
            ("HIGH_PRESSURE", r.pip > lim.ppeak_high, f"{r.pip:.1f} > {lim.ppeak_high:.0f} cmH2O"),
            ("LOW_PRESSURE", r.pip < lim.ppeak_low, f"{r.pip:.1f} < {lim.ppeak_low:.0f} cmH2O"),
            ("LOW_VTE", r.vte < lim.vte_low, f"{r.vte:.0f} < {lim.vte_low:.0f} mL"),
            ("HIGH_VTE", r.vte > lim.vte_high, f"{r.vte:.0f} > {lim.vte_high:.0f} mL"),
            ("LOW_MVE", r.mve < lim.mve_low, f"{r.mve:.1f} < {lim.mve_low:.1f} L/min"),
            ("HIGH_MVE", r.mve > lim.mve_high, f"{r.mve:.1f} > {lim.mve_high:.1f} L/min"),
            ("HIGH_RR", r.rr > lim.rr_high, f"{r.rr:.0f} > {lim.rr_high:.0f} bpm"),
        )
        for alarm_id, condition, detail in checks:
            self._evaluate(alarm_id, condition, now, detail, breath=True)
        low, high = peep_limits(self.settings.peep)
        self._evaluate("LOW_PEEP", r.peep < low, now, f"{r.peep:.1f} < {low:.0f} cmH2O", breath=True)
        self._evaluate("HIGH_PEEP", r.peep > high, now, f"{r.peep:.1f} > {high:.0f} cmH2O", breath=True)

    def on_status(self, m: MonitorStatus, now: float) -> None:
        low, high = fio2_limits(self.settings.fio2)
        self._evaluate("LOW_FIO2", m.fio2 < low, now, f"{m.fio2:.0f} < {low:.0f} %")
        self._evaluate("HIGH_FIO2", m.fio2 > high, now, f"{m.fio2:.0f} > {high:.0f} %")
        self._evaluate("O2_SUPPLY", not m.o2_supply_ok, now, "check O2 inlet")
        pct = m.battery_pct
        depleted = m.on_battery and pct < BATTERY_DEPLETED_PCT
        low_batt = m.on_battery and not depleted and pct < BATTERY_LOW_PCT
        on_batt = m.on_battery and not depleted and not low_batt
        detail = f"{pct:.0f} %"
        self._evaluate("BATTERY_DEPLETED", depleted, now, detail)
        self._evaluate("BATTERY_LOW", low_batt, now, detail)
        self._evaluate("ON_BATTERY", on_batt, now, detail)

    def set_condition(self, alarm_id: str, active: bool, now: float, detail: str = "") -> None:
        """For conditions detected elsewhere (MCU link, device faults, skipped pre-use check)."""
        self._evaluate(alarm_id, active, now, detail)

    def tick(self, now: float) -> None:
        """Call regularly (every 200 ms): ends Audio Paused and checks apnea."""
        if self._pause_until is not None and now >= self._pause_until:
            self._pause_until = None
        if self._ventilating and self._last_breath is not None:
            silent = now - self._last_breath
            self._evaluate("APNEA", silent > self.limits.apnea_time, now, f"no breath for {silent:.0f} s")

    # ----- operator actions ----------------------------------------------------------------------
    def audio_pause(self, now: float) -> None:
        self._pause_until = now + AUDIO_PAUSE_S
        self._events.append(AlarmEvent("AUDIO_PAUSED", detail=f"{AUDIO_PAUSE_S:.0f} s"))

    def audio_paused(self, now: float) -> bool:
        return self._pause_until is not None and now < self._pause_until

    def audio_pause_remaining(self, now: float) -> float:
        return max(0.0, self._pause_until - now) if self._pause_until is not None else 0.0

    def reset(self, now: float) -> None:
        """Alarm Reset: remove resolved (latched) alarms. Alarms whose condition is still true stay."""
        resolved = [a for a, s in self._states.items() if not s.active]
        for alarm_id in resolved:
            del self._states[alarm_id]
        self._events.append(AlarmEvent("ALARM_RESET", detail=f"{len(resolved)} cleared"))

    # ----- outputs -------------------------------------------------------------------------------
    def alarms(self) -> list[AlarmState]:
        """Active first, then by priority, then newest first."""
        return sorted(self._states.values(), key=lambda s: (s.active, s.priority, s.onset), reverse=True)

    def audible_priority(self) -> Priority:
        return max((s.priority for s in self._states.values() if s.active), default=Priority.NONE)

    def readout_priorities(self) -> dict[str, Priority]:
        result: dict[str, Priority] = {}
        for s in self._states.values():
            key = s.definition.readout
            if s.active and key:
                result[key] = max(result.get(key, Priority.NONE), s.priority)
        return result

    def drain_events(self) -> list[AlarmEvent]:
        events, self._events = self._events, []
        return events

    # ----- internals -----------------------------------------------------------------------------
    def _evaluate(self, alarm_id: str, condition: bool, now: float, detail: str = "",
                  breath: bool = False) -> None:
        d = ALARMS[alarm_id]
        if d.physiological and not self._ventilating:
            condition = False
        if condition and d.grace and now - self._vent_start < GRACE_S:
            condition = False
        if not condition:
            self._pending.pop(alarm_id, None)
            self._resolve(alarm_id)
            return
        state = self._states.get(alarm_id)
        if state is not None and state.active:
            state.detail = detail
            return
        if self._delay_met(d, now, breath):
            self._raise(d, now, detail)

    def _delay_met(self, d: AlarmDef, now: float, breath: bool) -> bool:
        if d.delay_breaths:
            if not breath:
                return False
            count = self._pending.get(d.id, 0) + 1
            self._pending[d.id] = count
            return count >= d.delay_breaths
        if d.delay_s:
            first = self._pending.setdefault(d.id, now)
            return now - first >= d.delay_s
        return True

    def _raise(self, d: AlarmDef, now: float, detail: str) -> None:
        self._states[d.id] = AlarmState(d, onset=now, detail=detail)
        self._pause_until = None  # a new alarm condition ends Audio Paused
        self._events.append(AlarmEvent("ALARM_ON", d.id, d.priority.name, detail))

    def _resolve(self, alarm_id: str) -> None:
        state = self._states.get(alarm_id)
        if state is None or not state.active:
            return
        self._events.append(AlarmEvent("ALARM_OFF", alarm_id, state.priority.name, state.detail))
        if state.definition.latching:
            state.active = False
        else:
            del self._states[alarm_id]
