# 02 — Alarms

## What the standards ask for

**IEC 60601-1-8** (general requirements for alarm systems in medical electrical equipment):

- Every alarm has a **priority** — high, medium or low — and the priority must be obvious from
  color, flash rate *and* sound, never from color alone (someone colorblind, or a screen visible
  only in black and white through a low-bandwidth link, must still be able to tell them apart).
- A **high-priority** alarm needs immediate operator action; **medium** needs prompt action;
  **low** is informational.
- Alarm sound must be silenceable, but only for a **limited time** — a silenced alarm must not stay
  silent forever if a new problem appears.
- The operator must always be able to see **which** alarm is active, not just that "something" is
  wrong.
- Nuisance alarms (brief, self-correcting blips) should be filtered out with short delays, without
  hiding a real, persistent problem.

**ISO 80601-2-12** (particular requirements for critical care ventilators), on top of the above:

- The ventilator must alarm on **high airway pressure**, with a mechanism to end inspiration and
  protect the patient's lungs (a "pressure safety cut-off").
- It must alarm on **low pressure / disconnection** and on **apnea** — the two failure modes most
  likely to be immediately life-threatening.
- It must alarm on **abnormal delivered volume/minute volume** and on **abnormal FiO2**, since
  those are what the whole therapy is trying to control.
- It must alarm on **loss of power / running on battery**, since ventilation must not silently stop.
- A **pre-use check** must be possible (and its omission should be visible), since a fault found
  before the patient is connected is infinitely cheaper than one found after.

> **Scope note.** This project follows the *design* requirements of both standards. Proving real
> compliance (measured sound levels, timing accuracy, full risk management file) requires testing
> the finished device and is outside the scope of this software demo.

---

## Priorities

| Priority | Color | Visual signal | Buzzer burst (on the MCU) | Repeats |
|---|---|---|---|---|
| **High** | Red | Flashing 2 Hz, 50 % on (standard range: 1.4–2.8 Hz, 20–60 %) | 10 pulses: `x-x-x--x-x` pause `x-x-x--x-x` | every 5 s (standard range: 2.5–15 s) |
| **Medium** | Yellow | Flashing 0.6 Hz, 50 % on (standard range: 0.4–0.8 Hz) | 3 pulses: `x-x-x` | every 10 s (standard range: 2.5–30 s) |
| **Low** | Cyan | Steady, no flashing | 1 pulse | once, no repeat |

Every alarm message also carries a text marker — `!!!` high, `!!` medium, `!` low — so the
priority never depends on color alone, e.g. `!!! LOW PRESSURE  6 < 8 cmH2O`.

The top-bar banner always shows the **highest-priority, most recent** active alarm, with a
**"+N" badge** for however many others are active. Tapping the banner opens the full *Active
alarms* list, sorted by priority then time.

---

## Operator actions

| Term | Meaning |
|---|---|
| **Active** | The alarm condition is currently true (and its delay, if any, has passed). |
| **Latched** | Only **high-priority** alarms latch: once the condition ends, the alarm stays listed as "resolved" (flashing stops, but the text stays) until **Alarm Reset**. A resolved alarm no longer sounds — the buzzer only follows conditions that are still true. |
| **Audio Paused** | Silences the buzzer for **120 s** (the maximum ISO 80601-2-12 allows). Shown with a crossed-bell icon and a countdown. Visual signals keep flashing. A **new** alarm condition ends the pause immediately — a silenced buzzer must never hide a *new* problem. Pressing the button again during a pause restarts the 120 s. |
| **Alarm Reset** | Clears latched (resolved) alarms from the banner and list. It does **not** clear an alarm whose condition is still true — you cannot "reset away" a real ongoing problem. |
| Medium / low alarms | Non-latching: they disappear by themselves the moment the condition ends. |

Physiological alarms (pressure, volume, rate, FiO2, PEEP, apnea) are evaluated **only while
ventilating** — in Standby, only technical alarms (link, O2 supply, battery, device fault) are
active, because the physiological ones would be meaningless with nobody breathing through the
circuit. When ventilation starts, volume/rate/PEEP/FiO2 alarms are muted for a **30 s start-up
grace period** so the readings can settle; pressure alarms (high pressure, low pressure, sustained
pressure) are active immediately, because those protect against the fastest, most dangerous
failures (a kinked tube, a fully open circuit) and cannot wait.

### Alarm state diagram

```
 inactive ──(condition becomes true)──▶ pending ──(delay elapsed)──▶ active
                                           │                            │
                                (condition ends before delay)  (condition ends)
                                           │                            │
                                           ▼                            ▼
                                       inactive              ┌─ non-latching → inactive
                                                              └─ latching (high only) → resolved
                                                                            │
                                                                    (Alarm Reset)
                                                                            ▼
                                                                        inactive
```

---

## Every alarm

"Delay" is how long the condition must persist, continuously, before the alarm is actually raised
— this is what filters out brief, self-correcting blips without hiding a real problem. IDs and
values below are copied from `hmi/core/alarms/definitions.py`, the one table the code uses.

| ID | Alarm | Priority | Condition | Delay | Latching | Required by ISO 80601-2-12 |
|---|---|---|---|---|---|---|
| `HIGH_PRESSURE` | High airway pressure | High | Pressure > Ppeak high limit (the simulated MCU also ends inspiration) | Immediate | Yes | Yes |
| `LOW_PRESSURE` | Low pressure / disconnection | High | PIP < Ppeak low limit | 2 breaths | Yes | Yes |
| `SUSTAINED_PRESSURE` | Obstruction / sustained high pressure | High | Pressure > set PEEP + 15 cmH2O continuously | 15 s | Yes | Yes |
| `APNEA` | Apnea | High | No breath detected | Apnea time (adult 20 s, pediatric 15 s) | Yes | — |
| `LOW_FIO2` | Low O2 concentration | High | FiO2 < set − 6 percentage points (never below 18 %) | 30 s | Yes | Yes |
| `HIGH_FIO2` | High O2 concentration | Medium | FiO2 > set + 6 percentage points | 30 s | No | Yes |
| `LOW_VTE` | Low expired volume | Medium | Vte < Vte low limit | 3 breaths | No | Yes |
| `HIGH_VTE` | High expired volume | Medium | Vte > Vte high limit | 3 breaths | No | Yes |
| `LOW_MVE` | Low minute volume | Medium | MVe < low limit | 10 s | No | — |
| `HIGH_MVE` | High minute volume | Medium | MVe > high limit | 10 s | No | — |
| `HIGH_RR` | High respiratory rate | Medium | RR > high limit | 10 s | No | — |
| `LOW_PEEP` | Low PEEP | Medium | PEEP < set − 3 cmH2O | 3 breaths | No | — |
| `HIGH_PEEP` | High PEEP | Medium | PEEP > set + 5 cmH2O | 3 breaths | No | Yes (continuing pressure) |
| `O2_SUPPLY` | O2 supply failure | High | MCU status: O2 supply = FAIL | Immediate | Yes | Yes |
| `LINK_LOST` | MCU communication lost | High | No heartbeat from the MCU for > 1 s | Immediate | Yes | Yes (technical) |
| `DEVICE_FAULT` | Device fault (code) | High | MCU reports a fault code | Immediate | Yes | Yes (technical) |
| `ON_BATTERY` | Running on battery | Low | Power source = battery | Immediate | No | Yes |
| `BATTERY_LOW` | Battery low | Medium | Battery < 20 % | Immediate | No | Yes |
| `BATTERY_DEPLETED` | Battery nearly depleted | High | Battery < 5 % | Immediate | Yes | Yes |
| `NO_PRECHECK` | Pre-use check not performed | Low | Check was skipped | Immediate | No | Yes (pre-use check) |

Notes:
- In VC/PC the machine guarantees breaths at the set rate, so Apnea acts as a backup (e.g. breath
  delivery has stopped for some other reason). It becomes essential once spontaneous modes are
  added in a later phase.
- A battery alarm only ever shows the single most severe of `ON_BATTERY` / `BATTERY_LOW` /
  `BATTERY_DEPLETED` at once — they describe the same underlying condition at increasing severity.
- `LOW_PRESSURE` doubles as the disconnection alarm: a fully open circuit reads as very low
  pressure, so a real disconnection and a "pressure too low" fault look the same to the alarm
  engine, which is exactly what should happen.

---

## Default alarm limits

| Limit | Adult default (range) | Pediatric default (range) |
|---|---|---|
| Ppeak high (cmH2O) | 40 (10–60) | 35 (10–50) |
| Ppeak low (cmH2O) | 8 (3–40) | 6 (3–35) |
| Vte high (mL) | 10 mL/kg IBW (clamped to 50–2000) | 10 mL/kg IBW (clamped to 20–1000) |
| Vte low (mL) | 4 mL/kg IBW (clamped to 20–1500) | 4 mL/kg IBW (clamped to 10–800) |
| MVe high (L/min) | 15 (2–40) | 8 (1–25) |
| MVe low (L/min) | 3 (0.5–30) | 1 (0.2–15) |
| RR high (bpm) | 35 (10–70) | 50 (15–90) |
| Apnea time (s) | 20 (10–60) | 15 (10–60) |
| FiO2 / PEEP limits | automatic, follow the set value (see the `LOW_FIO2`/`HIGH_FIO2`/`LOW_PEEP`/`HIGH_PEEP` rows above) | same |

Every limit must satisfy low < high — the Confirm button is disabled otherwise, so it is not
possible to save a limit pair that could never alarm (or that alarms permanently).

---

## The event log

Every alarm start, end, reset and audio pause is recorded, along with setting changes, limit
changes, mode changes, start/standby, and pre-use check results — anything an examiner (or an
incident investigation) would want a timestamped trail of.

- Stored as **JSON Lines** (one JSON object per line) in
  `~/.ventilator-hmi/logs/events-YYYY-MM-DD.jsonl`, so the log survives restarts and can be opened
  in any text editor — no special tool needed to read it.
- The *Log* tab in the Alarms dialog shows the most recent 500 entries, newest first.
- If the file cannot be written (e.g. a read-only filesystem), the HMI keeps running and keeps the
  log in memory only, rather than crashing.

Example line (one alarm turning on):

```json
{"time": "2026-09-22T11:32:05", "kind": "ALARM_ON", "alarm_id": "LOW_PRESSURE", "priority": "HIGH", "detail": "0.7 < 8 cmH2O"}
```

---

## Pi ↔ MCU alarm responsibilities

| Responsibility | Where |
|---|---|
| Physiological alarm detection (pressure, volume, rate, FiO2, PEEP, apnea) | Pi (alarm engine) |
| Technical conditions (O2 supply, power, battery, sensor/valve faults) | MCU reports it → Pi raises the alarm |
| **Buzzer sound** | **MCU**: the Pi sends `(highest active priority, audio paused?)`; the MCU plays the IEC pattern |
| Pressure safety cut-off (end inspiration above Ppeak high) | MCU (the Pi sends the limit) |
| Pi frozen or crashed | MCU sees no Pi heartbeat for > 1 s → sounds the high-priority pattern on its own |
| MCU dead | Pi shows `!!! MCU COMMUNICATION LOST` (visual only) |

**Known gap (for the report):** if the MCU itself dies, its buzzer goes silent with it — the Pi
can show the alarm but cannot make any sound (VNC does not carry audio either). The recommended
fix is a small backup buzzer wired to a Pi GPIO pin, used only for `LINK_LOST`. This is not
implemented; it is not needed for the software demo, but it is a real gap that should be closed
before the design goes further.

**In the demo**, the simulated MCU (`hmi/device/buzzer_sound.py`) plays the pulse patterns on the
computer's own speaker (Windows: `winsound`; Linux/Pi: `aplay`) so the alarm sound can actually be
heard in a presentation. If no audio output is available the app keeps running silently and shows
the buzzer's state as text in the Demo Panel instead. The buzzer only plays when the simulator was
started with sound enabled (the default; `--no-sound` or `sound=False` turns it off).

---

## How to verify

- `tests/test_alarm_engine.py` — priority ordering, all the delays (2/3-breath, 10 s, 15 s, 30 s),
  latching + reset, the 120 s audio pause and how a new alarm ends it early, the 30 s start-up
  grace period, and that Standby suppresses physiological alarms.
- `tests/test_fault_scenarios.py` — runs the simulator with each Demo Panel fault injected and
  checks that exactly the expected set of alarms appears (this is the same table used in
  [docs/07-demo-guide.md](07-demo-guide.md)).
