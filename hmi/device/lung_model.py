"""Single-compartment lung model used by the simulator. No Qt imports.

The patient is one balloon (compliance C, mL/cmH2O) behind one tube (resistance R, cmH2O/(L/s)):

    P_airway = PEEP + V / C + R x flow

- VC inspiration: constant flow VT / Ti; pressure is calculated (the classic ramp).
- PC inspiration: airway pressure held at PEEP + Pinsp; flow decays exponentially.
- Expiration: passive, V(t) = V0 x e^(-t / (R x C)); airway pressure returns to PEEP.

Faults (see docs/04-simulator.md): disconnection, expiratory occlusion, leak, stiff lungs (C / 4),
and patient effort (breaths triggered by the patient).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from hmi.device.messages import Sample
from hmi.model.patient import Category
from hmi.model.settings import Mode, VentSettings

MLS_TO_LPM = 0.06             # mL/s -> L/min
STIFF_FACTOR = 4.0            # "stiff lungs" divides compliance by this
DISCONNECTED_FLOW_LPM = 60.0  # PC flow escaping through an open circuit
EFFORT_DIP_S = 0.1            # duration of the patient's inspiratory effort before triggering
TRIGGER_REFRACTORY_S = 0.3    # no triggering in the first 0.3 s of expiration
_EPS = 1e-9


@dataclass(frozen=True)
class LungParams:
    compliance: float  # mL/cmH2O
    resistance: float  # cmH2O/(L/s)


DEFAULT_LUNGS = {
    Category.ADULT: LungParams(50.0, 10.0),
    Category.PEDIATRIC: LungParams(20.0, 20.0),
}


@dataclass
class LungFaults:
    disconnected: bool = False
    occluded: bool = False
    leak_fraction: float = 0.0
    stiff: bool = False
    patient_rate: float = 0.0  # patient breathing efforts per minute, 0 = none


class LungSimulator:
    def __init__(self, params: LungParams = DEFAULT_LUNGS[Category.ADULT], noise: float = 1.0,
                 seed: int | None = None):
        self.params = params
        self.faults = LungFaults()
        self.settings = VentSettings()
        self.pmax = 40.0
        self.noise = noise
        self._rng = random.Random(seed)
        self.running = False
        self.t = 0.0
        self.phase = "E"
        self._breath_start = 0.0
        self._lung_v = 0.0       # mL above the PEEP volume (physics)
        self._measured_v = 0.0   # mL, integrated from measured flow, reset each breath
        self._insp_cut = False   # VC inspiration ended early because pressure passed pmax
        self._last_effort = 0.0
        self._effort_started: float | None = None

    # ----- control -------------------------------------------------------------------------------
    def apply(self, settings: VentSettings, pmax: float | None = None) -> None:
        self.settings = settings
        if pmax is not None:
            self.pmax = pmax

    def start(self) -> None:
        self.running = True
        self._lung_v = 0.0
        self._begin_inspiration()

    def stop(self) -> None:
        self.running = False
        self.phase = "E"
        self._lung_v = 0.0
        self._measured_v = 0.0
        self._effort_started = None

    # ----- lung properties -----------------------------------------------------------------------
    @property
    def compliance(self) -> float:
        c = self.params.compliance
        return c / STIFF_FACTOR if self.faults.stiff else c

    @property
    def resistance(self) -> float:
        return self.params.resistance

    @property
    def tau(self) -> float:
        """Time constant R x C in seconds."""
        return self.resistance * self.compliance / 1000.0

    # ----- simulation ----------------------------------------------------------------------------
    def step(self, dt: float) -> Sample:
        self.t += dt
        if self.running:
            self._advance_phase()
        flow_mls, pressure = self._physics(dt)
        if flow_mls < 0:  # with a leak, less gas comes back through the flow sensor
            flow_mls *= 1.0 - self.faults.leak_fraction
        if self._effort_started is not None:
            flow_mls -= (self.settings.trigger + 1.0) / MLS_TO_LPM
        self._measured_v += flow_mls * dt
        return Sample(
            t_ms=int(round(self.t * 1000)),
            pressure=round(pressure + self._noise(0.15), 2),
            flow=round(flow_mls * MLS_TO_LPM + self._noise(0.3), 2),
            volume=round(self._measured_v, 1),
            phase=self.phase,
        )

    def _noise(self, amplitude: float) -> float:
        return self._rng.uniform(-amplitude, amplitude) * self.noise if self.noise else 0.0

    def _begin_inspiration(self) -> None:
        self.phase = "I"
        self._breath_start = self.t
        self._measured_v = 0.0
        self._insp_cut = False
        self._effort_started = None

    def _advance_phase(self) -> None:
        s = self.settings
        elapsed = self.t - self._breath_start
        if self.phase == "I":
            if elapsed >= s.ti - _EPS:
                self.phase = "E"
            return
        if elapsed >= s.cycle_s - _EPS:
            self._begin_inspiration()
            return
        rate = self.faults.patient_rate
        if rate <= 0:
            return
        if self._effort_started is None:
            if (self.t - self._last_effort >= 60.0 / rate - _EPS
                    and elapsed - s.ti >= TRIGGER_REFRACTORY_S - _EPS):
                self._effort_started = self.t
                self._last_effort = self.t
        elif self.t - self._effort_started >= EFFORT_DIP_S - _EPS:
            self._begin_inspiration()

    def _physics(self, dt: float) -> tuple[float, float]:
        """Return (true flow in mL/s, airway pressure in cmH2O) for this step."""
        if not self.running:
            return 0.0, 0.0
        s, f = self.settings, self.faults
        c, r = self.compliance, self.resistance
        peep = s.peep * max(0.0, 1.0 - 1.5 * f.leak_fraction)  # a big leak cannot hold PEEP

        if f.disconnected:
            self._lung_v = 0.0
            if self.phase == "I":
                flow = s.vt / s.ti if s.mode is Mode.VC else DISCONNECTED_FLOW_LPM / MLS_TO_LPM
                return flow, 0.5
            return 0.0, 0.3

        if self.phase == "I":
            if s.mode is Mode.VC:
                flow = 0.0 if self._insp_cut else s.vt / s.ti
                self._lung_v += flow * dt
                pressure = peep + self._lung_v / c + r * flow / 1000.0
                if pressure > self.pmax:
                    self._insp_cut = True  # MCU safety: stop inspiration above Ppeak high
                return flow, pressure
            target = s.pinsp * c
            new_v = target + (self._lung_v - target) * math.exp(-dt / self.tau)
            flow = (new_v - self._lung_v) / dt
            self._lung_v = new_v
            return flow, peep + s.pinsp

        if f.occluded:
            return 0.0, peep + self._lung_v / c
        new_v = self._lung_v * math.exp(-dt / self.tau)
        flow = (new_v - self._lung_v) / dt
        self._lung_v = new_v
        return flow, peep
