# 03 — Architecture

## Big picture

The UI never knows whether the data it displays comes from the simulator or from the real MCU.
Both implement one interface, `DeviceLink`. Switching to hardware is one line in `main.py` (or the
`--serial COM3` / `--serial /dev/ttyACM0` command-line option) — nothing in the UI, the alarm
engine or the breath analyzer changes.

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

## Every module

| File | What it does | Depends on |
|---|---|---|
| `main.py` | Entry point: parses `--fullscreen`/`--serial`/`--log-dir`/`--no-sound`, builds the `QApplication`, picks `SimulatedDevice` or `SerialDevice`, opens `MainWindow` | `hmi.ui.main_window`, `hmi.device.*`, `hmi.core.alarms.event_log` |
| `hmi/qt.py` | The one place that imports Qt, via `pyqtgraph.Qt` (works with PySide6, PyQt6 or PyQt5) | pyqtgraph |
| `hmi/model/patient.py` | `PatientProfile`, IBW formulas, category defaults | nothing in `hmi` |
| `hmi/model/settings.py` | `VentSettings`, `ParamSpec` (range/step/default), the VC/PC cross-checks | `hmi.model.patient` |
| `hmi/model/alarm_limits.py` | `AlarmLimits`, defaults from patient category + IBW + settings | `hmi.model.patient` |
| `hmi/core/flow.py` | The screen-flow state machine (Patient → Pre-use check → Settings → Ventilating) | nothing in `hmi` |
| `hmi/core/breath_analyzer.py` | Turns a stream of samples into one `BreathResult` per breath (PIP, PEEP, Vte, RR, MVe, I:E) | `hmi.device.messages` |
| `hmi/core/alarms/definitions.py` | The **one table** of every alarm condition (ID, priority, delay, latching) | nothing in `hmi` |
| `hmi/core/alarms/engine.py` | Evaluates conditions against limits, applies delays/latching/grace/audio pause, emits events | `hmi.core.alarms.definitions`, `hmi.core.breath_analyzer`, `hmi.model.*` |
| `hmi/core/alarms/event_log.py` | Append-only JSON Lines log file | nothing in `hmi` |
| `hmi/device/base.py` | `DeviceLink`: the `QObject` + signals interface every device implements | `hmi.model.*` |
| `hmi/device/lung_model.py` | Pure-Python single-compartment lung physics used by the simulator | `hmi.device.messages`, `hmi.model.*` |
| `hmi/device/simulator.py` | `SimulatedDevice`: a 50 Hz Qt timer driving the lung model, pre-use tests, faults, and the simulated buzzer | `hmi.device.lung_model`, `hmi.device.buzzer_sound`, `hmi.device.base` |
| `hmi/device/buzzer_sound.py` | Renders and plays IEC-style buzzer pulse patterns on the computer speaker (demo only) | `hmi.core.alarms.definitions` |
| `hmi/device/protocol.py` | Encode/decode/checksum for every serial message type (see [docs/05-serial-protocol.md](05-serial-protocol.md)) | `hmi.device.messages`, `hmi.model.settings` |
| `hmi/device/serial_device.py` | `SerialDevice`: the skeleton that will talk to the real MCU over `pyserial`, once firmware exists | `hmi.device.protocol`, `hmi.device.base` |
| `hmi/ui/theme.py` | Colors, fonts, the Qt stylesheet, alarm colors | Qt |
| `hmi/ui/main_window.py` | Builds the four screens, wires device signals → analyzer → alarm engine → UI, handles navigation | almost everything above |
| `hmi/ui/screens/*.py` | The four screens: `patient.py`, `precheck.py`, `settings.py`, `monitoring.py` | `hmi.ui.widgets`, `hmi.model.*` |
| `hmi/ui/widgets/*.py` | Reusable pieces: adjuster, param tile, numeric readout, waveform panel, alarm banner, step indicator, toggle group | Qt, `hmi.model.*` |
| `hmi/ui/dialogs/*.py` | Confirm, value-adjust, on-screen keyboard, modes, alarms, demo panel | Qt, `hmi.core.*`, `hmi.model.*` |

## The "no Qt in logic layers" rule

**`hmi/model/`, `hmi/core/`, `hmi/device/lung_model.py` and `hmi/device/protocol.py` never import
Qt.** Everything that decides *what* the ventilator should do — IBW, cross-checks, alarm rules,
breath analysis, lung physics, the wire protocol — is plain Python: dataclasses, functions, no
`QObject`, no signals.

Why this matters:

- **Testable.** These modules can be unit-tested in a fraction of a second, with no display, no
  event loop, and no timing flakiness — most of this project's 150+ tests run this way. Alarm
  timing (delays, the 30 s grace period, the 120 s audio pause) is tested by passing an explicit
  `now` into every call, rather than waiting on a real clock.
- **Reusable outside this codebase.** The MCU firmware team can read `hmi/device/protocol.py`
  and `hmi/core/alarms/definitions.py` directly as the reference for what to implement — they do
  not need to install Qt, or understand anything about the UI, to know what a `$D,...` line means
  or what `HIGH_PRESSURE` requires.
- **Swap-friendly.** Because the alarm engine and breath analyzer never touch a `DeviceLink`
  directly (they consume plain `Sample`/`MonitorStatus`/`BreathResult` objects), replacing the
  simulator with the real MCU cannot silently change how an alarm is evaluated.

Only `hmi/ui/` and the device *drivers* (`DeviceLink`, `SimulatedDevice`, `SerialDevice`, and
`buzzer_sound.py`, which needs Qt timers) import Qt.

## Data flow and timing

| Data | Rate | Producer → Consumer |
|---|---|---|
| Sample: time, pressure, flow, volume, phase (I/E) | 50 Hz | Device → waveform buffer, breath analyzer |
| Status: FiO2, battery %, power source, O2 supply | 1 Hz | Device → top bar, alarm engine |
| BreathResult: PIP, PEEP, Pmean, Vti, Vte, Ti, Te, triggered | per breath | Breath analyzer → readouts, alarm engine |
| Waveform redraw | 25 fps | QTimer → pyqtgraph |
| Alarm evaluation | on each breath + every 200 ms timer | Alarm engine → banner, readouts, buzzer command |
| Heartbeat | 5 Hz each way | Pi ↔ MCU |

## How to switch from the simulator to the real MCU

```bash
python main.py --serial /dev/ttyACM0
```

That one option makes `main.py` build a `SerialDevice` instead of a `SimulatedDevice`; everything
downstream (breath analyzer, alarm engine, all four screens) is unchanged, because both classes
implement the same `DeviceLink` signals and methods.

For this to work with real hardware, the MCU firmware must:

1. Speak the line protocol in [docs/05-serial-protocol.md](05-serial-protocol.md) — `$D`, `$M`,
   `$R`, `$F`, `$K`, `$H` outgoing; `$S`, `$C`, `$X`, `$B`, `$H` incoming.
2. Send a heartbeat (`$H`) at 5 Hz, and treat a missing Pi heartbeat for > 1 s as "Pi is down" —
   see the alarm responsibilities table in [docs/02-alarms.md](02-alarms.md).
3. Enforce the pressure safety cut-off itself (end inspiration above the `PMAX` value the Pi sent)
   — the Pi's alarm engine can only *display* an alarm; it does not touch a valve.
4. Drive its own buzzer from the `$B` messages the Pi sends (priority, paused), using the burst
   patterns in [docs/02-alarms.md](02-alarms.md).

`hmi/device/serial_device.py` already implements the Pi side of this (polling, heartbeat, link-lost
detection, sending settings/commands) and is unit-tested against a fake serial port
(`tests/test_serial_device.py`); it has not been run against real firmware.
