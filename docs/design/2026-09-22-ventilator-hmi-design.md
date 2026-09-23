# Ventilator HMI — Design Specification

| | |
|---|---|
| **Project** | Ventilator Human–Machine Interface (graduation project) |
| **Phase** | UI demo with simulated data |
| **Date** | 2026-09-22 |
| **Target hardware** | Raspberry Pi 4 Model B (4 GB), screen shown on a Samsung tablet through VNC |
| **Language / UI** | Python 3.11+, Qt (PySide6 preferred, PyQt5 fallback) + pyqtgraph |
| **Standards followed** | IEC 60601-1-8 (alarm systems), ISO 80601-2-12 (critical care ventilators) |

> **Scope note.** The software is *designed per* the standards above. Real compliance
> requires testing the finished device (sound levels, timing, risk management), which is
> outside the scope of this software demo.

---

## 1. Goals

1. Show a realistic ventilator HMI that walks the operator through
   **Patient Profile → Pre-Use Check → Settings → Monitoring**.
2. Display live **pressure, flow and volume waveforms** and **measured values**.
3. Let the operator set **VC** (Volume Control) and **PC** (Pressure Control) ventilation.
4. Implement an **alarm system that follows IEC 60601-1-8 and ISO 80601-2-12**.
5. Run today on **simulated data**, and later on a **real microcontroller (MCU) over serial**
   by swapping one component.
6. Be **clearly documented** so the team and examiners can understand every decision.

### Out of scope (for now)

- Spontaneous modes (PSV, CPAP, SIMV).
- Real sensor/valve control (done by the MCU firmware, a separate project).
- Networking, remote monitoring, user accounts, patient database.
- Formal certification testing.

---

## 2. Hardware & display constraints

| Constraint | Consequence for the design |
|---|---|
| Tablet talks to the Pi through **VNC** | Touches arrive as **single mouse clicks**. No pinch/swipe/multi-touch. All controls are big tap targets (≥ 48 px; primary actions ≥ 56 px — about 9–10 mm on a 10–11" tablet). No text typing required except optional patient name (on-screen keyboard). |
| VNC does **not carry sound** | Alarm sound is produced by a **buzzer on the MCU** (Section 6.6). |
| Pi 4 CPU / VNC bandwidth | Screen is **1280 × 800 landscape**. Waveforms redraw at **25 fps**, antialiasing off. |
| Development happens on a Windows laptop | The app runs the same on Windows (windowed) and on the Pi (fullscreen). |

---

## 3. Screen flow

```
 ┌─────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
 │ 1. PATIENT  │──▶│ 2. PRE-USE   │──▶│ 3. SETTINGS  │──▶│ 4. MONITORING│
 │   PROFILE   │   │    CHECK     │   │  (initial)   │   │ (ventilating)│
 └─────────────┘   └──────────────┘   └──────────────┘   └──────┬───────┘
   │                                                            │
   │ QUICK START ─▶ "Skip pre-use check?" ─▶ Settings           │ STANDBY (confirm)
   │               (defaults for category)                      ▼
   │                                                   back to 3. SETTINGS
```

- A **step indicator** at the top shows ① Patient ② Check ③ Settings ④ Ventilate.
- **Back** is allowed from screens 2 and 3 to the previous screen.
- From Monitoring, **Standby** (with confirmation) stops ventilation and returns to Settings.

### 3.1 Screen 1 — Patient Profile

| Field | Input | Notes |
|---|---|---|
| Category | Toggle: **Adult** / **Pediatric** | Sets ranges, defaults, alarm limits |
| Sex | Toggle: **Male** / **Female** | Needed for IBW (adults) |
| Height | Big **− / +** adjuster (cm) | Adult 140–210 cm, Pediatric 75–150 cm; step 1 cm |
| Name, ID | Optional, on-screen keyboard | Shown in top bar and alarm log |
| Age | Optional, − / + adjuster (years) | Information only |

**Ideal Body Weight (IBW)** is shown live, with the suggested tidal volume range **6–8 mL/kg IBW**:

| Category | Formula | Source |
|---|---|---|
| Adult male | IBW = 50 + 0.91 × (height_cm − 152.4) | ARDSNet |
| Adult female | IBW = 45.5 + 0.91 × (height_cm − 152.4) | ARDSNet |
| Pediatric (any sex) | IBW = 2.396 × e^(0.01863 × height_cm) | Traub & Kichen (valid 74–152 cm) |

IBW is rounded to 0.1 kg.

Buttons: **Next** → Pre-Use Check. **Quick Start** (red, top-right) → confirmation
"Skip pre-use check and start with default settings?" → Settings screen, and a
**"Pre-use check not performed"** low-priority alarm stays active for the session.
Quick Start with no height entered uses default height (Adult male 170 cm, Pediatric 110 cm).

### 3.2 Screen 2 — Pre-Use Check

A checklist of four tests. Each row shows: name, status (⏳ pending / 🔄 running / ✔ pass / ✖ fail),
measured value, and pass criterion.

| # | Test | What happens | Pass criterion |
|---|---|---|---|
| 1 | **System self-test** | MCU link, pressure sensor, flow sensor, O2 sensor, valves, battery | All sub-checks OK, battery ≥ 20 % |
| 2 | **Circuit leak test** | Prompt: *"Block the patient Y-piece, then tap Start"*. Machine pressurizes the circuit and measures leak | Leak < 200 mL/min |
| 3 | **Circuit compliance & resistance** | Measures tubing compliance and resistance (Y-piece still blocked for compliance) | C 0.5–5.0 mL/cmH2O, R < 6 cmH2O/(L/s) |
| 4 | **Sensor calibration + alarm test** | O2 cell and flow sensor zero/calibration, then buzzer sounds the high-priority pattern and the alarm banner flashes; operator taps **"I heard and saw the alarm"** or **"Not heard"** | O2 reads 21 ± 2 % on air, flow zero offset < 0.5 L/min, operator confirms alarm |

Buttons: **Run All**, **Retry** (per failed test), **Continue** (enabled only when all tests
pass), **Skip** (confirmation → same low-priority "Pre-use check not performed" alarm), **Back**.

In the demo each test takes 2–4 s and returns realistic values. The Demo Panel (Section 8)
can force any test to fail.

### 3.3 Screen 3 — Settings (initial)

Two tabs: **Ventilation** and **Alarm Limits**.

**Ventilation tab**
- Mode selector: **VC** | **PC**.
- Grid of large parameter tiles (tap → adjuster dialog with − / + and Confirm/Cancel).
- The **VT tile is pre-filled from IBW** (7 mL/kg, rounded to 10 mL adult / 5 mL pediatric).
- A tile gets an **orange border and a note** when a value is outside typical/lung-protective ranges
  (e.g. VT outside 6–8 mL/kg IBW). This is an *advisory*, not an alarm (orange, because red/yellow/cyan are reserved for alarms).
- Computed read-only info: **I:E ratio**, and in VC the **inspiratory flow** (VT / Ti).

**Parameter ranges and defaults**

| Parameter | Mode | Adult range (default) | Pediatric range (default) | Step |
|---|---|---|---|---|
| VT — tidal volume (mL) | VC | 200–1000 (7 mL/kg IBW) | 50–500 (7 mL/kg IBW) | 10 / 5 |
| Pinsp — pressure above PEEP (cmH2O) | PC | 5–40 (15) | 5–35 (12) | 1 |
| RR — rate (breaths/min) | both | 5–40 (14) | 10–60 (20) | 1 |
| PEEP (cmH2O) | both | 0–20 (5) | 0–15 (5) | 1 |
| FiO2 (%) | both | 21–100 (40) | 21–100 (40) | 1 |
| Ti — inspiratory time (s) | both | 0.5–2.5 (1.0) | 0.3–1.5 (0.7) | 0.1 |
| Trigger — flow trigger (L/min) | both | 1–10 (2) | 0.5–5 (1) | 0.5 |

**Cross-checks** (Confirm is disabled and a message explains why):
- I:E must not be inverse: Ti ≤ 0.5 × (60 / RR).
- VC inspiratory flow VT/Ti ≤ 120 L/min (adult) / 60 L/min (pediatric).
- PC: PEEP + Pinsp ≤ high-pressure alarm limit − 2 cmH2O.

**Alarm Limits tab** — pre-filled from patient category & IBW (Section 6.4), each editable with
the same adjuster. **Restore defaults** button. Every change is written to the event log.

**Start Ventilation** — large green button → confirmation → device starts → Monitoring screen.

### 3.4 Screen 4 — Monitoring

```
┌──────────────────────────────────────────────────────────────────────────┐
│ VC │ Adult · IBW 66 kg · J.Smith │ !!! LOW PRESSURE  +2 │ 🔕1:43 │[🔕][↺]│🔋│12:04│  top bar
├────────────────────────────────────────────────────┬─────────────────────┤
│ Paw  cmH2O  sweep ──/‾‾\────/‾‾\──▌                │  PIP      PEEP      │
│────────────────────────────────────────────────────│  24 ⁴⁰₈   5.0 ⁸₂    │
│ Flow L/min  ──/\__/‾\───/\__/‾\──▌                 │  Pmean    Vte       │
│────────────────────────────────────────────────────│  11       498 ⁷⁵⁰₂₅₀│
│ Vol  mL     ──/‾‾\___/‾‾\___──▌                    │  MVe      RR        │
│                                                    │  7.0      14 ³⁵     │
│                                                    │  FiO2     I:E       │
│                                                    │  40 ⁴⁶₃₄  1:3.3     │
├────────────────────────────────────────────────────┴─────────────────────┤
│ [VT 500][RR 14][PEEP 5][FiO2 40][Ti 1.0][Trig 2]  │ [MODES][ALARMS][STANDBY]│  bottom bar
└──────────────────────────────────────────────────────────────────────────┘
```

- **Waveforms**: three stacked plots, 10 s window, **sweep mode** (left→right with an erase gap,
  like bedside monitors). Fixed, sensible Y-axis ranges per category (auto-scale off to avoid
  jumping).
- **Numeric readouts** (updated every breath): PIP, PEEP, Pmean, Vte, MVe, RR (total), FiO2, I:E.
  Each shows its **alarm limits** in small print. A value in violation takes the alarm color.
- **Bottom bar**: current settings as tiles; tap → adjuster → Confirm → applied to the device
  immediately and logged. In PC the VT tile is replaced by Pinsp.
- **MODES**: switch VC ↔ PC with confirmation. Suggested starting values keep ventilation
  similar: VC→PC uses Pinsp = last PIP − PEEP; PC→VC uses VT = last Vte (clamped to ranges).
- **ALARMS**: dialog with three tabs — *Active alarms*, *Limits* (same as Settings tab), *Log*.
- **Top bar buttons**: **Audio Paused** (🔕, 120 s) and **Alarm Reset** (↺).
- **STANDBY**: confirmation → ventilation stops → Settings screen.

### 3.5 Visual style

- Dark background (easy on the eyes in an ICU, good contrast through VNC).
- **Red, yellow and cyan are reserved for alarms only.** Waveforms and labels use other
  colors (e.g. pressure green, flow magenta, volume periwinkle) so a trace is never mistaken
  for an alarm.
- Large sans-serif numbers; minimum body text 16 px, measured values ≥ 36 px.

---

## 4. Ventilation behavior (what VC and PC mean)

| | **VC — Volume Control** | **PC — Pressure Control** |
|---|---|---|
| Operator sets | VT, RR, PEEP, FiO2, Ti, Trigger | Pinsp, RR, PEEP, FiO2, Ti, Trigger |
| Machine guarantees | The **volume** (constant flow = VT / Ti) | The **pressure** (PEEP + Pinsp during Ti) |
| What varies with the lungs | **Pressure** (stiffer lungs → higher PIP) | **Volume** (stiffer lungs → lower Vte) |
| Breath start | Timer (60/RR) **or** patient effort crossing the flow trigger (assist-control) | same |

---

## 5. Software architecture

### 5.1 Big picture

The UI never knows whether data comes from the simulator or the real MCU. Both implement one
**`DeviceLink`** interface. Switching to hardware = changing one line in `main.py`
(or a `--serial COM3` / `--serial /dev/ttyACM0` command-line option).

```
 ┌────────────────────┐   samples 50 Hz (P, flow, V, phase) ┌──────────────────────┐
 │  DeviceLink        │ ──────────────────────────────────▶ │ Breath analyzer      │
 │  ├ SimulatedDevice │   status 1 Hz (FiO2, battery, O2)   │ PIP, PEEP, Vte, RR,  │
 │  └ SerialDevice    │   test results, faults, link state  │ MVe, I:E per breath  │
 │    (later)         │ ◀────────────────────────────────── └──────────┬───────────┘
 └────────────────────┘   settings, start/standby,                     ▼
          ▲               run test, buzzer command          ┌──────────────────────┐
          │                                                 │ Alarm engine         │
          └──────────── buzzer (priority, paused) ───────── │ limits, delays,      │
                                                            │ latching, audio pause│
 ┌──────────────────────────────────────────────┐           │ → event log file     │
 │ UI (Qt): 4 screens + widgets + dialogs       │ ◀──────── └──────────────────────┘
 │ waveforms redraw at 25 fps (pyqtgraph)       │
 └──────────────────────────────────────────────┘
```

### 5.2 Folder layout and responsibilities

```
ventilator-hmi/
├─ main.py                      # entry point: --windowed (default on Windows), --fullscreen, --serial PORT
├─ requirements.txt
├─ hmi/
│  ├─ qt.py                     # single place that imports Qt (PySide6 or PyQt5 via pyqtgraph.Qt)
│  ├─ model/                    # plain data + rules — NO Qt imports
│  │   patient.py               #   PatientProfile, IBW formulas, category defaults
│  │   settings.py              #   VentSettings, ParamSpec (range/step/default), cross-checks
│  │   alarm_limits.py          #   AlarmLimits, defaults from category + IBW + settings
│  ├─ core/                     # logic — NO Qt imports (easy to test)
│  │   flow.py                  #   screen-flow state machine
│  │   breath_analyzer.py       #   samples → BreathResult (per breath)
│  │   alarms/
│  │     definitions.py         #   ONE table of all alarm conditions
│  │     engine.py              #   evaluation, delays, latching, audio pause, reset
│  │     event_log.py           #   append-only log (JSON Lines file)
│  ├─ device/
│  │   base.py                  #   DeviceLink (QObject with signals) + data classes
│  │   lung_model.py            #   pure-Python lung physics (no Qt)
│  │   simulator.py             #   SimulatedDevice: timer + lung model + faults + simulated buzzer
│  │   buzzer_sound.py          #   plays IEC pulse patterns on the computer speaker (demo only)
│  │   protocol.py              #   serial message encode/decode + checksum (no Qt)
│  │   serial_device.py         #   SerialDevice skeleton for the real MCU (later)
│  └─ ui/
│      theme.py                 #   colors, fonts, Qt stylesheet
│      main_window.py           #   top bar, step indicator, screen stack, wiring
│      screens/                 #   patient.py, precheck.py, settings.py, monitoring.py
│      widgets/                 #   adjuster, param_tile, numeric_readout, waveform_panel,
│                               #   alarm_banner, step_indicator, toggle_group
│      dialogs/                 #   confirm, adjust_value, keyboard, modes, alarms, demo_panel
├─ tests/                       # pytest
└─ docs/                        # user-facing documentation (Section 10)
```

Rule: **`model/`, `core/`, `device/lung_model.py` and `device/protocol.py` never import Qt**, so
they can be unit-tested quickly and reused by anyone (e.g. the MCU team can read the protocol
module).

### 5.3 Qt binding

`hmi/qt.py` imports Qt through `pyqtgraph.Qt`, which works with PySide6, PyQt6 or PyQt5. This keeps
the Pi installation flexible: PySide6 from pip/apt where available, otherwise `python3-pyqt5` from
apt (Section 9).

### 5.4 Data flow and timing

| Data | Rate | Producer → Consumer |
|---|---|---|
| Sample: time, pressure, flow, volume, phase (I/E) | 50 Hz | Device → waveform buffer, breath analyzer |
| Status: FiO2, battery %, power source, O2 supply | 1 Hz | Device → top bar, alarm engine |
| BreathResult: PIP, PEEP, Pmean, Vti, Vte, Ti, Te, triggered | per breath | Breath analyzer → readouts, alarm engine |
| Waveform redraw | 25 fps | QTimer → pyqtgraph |
| Alarm evaluation | on each breath + every 200 ms timer | Alarm engine → banner, readouts, buzzer command |
| Heartbeat | 5 Hz each way | Pi ↔ MCU |

### 5.5 Breath analyzer (how numbers are computed)

- A new breath starts when phase changes **E → I**. The previous breath is then finalized.
- **PIP** = maximum pressure during the breath.
- **PEEP** = average pressure over the last 100 ms of expiration.
- **Pmean** = average pressure over the whole breath.
- **Vti** = volume at the end of inspiration; **Vte** = integral of expiratory flow (absolute).
- **Ti / Te** from phase durations → **I:E** = 1 : (Te / Ti).
- **RR (total)** = 60 / average breath period over the last 4 breaths.
- **MVe** (L/min) = average Vte of the last 4 breaths × RR / 1000.
- **Last breath time** is tracked for the apnea alarm.

---

## 6. Alarm system

### 6.1 Priorities and signals (IEC 60601-1-8)

| Priority | Color | Visual signal | Buzzer burst (on MCU) | Burst repeats |
|---|---|---|---|---|
| **High** | Red | Flashing **2 Hz**, 50 % on (standard: 1.4–2.8 Hz, 20–60 %) | **10 pulses**: `x-x-x--x-x` pause `x-x-x--x-x` | every **5 s** (standard: 2.5–15 s) |
| **Medium** | Yellow | Flashing **0.6 Hz**, 50 % on (standard: 0.4–0.8 Hz) | **3 pulses**: `x-x-x` | every **10 s** (standard: 2.5–30 s) |
| **Low** | Cyan | **Steady** (no flashing) | **1 pulse** | once, no repeat |

- Alarm messages carry a text priority marker so priority does not depend on color alone:
  `!!!` high, `!!` medium, `!` low. Example: `!!! LOW PRESSURE  6 < 8 cmH2O`.
- The banner shows the **highest-priority, most recent** active alarm, plus a **"+N" badge** for the
  others. Tapping the banner opens the Active alarms list (sorted by priority, then time).

### 6.2 Alarm states and operator actions

| Term | Meaning in this HMI |
|---|---|
| **Active** | The alarm condition is currently true (after its delay). |
| **Latched** | A **high-priority** alarm whose condition has ended but is kept visible (banner shows "resolved", flashing stops, text stays) until **Alarm Reset**. A resolved alarm no longer sounds; the buzzer follows only alarms whose condition is still true. |
| **Audio Paused** | Sound stopped for **120 s** (ISO 80601-2-12 maximum). Shown with a crossed-bell icon and countdown. Visual signals continue. A **new** alarm condition ends the pause immediately. Pressing again during a pause restarts the 120 s. |
| **Alarm Reset** | Clears latched (resolved) alarms and removes them from the banner. It does **not** clear alarms whose condition is still true. |
| Medium / low alarms | **Non-latching**: they disappear by themselves when the condition ends. |

Physiological alarms are only evaluated while **ventilating**. In Standby only technical alarms
are active. Volume, rate, PEEP and FiO2 alarms have a **30 s start-up grace period** after
Start Ventilation; pressure alarms are active immediately.

### 6.3 Alarm conditions

"Delay" = how long the condition must persist before the alarm is raised (avoids nuisance alarms).

| ID | Alarm | Priority | Condition | Delay | Latching | Required by ISO 80601-2-12 |
|---|---|---|---|---|---|---|
| `HIGH_PRESSURE` | High airway pressure | High | Pressure > Ppeak high limit (MCU also ends inspiration) | Immediate | Yes | ✔ |
| `LOW_PRESSURE` | Low pressure / disconnection | High | PIP < Ppeak low limit | 2 breaths | Yes | ✔ |
| `SUSTAINED_PRESSURE` | Obstruction / sustained high pressure | High | Pressure > PEEP set + 15 cmH2O continuously | 15 s | Yes | ✔ |
| `APNEA` | Apnea | High | No breath detected | Apnea time (adult 20 s, ped 15 s) | Yes | — |
| `LOW_FIO2` | Low O2 concentration | High | FiO2 < set − 6 percentage points (never below 18 %) | 30 s | Yes | ✔ |
| `HIGH_FIO2` | High O2 concentration | Medium | FiO2 > set + 6 percentage points | 30 s | No | ✔ |
| `LOW_VTE` | Low expired volume | Medium | Vte < Vte low limit | 3 breaths | No | ✔ |
| `HIGH_VTE` | High expired volume | Medium | Vte > Vte high limit | 3 breaths | No | ✔ |
| `LOW_MVE` | Low minute volume | Medium | MVe < low limit | 10 s | No | — |
| `HIGH_MVE` | High minute volume | Medium | MVe > high limit | 10 s | No | — |
| `HIGH_RR` | High respiratory rate | Medium | RR > high limit | 10 s | No | — |
| `LOW_PEEP` | Low PEEP | Medium | PEEP < set − 3 cmH2O | 3 breaths | No | — |
| `HIGH_PEEP` | High PEEP | Medium | PEEP > set + 5 cmH2O | 3 breaths | No | ✔ (continuing pressure) |
| `O2_SUPPLY` | O2 supply failure | High | MCU status: O2 supply = FAIL | Immediate | Yes | ✔ |
| `LINK_LOST` | MCU communication lost | High | No heartbeat from MCU for > 1 s | Immediate | Yes | ✔ (technical) |
| `DEVICE_FAULT` | Device fault (code) | High | MCU reports a fault code | Immediate | Yes | ✔ (technical) |
| `ON_BATTERY` | Running on battery | Low | Power source = battery | Immediate | No | ✔ |
| `BATTERY_LOW` | Battery low | Medium | Battery < 20 % | Immediate | No | ✔ |
| `BATTERY_DEPLETED` | Battery nearly depleted | High | Battery < 5 % | Immediate | Yes | ✔ |
| `NO_PRECHECK` | Pre-use check not performed | Low | Check was skipped | Immediate | No | ✔ (pre-use check) |

Notes:
- In VC/PC the machine guarantees breaths at the set rate, so **Apnea** acts as a backup (e.g.
  breath delivery stopped). It becomes essential when spontaneous modes are added later.
- A battery alarm only shows the most severe of `ON_BATTERY` / `BATTERY_LOW` / `BATTERY_DEPLETED`.

### 6.4 Default alarm limits

| Limit | Adult default (range) | Pediatric default (range) |
|---|---|---|
| Ppeak high (cmH2O) | 40 (10–60) | 35 (10–50) |
| Ppeak low (cmH2O) | 8 (3–40) | 6 (3–35) |
| Vte high (mL) | 10 mL/kg IBW (50–2000) | 10 mL/kg IBW (20–1000) |
| Vte low (mL) | 4 mL/kg IBW (20–1500) | 4 mL/kg IBW (10–800) |
| MVe high (L/min) | 15 (2–40) | 8 (1–25) |
| MVe low (L/min) | 3 (0.5–30) | 1 (0.2–15) |
| RR high (bpm) | 35 (10–70) | 50 (15–90) |
| Apnea time (s) | 20 (10–60) | 15 (10–60) |
| FiO2 / PEEP limits | Automatic, follow the set value (Section 6.3) | same |

Limits must satisfy low < high (Confirm disabled otherwise).

### 6.5 Event log

- Records: alarm **start**, **end**, **reset**, **audio paused**; **setting changes**; **limit changes**;
  **mode changes**; **start/standby**; **pre-use check results/skip**.
- Each entry: timestamp, type, alarm ID/parameter, priority, value and limit / old and new value.
- Stored as **JSON Lines** (one JSON object per line) in `~/.ventilator-hmi/logs/events-YYYY-MM-DD.jsonl`,
  so it survives restarts and can be opened in any text editor.
- The Log tab shows the most recent 500 entries, newest first.

### 6.6 Pi ↔ MCU alarm responsibilities

| Responsibility | Where |
|---|---|
| Physiological alarm detection (pressure, volume, rate, FiO2, PEEP, apnea) | Pi (alarm engine) |
| Technical conditions (O2 supply, power, battery, sensor/valve faults) | MCU reports → Pi raises alarms |
| **Buzzer sound** | **MCU**: Pi sends `(highest active priority, audio paused?)`; MCU plays the IEC pattern |
| Pressure safety cut-off (end inspiration above Ppeak high) | MCU (Pi sends the limit) |
| Pi frozen or crashed | MCU sees no Pi heartbeat for > 1 s → sounds **high-priority** pattern on its own |
| MCU dead | Pi shows `!!! MCU COMMUNICATION LOST` (visual only) |

**Known gap (for the report):** if the MCU dies, its buzzer is silent. Recommended fix: a small backup
buzzer on a Pi GPIO pin used only for `LINK_LOST`. Not needed for the demo.

**Demo:** the simulated MCU plays the pulse patterns on the computer speaker
(Windows: `winsound`; Linux/Pi: `aplay`). If audio is unavailable the app keeps running and shows a
"buzzer" indicator in the Demo Panel instead.

---

## 7. Serial protocol (defined now, implemented on the MCU later)

**Link:** USB/UART, **115200 baud, 8N1**. Text lines, NMEA-style:

```
$<TYPE>,<field1>,<field2>,...*<CS>\n
```

`CS` = XOR of all characters between `$` and `*`, written as two uppercase hex digits.
Lines with a wrong checksum are ignored and counted.

**MCU → Pi**

| Type | Fields | Rate | Example |
|---|---|---|---|
| `D` data sample | t_ms, pressure_cmH2O, flow_Lpm, volume_mL, phase (`I`/`E`) | 50 Hz | `$D,12345,18.2,32.5,410,I*..` |
| `M` monitor status | fio2_pct, battery_pct, power (`AC`/`BAT`), o2_supply (`OK`/`FAIL`) | 1 Hz | `$M,40.5,87,AC,OK*..` |
| `R` test result | test (`SELF`/`LEAK`/`COMP`/`CAL`/`ALARM`), `PASS`/`FAIL`, detail text (no commas) | on completion | `$R,LEAK,PASS,Leak 45 mL/min (limit < 200)*..` |
| `F` fault | code, `1` active / `0` cleared | on change | `$F,FLOW_SENSOR,1*..` |
| `K` acknowledge | command type, `OK`/`ERR`, reason | per command | `$K,S,OK,*..` |
| `H` heartbeat | sequence number | 5 Hz | `$H,42*..` |

**Pi → MCU**

| Type | Fields | Example |
|---|---|---|
| `S` set parameter | name (`MODE`,`VT`,`PINSP`,`RR`,`PEEP`,`FIO2`,`TI`,`TRIG`,`PMAX`), value | `$S,VT,500*..` |
| `C` command | `START` / `STANDBY` | `$C,START*..` |
| `X` run test | `SELF` / `LEAK` / `COMP` / `CAL` / `ALARM` | `$X,LEAK*..` |
| `B` buzzer | priority `0` none / `1` low / `2` medium / `3` high, paused `0`/`1` | `$B,3,0*..` |
| `H` heartbeat | sequence number | `$H,17*..` |

Bandwidth: ~50 × 35 bytes ≈ 1.8 kB/s, well under 115200 baud (~11.5 kB/s).

In this phase `protocol.py` (encode/decode/checksum) is implemented and tested; `serial_device.py`
is a skeleton using `pyserial` that will be completed when the MCU firmware exists.

---

## 8. Simulator

### 8.1 Lung model

The patient is modeled as **one balloon (compliance C) behind one tube (resistance R)** — the
standard single-compartment model:

```
P_airway = PEEP + V / C + R × flow
```

| | Adult default | Pediatric default |
|---|---|---|
| Compliance C | 50 mL/cmH2O | 20 mL/cmH2O |
| Resistance R | 10 cmH2O/(L/s) | 20 cmH2O/(L/s) |

- **VC inspiration:** constant flow = VT / Ti; pressure is calculated from the equation (the classic ramp).
- **PC inspiration:** airway pressure = PEEP + Pinsp; flow = (Pinsp − V/C) / R, decaying exponentially.
- **Expiration (both):** passive; volume decays as V(t) = V₀ · e^(−t / (R·C)); flow is negative.
- **Patient effort** (optional): small negative flow dip at a patient rate; when it crosses the
  trigger setting a new (triggered) breath starts early.
- **Noise:** small random noise on signals so they look real.
- **FiO2:** measured value moves toward the set value with a 10 s time constant.
- Runs at **50 Hz** on a Qt timer in the UI thread (cheap enough on a Pi 4).

### 8.2 Fault injection (Demo Panel)

Opened by **long-press (2 s) on the logo** or **F12**. Toggles:

| Fault | Effect in the simulation | Alarms you should see |
|---|---|---|
| Disconnection | Pressure stays near 0, Vte ≈ 0 | LOW PRESSURE, LOW VTE, LOW MVE |
| Occlusion (expiratory) | Air cannot leave: pressure stays high | VC: HIGH PRESSURE, SUSTAINED PRESSURE, LOW VTE · PC: LOW VTE, LOW MVE |
| Large leak (50 %) | Vte = 50 % of delivered volume, PEEP cannot be held | LOW VTE, LOW PEEP |
| Stiff lungs (C ÷ 4) | VC: PIP rises; PC: Vte falls | HIGH PRESSURE (VC) or LOW VTE (PC) |
| Patient effort (fast breathing) | Triggered breaths at 40 bpm | HIGH RR, HIGH MVE |
| O2 supply loss | O2 supply = FAIL, FiO2 drifts to 21 % | O2 SUPPLY, then LOW FIO2 |
| Battery mode | Power = BAT, battery jumps to 25 % and drains 1 % every 2 s | ON BATTERY → BATTERY LOW → BATTERY DEPLETED |
| MCU link loss | Simulator stops sending heartbeats/data | MCU COMMUNICATION LOST |
| Force pre-use test failure | Chosen test returns FAIL | (Pre-use check screen shows failure) |

A **Reset all faults** button restores normal operation.

---

## 9. Running the app

| Where | Command |
|---|---|
| Windows laptop (development) | `python main.py` (1280×800 window) |
| Raspberry Pi | `python3 main.py --fullscreen` |
| Real MCU later | `python3 main.py --fullscreen --serial /dev/ttyACM0` |

Raspberry Pi setup (documented step-by-step in `docs/06-raspberry-pi-setup.md`):
1. Raspberry Pi OS 64-bit (latest). Install Qt: PySide6 (pip or apt) or fallback `sudo apt install python3-pyqt5`,
   plus `python3-pyqtgraph`, `python3-numpy`, `python3-serial`.
2. Enable VNC (`raspi-config` → Interface Options → VNC) and set the desktop resolution to **1280×800**.
3. Install a VNC viewer on the tablet (e.g. RealVNC Viewer) and connect to the Pi's IP.
4. Optional: auto-start the HMI on boot (desktop autostart entry).

> The Pi setup steps are written from documentation and must be verified on the actual Pi; the
> demo itself is developed and tested on the Windows laptop.

---

## 10. Documentation deliverables

Written in plain language with tables and diagrams, explaining the *why*:

| File | Contents |
|---|---|
| `README.md` | What it is, screenshots, how to run on laptop and Pi |
| `docs/01-screen-flow.md` | The 4 screens and every button |
| `docs/02-alarms.md` | All alarms, priorities, colors, sounds, what the standards require and how we meet it |
| `docs/03-architecture.md` | Module diagram, data flow, how to swap simulator for the MCU |
| `docs/04-simulator.md` | Lung model equations explained simply; fault injection |
| `docs/05-serial-protocol.md` | Message format for the MCU firmware team |
| `docs/06-raspberry-pi-setup.md` | Install, resolution, VNC, autostart |
| `docs/07-demo-guide.md` | Step-by-step presentation script, including which faults to inject |

Code: every module starts with a short docstring saying what it does and what it depends on.

---

## 11. Testing

**Automated (`pytest`)** — for everything that must be correct:

| Area | Examples of tests |
|---|---|
| Patient | IBW for male/female/pediatric at known heights; default VT = 7 mL/kg rounded |
| Settings | Range clamping; I:E cross-check; VC flow limit; PC pressure vs limit check |
| Alarm limits | Defaults from category/IBW; low < high enforced |
| Breath analyzer | Feed a simulated breath with known R, C → PIP, PEEP, Vte, RR within tolerance |
| Alarm engine | Priority ordering; delays (3-breath, 10 s, 30 s); latching + reset; audio pause 120 s; new alarm ends pause; start-up grace; standby suppresses physiological alarms |
| Protocol | Checksum; encode/decode every message type; reject bad checksum/garbage |
| Lung model | VC delivers set VT; PC reaches set pressure; expiration time constant = R·C |
| UI smoke test | App starts offscreen, each screen can be shown, flow Patient→Monitoring works |

**Manual:** the demo guide doubles as the manual test checklist (every fault → expected alarms).

---

## 12. Future work (not in this phase)

- Real `SerialDevice` + MCU firmware.
- Backup Pi GPIO buzzer for `LINK_LOST`.
- Spontaneous modes (PSV/CPAP/SIMV), P-V and flow-volume loops, trends.
- Physical alarm LED/light on the MCU.
- Formal verification against IEC 60601-1-8 (sound level, timing measurements).
