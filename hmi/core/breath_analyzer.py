"""Turns the 50 Hz sample stream into one BreathResult per breath. No Qt imports.

A breath starts when the phase changes from E (expiration) to I (inspiration). When the next breath
starts, the previous one is finished and measured:
  PIP   = highest pressure              PEEP  = mean pressure in the last 100 ms of expiration
  Pmean = mean pressure                 Vti / Vte = inspired / expired volume (integral of flow)
  Ti / Te = phase durations             RR and MVe = averages over the last 4 breaths
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from hmi.device.messages import Sample
from hmi.model.settings import ie_text

LPM_TO_MLS = 1000.0 / 60.0
PEEP_WINDOW_MS = 100
AVERAGE_BREATHS = 4
MAX_BREATH_SAMPLES = 3000  # 60 s at 50 Hz: a breath that never returns to I (stuck phase /
# fault) is discarded rather than growing the sample buffer without bound.


@dataclass(frozen=True)
class BreathResult:
    end_t_ms: int
    pip: float
    peep: float
    pmean: float
    vti: float
    vte: float
    ti: float
    te: float
    rr: float
    mve: float  # L/min

    @property
    def ie_text(self) -> str:
        return ie_text(self.ti, self.te)


class BreathAnalyzer:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._samples: list[Sample] = []
        self._started = False
        self._prev_phase: str | None = None
        self._periods: deque[float] = deque(maxlen=AVERAGE_BREATHS)
        self._vtes: deque[float] = deque(maxlen=AVERAGE_BREATHS)

    def add(self, sample: Sample) -> BreathResult | None:
        result = None
        if sample.phase == "I" and self._prev_phase != "I":
            if self._samples:
                result = self._finish(sample.t_ms)
            self._samples = []
            self._started = True
        if self._started:
            self._samples.append(sample)
            if len(self._samples) > MAX_BREATH_SAMPLES:
                self._samples = []
                self._started = False
        self._prev_phase = sample.phase
        return result

    def _finish(self, end_t_ms: int) -> BreathResult | None:
        ss = self._samples
        e_idx = next((i for i, s in enumerate(ss) if s.phase == "E"), None)
        if e_idx is None:
            return None
        e_start = ss[e_idx].t_ms
        ti = (e_start - ss[0].t_ms) / 1000.0
        te = (end_t_ms - e_start) / 1000.0
        pressures = [s.pressure for s in ss]
        tail = [s.pressure for s in ss[e_idx:] if s.t_ms >= end_t_ms - PEEP_WINDOW_MS] or [ss[-1].pressure]

        times = [s.t_ms for s in ss] + [end_t_ms]
        vti = vte = 0.0
        for i, s in enumerate(ss):
            dt = (times[i + 1] - times[i]) / 1000.0
            if s.phase == "I" and s.flow > 0:
                vti += s.flow * LPM_TO_MLS * dt
            elif s.phase == "E" and s.flow < 0:
                vte -= s.flow * LPM_TO_MLS * dt

        self._periods.append(ti + te)
        self._vtes.append(vte)
        rr = 60.0 / (sum(self._periods) / len(self._periods))
        mve = (sum(self._vtes) / len(self._vtes)) * rr / 1000.0
        return BreathResult(
            end_t_ms=end_t_ms, pip=max(pressures), peep=sum(tail) / len(tail),
            pmean=sum(pressures) / len(pressures), vti=vti, vte=vte, ti=ti, te=te, rr=rr, mve=mve,
        )
