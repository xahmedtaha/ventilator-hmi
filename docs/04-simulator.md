# 04 — Simulator

There is no real patient connected to this demo, so `hmi/device/simulator.py` and
`hmi/device/lung_model.py` play the role of the patient and the MCU. This document explains the
physics in plain language and lists what each Demo Panel fault does to it.

## The balloon and the tube

The lungs are modeled the way every basic ventilator textbook models them: **one balloon behind
one tube.**

```
                       tube                    balloon
  ventilator  ═══════════════════════▶   (  (  (  ( )  )  )  )
   (flow in)   resistance R (cmH2O/(L/s))   compliance C (mL/cmH2O)

  - The tube resists flow: pushing gas through it costs pressure, more so the
    narrower/stiffer the tube (higher R) and the faster the flow.
  - The balloon resists being filled: holding a volume V of gas in it costs
    pressure, more so the stiffer the balloon (lower C).
```

This is the standard **single-compartment lung model**. It is a simplification (real lungs have
many regions filling at different rates), but it is the model every entry-level ventilator
course teaches, and it is good enough to make the waveforms, the alarms and the fault behavior
all look realistic.

## The equation

```
P_airway = PEEP + V / C + R × flow
```

| Term | Meaning | Why it's there |
|---|---|---|
| `PEEP` | Positive End-Expiratory Pressure, the baseline pressure the ventilator holds at the end of every breath | Keeps the smallest airways from collapsing shut between breaths |
| `V / C` | Extra pressure needed to hold volume `V` in a balloon of compliance `C` | Stiffer lungs (lower `C`) need more pressure for the same volume — this is why "stiff lungs" raises PIP in Volume Control |
| `R × flow` | Extra pressure needed to push `flow` through a tube of resistance `R` | Only present while gas is actually moving; it disappears the instant flow stops |

## VC vs PC vs expiration

| | **VC inspiration** | **PC inspiration** | **Expiration (both modes)** |
|---|---|---|---|
| What the machine holds constant | Flow = VT / Ti (a straight ramp) | Airway pressure = PEEP + Pinsp | Nothing — it is passive |
| What the equation then produces | Pressure rises through the breath (the classic VC "ramp") as `V/C` grows | Flow starts high and decays exponentially as the balloon fills toward its target volume | Volume decays exponentially; flow is negative (gas leaving) |
| What varies with the lungs | **Pressure** — stiffer lungs → higher PIP for the same volume | **Volume** — stiffer lungs → less volume for the same pressure | Same, either mode: a stiffer/higher-resistance lung empties differently (see time constant below) |

## Time constant: how fast the lungs empty

Expiration is passive — nothing is pushing, so the balloon just empties on its own, the way air
leaks out of a balloon you let go of. The math for that is:

```
V(t) = V0 · e^(−t / τ)          where τ = R × C
```

`τ` ("time constant") is how long the lungs take to empty to about a third of the starting volume.
After `5τ`, **99 %** of the volume is gone (because e^−5 ≈ 0.0067) — that is the rule of thumb used
throughout respiratory physiology.

**Worked example (adult defaults):** R = 10 cmH2O/(L/s), C = 50 mL/cmH2O.

```
τ = R × C / 1000 = 10 × 50 / 1000 = 0.5 s
5τ = 2.5 s  →  99 % exhaled after 2.5 s
```

(The `/ 1000` converts compliance's mL to the liters that resistance is defined in, so the result
comes out in seconds.) This is also why the set inspiratory time Ti and expiratory time Te matter:
if Te is shorter than roughly `3τ`–`5τ`, the patient cannot fully exhale before the next breath
starts — "breath stacking" — which is exactly the kind of problem the `SUSTAINED_PRESSURE` alarm is
there to catch.

## Default lung parameters

| | Adult default | Pediatric default |
|---|---|---|
| Compliance C | 50 mL/cmH2O | 20 mL/cmH2O |
| Resistance R | 10 cmH2O/(L/s) | 20 cmH2O/(L/s) |

Pediatric lungs are modeled as stiffer (lower C) and narrower (higher R) than adult lungs, which is
why the pediatric parameter ranges on the Settings screen use smaller volumes and, generally,
faster rates.

Other simulator details: small random noise is added to every signal so the waveforms look real
rather than perfectly smooth; measured FiO2 moves toward the set value with a 10 s time constant
(it cannot jump instantly, like a real gas blender); the whole model steps at 50 Hz on a Qt timer,
cheap enough to run comfortably on a Raspberry Pi 4.

## Fault injection (Demo Panel)

Opened by **holding the VENT logo for 2 s** or pressing **F12**. Each fault changes the physics
above so a specific set of alarms can be demonstrated.

| Fault | Effect in the simulation | What it changes in the equations | Alarms you should see |
|---|---|---|---|
| Disconnection | Pressure stays near 0 all breath, Vte ≈ 0 | The circuit is open to atmosphere: airway pressure is fixed near 0 (0.5 cmH2O in, 0.3 cmH2O out) and the lung volume is forced to 0 every step, bypassing `PEEP + V/C + R·flow` entirely | LOW PRESSURE, LOW VTE, LOW MVE |
| Occlusion (expiratory) | Air cannot leave: pressure stays high | Expiration's `V(t) = V0·e^(−t/τ)` decay is replaced by "flow stays at 0" — the volume (and so `PEEP + V/C`) never comes back down | VC: HIGH PRESSURE, SUSTAINED PRESSURE, LOW VTE · PC: LOW VTE, LOW MVE |
| Large leak (50 %) | Vte = 50 % of delivered volume, PEEP cannot be held | Measured expiratory flow is scaled by `(1 − 0.5)`; the PEEP the physics targets is reduced to `set PEEP × (1 − 1.5 × 0.5)` because a big leak cannot hold pressure between breaths | LOW VTE, LOW PEEP |
| Stiff lungs (C ÷ 4) | VC: PIP rises · PC: Vte falls | Compliance `C` is divided by 4 everywhere it appears — the same volume now needs 4× the `V/C` pressure, and `τ = R·C` shrinks too, so a PC breath reaches less volume in the same Ti | VC: HIGH PRESSURE · PC: LOW VTE |
| Patient effort (fast breathing) | Triggered breaths at 40 bpm | A brief negative flow dip is added near the patient rate; once it crosses the flow trigger, a new inspiration starts early instead of waiting for the timed breath | HIGH RR, HIGH MVE |
| O2 supply loss | O2 supply = FAIL, FiO2 drifts to 21 % | The status message's *target* FiO2 is forced to 21 % (room air) instead of the set value; the *measured* value drifts toward it with the normal 10 s time constant | O2 SUPPLY, then LOW FIO2 |
| Battery mode | Power = BAT, battery starts at 25 % and drains 0.5 percentage points every second | Not part of the lung equations — the simulator's `battery_pct` counts down every tick regardless of ventilation | ON BATTERY → BATTERY LOW (below 20 %) → BATTERY DEPLETED (below 5 %) |
| MCU link loss | Simulator stops sending heartbeats/data | Not part of the lung equations — the device stops emitting samples and status at all, so the breath analyzer also sees no new breaths | MCU COMMUNICATION LOST, and — once no breath has been seen for the apnea time — APNEA too |

> **Note on the design spec.** The original design table (§8.2) listed only "MCU COMMUNICATION
> LOST" for MCU link loss. `tests/test_fault_scenarios.py` (which drives the real alarm engine
> against the real simulator) shows APNEA also appears after the apnea delay, since no breaths
> arrive either — this document follows the tested behavior.

A **Reset all faults** button in the Demo Panel restores normal operation (and also clears the O2
supply, battery, and link-loss states, and any forced pre-use test failure).

The Demo Panel can also **force any one pre-use test to fail** (`SELF`/`LEAK`/`COMP`/`CAL`/`ALARM`)
so the Pre-use Check screen's failure/Retry path can be demonstrated without waiting for a real
fault — see [docs/07-demo-guide.md](07-demo-guide.md).
