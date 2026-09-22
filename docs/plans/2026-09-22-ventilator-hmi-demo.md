# Ventilator HMI Demo — Implementation Plan

> Execute task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the ventilator HMI demo (Patient → Pre-Use Check → Settings → Monitoring) with
standard-style alarms, running on a simulated device that can later be swapped for a serial MCU.

**Architecture:** Pure-Python logic layers (`hmi/model`, `hmi/core`, `hmi/device/lung_model.py`,
`hmi/device/protocol.py`) with no Qt imports, fully unit-tested. A `DeviceLink` Qt interface with two
implementations (`SimulatedDevice`, `SerialDevice`). A PySide6/pyqtgraph UI (`hmi/ui`) wired together
by `MainWindow`.

**Tech Stack:** Python 3.11+ (dev machine: 3.14), PySide6 6.11 via `pyqtgraph.Qt`, pyqtgraph 0.14,
numpy, pyserial, pytest.

**Spec:** `docs/design/2026-09-22-ventilator-hmi-design.md`

## Global Constraints

- Qt is imported **only** through `hmi/qt.py` (which uses `pyqtgraph.Qt`), so PySide6/PyQt5 both work.
- `hmi/model/`, `hmi/core/`, `hmi/device/messages.py`, `hmi/device/lung_model.py`, `hmi/device/protocol.py` must **not** import Qt.
- Screen size 1280 × 800 landscape; tap targets ≥ 48 px high (primary ones ≥ 56 px).
- Red / yellow / cyan are reserved for alarms (HIGH `#ff3b3b`, MEDIUM `#ffd000`, LOW `#22d3ee`). Advisories use orange `#ff8a3d`.
- No emoji in UI text (Pi fonts may lack them). `✔` `✖` `–` `·` `→` are allowed.
- Every module starts with a docstring saying what it does and what it depends on.
- Commits: short imperative messages, **no AI/tool attribution lines**.
- Run all commands from the repo root with the venv: Windows `.venv\Scripts\python -m pytest`, Git-Bash `.venv/Scripts/python -m pytest`.
- Tests that create Qt objects use the `qapp` fixture (offscreen platform).

## File map

| File | Responsibility |
|---|---|
| `requirements.txt`, `pytest.ini`, `main.py` | Dependencies, test config, entry point |
| `hmi/qt.py` | The single Qt import point |
| `hmi/model/spec.py` | `NumericSpec` — range/step/format for any adjustable number |
| `hmi/model/patient.py` | `PatientProfile`, IBW formulas, height/age specs |
| `hmi/model/settings.py` | `Mode`, `VentSettings`, ranges/defaults, cross-checks, advisories, mode switch |
| `hmi/model/alarm_limits.py` | `AlarmLimits`, default limits, validation, automatic FiO2/PEEP limits |
| `hmi/core/flow.py` | `ScreenFlow` state machine |
| `hmi/core/breath_analyzer.py` | Samples → `BreathResult` |
| `hmi/core/alarms/definitions.py` | `Priority`, `AlarmDef`, the `ALARMS` table |
| `hmi/core/alarms/engine.py` | `AlarmEngine` |
| `hmi/core/alarms/event_log.py` | `EventLog` (JSON Lines) |
| `hmi/device/messages.py` | `Sample`, `MonitorStatus`, `TestResult`, `Fault`, `Ack`, `Heartbeat` |
| `hmi/device/protocol.py` | Serial text protocol encode/decode |
| `hmi/device/lung_model.py` | `LungSimulator` physics + `LungFaults` |
| `hmi/device/base.py` | `DeviceLink` Qt interface |
| `hmi/device/buzzer_sound.py` | IEC-style bursts on the PC speaker (demo) |
| `hmi/device/simulator.py` | `SimulatedDevice` |
| `hmi/device/serial_device.py` | `SerialDevice` |
| `hmi/ui/theme.py` | Colors, stylesheet, `make_button/make_label/make_card` helpers |
| `hmi/ui/widgets/*.py` | `ToggleGroup`, `InlineAdjuster`, `ParamTile`, `StepIndicator`, `NumericReadout`, `WaveformPanel`, `AlarmBanner`, `AlarmLimitsPanel` |
| `hmi/ui/dialogs/*.py` | `ConfirmDialog`, `ValueAdjustDialog`, `KeyboardDialog`, `ModesDialog`, `AlarmsDialog`, `DemoPanel` |
| `hmi/ui/setting_edit.py` | `edit_setting()`, `edit_limit()` (adjuster + validation) |
| `hmi/ui/top_bar.py` | `TopBar` |
| `hmi/ui/screens/*.py` | `PatientScreen`, `PrecheckScreen`, `SettingsScreen`, `MonitoringScreen` |
| `hmi/ui/main_window.py` | `MainWindow` — wiring/controller |
| `docs/*.md`, `README.md` | User documentation |

---

### Task 1: Project scaffold, NumericSpec, patient model

**Files:**
- Create: `requirements.txt`, `pytest.ini`, `hmi/__init__.py`, `hmi/qt.py`, `hmi/model/__init__.py`, `hmi/model/spec.py`, `hmi/model/patient.py`
- Test: `tests/conftest.py`, `tests/test_spec.py`, `tests/test_patient.py`

**Interfaces:**
- Produces: `NumericSpec(key, label, unit, minimum, maximum, step, decimals=0)` with `.clamp(v)->float`, `.fmt(v)->str`, `.range_text()->str`;
  `Category.ADULT/PEDIATRIC`, `Sex.MALE/FEMALE`, `ideal_body_weight(category, sex, height_cm)->float`,
  `height_spec(category)->NumericSpec`, `AGE_SPEC`, `DEFAULT_HEIGHT`, `PatientProfile` (fields `category, sex, height_cm, name, patient_id, age_years`; `.ibw_kg`, `.ibw_formula_text()`, `.suggested_vt_range()->tuple[int,int]`, `.default_vt()->float`, `.summary()->str`, `PatientProfile.quick_start(category)`);
  `hmi.qt` exports `QtCore, QtGui, QtWidgets, Signal, Slot, QT_LIB`; `qapp` pytest fixture.

- [ ] **Step 1: Create scaffold files**

`requirements.txt`:
```
PySide6>=6.5
pyqtgraph>=0.13
numpy>=1.24
pyserial>=3.5
pytest>=7.0
```

`pytest.ini`:
```ini
[pytest]
testpaths = tests
pythonpath = .
```

`hmi/__init__.py`:
```python
"""Ventilator HMI package (graduation project demo)."""

__version__ = "0.1.0"
```

`hmi/qt.py`:
```python
"""The single place where Qt is imported.

pyqtgraph.Qt picks whichever binding is installed (PySide6, PyQt6 or PyQt5), so the same code runs
on the Windows laptop (PySide6 from pip) and on the Raspberry Pi (PySide6 or apt's python3-pyqt5).
Every other module imports Qt names from here.
"""
from pyqtgraph.Qt import QT_LIB, QtCore, QtGui, QtWidgets  # noqa: F401

Signal = QtCore.Signal
Slot = QtCore.Slot
```

`hmi/model/__init__.py`:
```python
"""Plain data and rules (patient, settings, alarm limits). No Qt imports."""
```

`tests/conftest.py`:
```python
"""Shared pytest fixtures. Qt runs 'offscreen' so tests need no display."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from hmi.qt import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app
```

- [ ] **Step 2: Write the failing tests**

`tests/test_spec.py`:
```python
from hmi.model.spec import NumericSpec

VT = NumericSpec("vt", "VT", "mL", 200, 1000, 10)
TI = NumericSpec("ti", "Ti", "s", 0.3, 1.5, 0.1, 1)


def test_clamp_snaps_to_step():
    assert VT.clamp(503) == 500
    assert VT.clamp(506) == 510


def test_clamp_keeps_value_in_range():
    assert VT.clamp(1200) == 1000
    assert VT.clamp(10) == 200
    assert TI.clamp(0.34) == 0.3


def test_format_uses_decimals():
    assert VT.fmt(500) == "500"
    assert TI.fmt(0.7) == "0.7"
    assert VT.range_text() == "200–1000 mL"
```

`tests/test_patient.py`:
```python
import pytest

from hmi.model.patient import (
    Category, PatientProfile, Sex, height_spec, ideal_body_weight,
)


def test_ibw_adult_male_ardsnet():
    assert ideal_body_weight(Category.ADULT, Sex.MALE, 170) == pytest.approx(66.0, abs=0.05)


def test_ibw_adult_female_ardsnet():
    assert ideal_body_weight(Category.ADULT, Sex.FEMALE, 160) == pytest.approx(52.4, abs=0.05)


def test_ibw_pediatric_traub_ignores_sex():
    assert ideal_body_weight(Category.PEDIATRIC, Sex.MALE, 110) == pytest.approx(18.6, abs=0.05)
    assert ideal_body_weight(Category.PEDIATRIC, Sex.FEMALE, 110) == pytest.approx(18.6, abs=0.05)


def test_default_vt_is_7_ml_per_kg_rounded_to_step():
    assert PatientProfile(height_cm=170).default_vt() == 460
    ped = PatientProfile(category=Category.PEDIATRIC, height_cm=110)
    assert ped.default_vt() == 130


def test_suggested_vt_range_is_6_to_8_ml_per_kg():
    assert PatientProfile(height_cm=170).suggested_vt_range() == (396, 528)


def test_quick_start_uses_default_heights():
    assert PatientProfile.quick_start(Category.ADULT).height_cm == 170
    assert PatientProfile.quick_start(Category.PEDIATRIC).height_cm == 110


def test_height_ranges_per_category():
    assert (height_spec(Category.ADULT).minimum, height_spec(Category.ADULT).maximum) == (140, 210)
    assert (height_spec(Category.PEDIATRIC).minimum, height_spec(Category.PEDIATRIC).maximum) == (75, 150)


def test_summary_includes_name_when_given():
    p = PatientProfile(height_cm=170, name="J. SMITH")
    assert p.summary() == "Adult · IBW 66.0 kg · J. SMITH"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_spec.py tests/test_patient.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'hmi.model.spec'`

- [ ] **Step 4: Implement**

`hmi/model/spec.py`:
```python
"""NumericSpec: the range, step and display format of one adjustable number.

Ventilation settings, alarm limits and patient height/age all use it, so every number the operator
can change is validated and displayed the same way. No Qt imports.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NumericSpec:
    key: str
    label: str
    unit: str
    minimum: float
    maximum: float
    step: float
    decimals: int = 0

    def clamp(self, value: float) -> float:
        """Snap `value` to the nearest step (counted from `minimum`) and keep it inside the range."""
        steps = round((value - self.minimum) / self.step)
        snapped = self.minimum + steps * self.step
        snapped = min(max(snapped, self.minimum), self.maximum)
        return round(snapped, 6)

    def fmt(self, value: float) -> str:
        return f"{value:.{self.decimals}f}"

    def range_text(self) -> str:
        return f"{self.fmt(self.minimum)}–{self.fmt(self.maximum)} {self.unit}"
```

`hmi/model/patient.py`:
```python
"""Patient profile and Ideal Body Weight (IBW).

IBW formulas:
- Adults (ARDSNet): male 50 + 0.91 x (height_cm - 152.4); female 45.5 + 0.91 x (height_cm - 152.4)
- Pediatric (Traub & Kichen, valid 74-152 cm): 2.396 x e^(0.01863 x height_cm)
Suggested tidal volume is 6-8 mL/kg IBW (lung-protective ventilation); the default is 7 mL/kg.
No Qt imports.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from hmi.model.spec import NumericSpec


class Category(str, Enum):
    ADULT = "adult"
    PEDIATRIC = "pediatric"

    @property
    def title(self) -> str:
        return "Adult" if self is Category.ADULT else "Pediatric"


class Sex(str, Enum):
    MALE = "male"
    FEMALE = "female"


HEIGHT_RANGE = {Category.ADULT: (140, 210), Category.PEDIATRIC: (75, 150)}
DEFAULT_HEIGHT = {Category.ADULT: 170, Category.PEDIATRIC: 110}
VT_STEP = {Category.ADULT: 10, Category.PEDIATRIC: 5}
AGE_SPEC = NumericSpec("age", "Age", "years", 0, 120, 1)


def height_spec(category: Category) -> NumericSpec:
    low, high = HEIGHT_RANGE[category]
    return NumericSpec("height", "Height", "cm", low, high, 1)


def ideal_body_weight(category: Category, sex: Sex, height_cm: float) -> float:
    """IBW in kg, rounded to 0.1 kg."""
    if category is Category.PEDIATRIC:
        ibw = 2.396 * math.exp(0.01863 * height_cm)
    else:
        base = 50.0 if sex is Sex.MALE else 45.5
        ibw = base + 0.91 * (height_cm - 152.4)
    return round(ibw, 1)


@dataclass(frozen=True)
class PatientProfile:
    category: Category = Category.ADULT
    sex: Sex = Sex.MALE
    height_cm: int = 170
    name: str = ""
    patient_id: str = ""
    age_years: int | None = None

    @classmethod
    def quick_start(cls, category: Category) -> "PatientProfile":
        return cls(category=category, height_cm=DEFAULT_HEIGHT[category])

    @property
    def ibw_kg(self) -> float:
        return ideal_body_weight(self.category, self.sex, self.height_cm)

    def ibw_formula_text(self) -> str:
        h = self.height_cm
        if self.category is Category.PEDIATRIC:
            return f"Traub: 2.396 × e^(0.01863 × {h})"
        base = "50" if self.sex is Sex.MALE else "45.5"
        return f"ARDSNet: {base} + 0.91 × ({h} − 152.4)"

    def suggested_vt_range(self) -> tuple[int, int]:
        return round(6 * self.ibw_kg), round(8 * self.ibw_kg)

    def default_vt(self) -> float:
        step = VT_STEP[self.category]
        return round(7 * self.ibw_kg / step) * step

    def summary(self) -> str:
        text = f"{self.category.title} · IBW {self.ibw_kg:.1f} kg"
        if self.name:
            text += f" · {self.name}"
        return text
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_spec.py tests/test_patient.py -v`
Expected: 11 passed

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pytest.ini hmi tests
git commit -m "Add project scaffold, NumericSpec and patient model with IBW"
```

---

### Task 2: Ventilation settings model

**Files:**
- Create: `hmi/model/settings.py`
- Test: `tests/test_settings.py`

**Interfaces:**
- Consumes: `Category`, `PatientProfile`, `NumericSpec` (Task 1)
- Produces: `Mode.VC/PC` (`.long_name`), `PARAM_KEYS`, `MODE_PARAMS`, `param_spec(category, key)->NumericSpec`,
  `VentSettings` (frozen; fields `mode, vt, pinsp, rr, peep, fio2, ti, trigger`; `defaults_for(patient)`, `get(key)`, `with_value(key, v)`, `with_mode(mode)`, `.cycle_s`, `.te`, `.ie_text`, `.inspiratory_flow_lpm`),
  `ie_text(ti, te)->str`, `validate_settings(settings, category, ppeak_high)->list[str]`, `advisories(settings, patient)->dict[str,str]`,
  `switch_mode(settings, mode, category, last_pip=None, last_vte=None)->VentSettings`

- [ ] **Step 1: Write the failing tests**

`tests/test_settings.py`:
```python
from hmi.model.patient import Category, PatientProfile
from hmi.model.settings import (
    Mode, VentSettings, advisories, ie_text, param_spec, switch_mode, validate_settings,
)

ADULT = PatientProfile(height_cm=170)
PED = PatientProfile(category=Category.PEDIATRIC, height_cm=110)


def test_adult_defaults_use_ibw_for_vt():
    s = VentSettings.defaults_for(ADULT)
    assert (s.mode, s.vt, s.rr, s.peep, s.fio2, s.ti, s.trigger) == (Mode.VC, 460, 14, 5, 40, 1.0, 2.0)
    assert s.pinsp == 15


def test_pediatric_defaults():
    s = VentSettings.defaults_for(PED)
    assert (s.vt, s.rr, s.ti, s.pinsp, s.trigger) == (130, 20, 0.7, 12, 1.0)


def test_ie_ratio_text():
    s = VentSettings(rr=14, ti=1.0)
    assert s.ie_text == "1:3.3"
    assert ie_text(0, 2) == "--"


def test_inverse_ratio_is_rejected():
    s = VentSettings(rr=40, ti=1.0)
    errors = validate_settings(s, Category.ADULT, ppeak_high=40)
    assert len(errors) == 1 and "inverse I:E" in errors[0]


def test_vc_flow_limit_pediatric():
    s = VentSettings(vt=500, ti=0.3, rr=20)
    errors = validate_settings(s, Category.PEDIATRIC, ppeak_high=35)
    assert any("flow" in e for e in errors)


def test_pc_pressure_must_stay_below_alarm_limit():
    s = VentSettings(mode=Mode.PC, pinsp=20, peep=20)
    errors = validate_settings(s, Category.ADULT, ppeak_high=40)
    assert any("Ppeak high" in e for e in errors)


def test_valid_defaults_have_no_errors():
    assert validate_settings(VentSettings.defaults_for(ADULT), Category.ADULT, 40) == []


def test_vt_advisory_outside_6_to_8_ml_per_kg():
    notes = advisories(VentSettings(vt=700), ADULT)
    assert "vt" in notes and "10.6 mL/kg" in notes["vt"]
    assert advisories(VentSettings(vt=460), ADULT) == {}


def test_switch_vc_to_pc_uses_last_pip():
    s = VentSettings(mode=Mode.VC, peep=5, pinsp=15)
    new = switch_mode(s, Mode.PC, Category.ADULT, last_pip=21.6)
    assert new.mode is Mode.PC and new.pinsp == 17


def test_switch_pc_to_vc_uses_last_vte_clamped():
    s = VentSettings(mode=Mode.PC, vt=460)
    new = switch_mode(s, Mode.VC, Category.ADULT, last_vte=1234)
    assert new.mode is Mode.VC and new.vt == 1000


def test_param_spec_lookup():
    assert param_spec(Category.PEDIATRIC, "vt").step == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_settings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'hmi.model.settings'`

- [ ] **Step 3: Implement**

`hmi/model/settings.py`:
```python
"""Ventilation settings (VC and PC modes), their ranges, defaults and safety cross-checks.

VC = Volume Control: the machine delivers a set tidal volume (VT) with constant flow VT/Ti.
PC = Pressure Control: the machine holds PEEP + Pinsp during Ti; the volume depends on the lungs.
No Qt imports.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from hmi.model.patient import Category, PatientProfile
from hmi.model.spec import NumericSpec


class Mode(str, Enum):
    VC = "VC"
    PC = "PC"

    @property
    def long_name(self) -> str:
        return "Volume Control" if self is Mode.VC else "Pressure Control"


PARAM_KEYS = ("vt", "pinsp", "rr", "peep", "fio2", "ti", "trigger")
MODE_PARAMS = {
    Mode.VC: ("vt", "rr", "peep", "fio2", "ti", "trigger"),
    Mode.PC: ("pinsp", "rr", "peep", "fio2", "ti", "trigger"),
}

PARAM_SPECS: dict[Category, dict[str, NumericSpec]] = {
    Category.ADULT: {
        "vt": NumericSpec("vt", "VT", "mL", 200, 1000, 10),
        "pinsp": NumericSpec("pinsp", "Pinsp", "cmH2O", 5, 40, 1),
        "rr": NumericSpec("rr", "RR", "bpm", 5, 40, 1),
        "peep": NumericSpec("peep", "PEEP", "cmH2O", 0, 20, 1),
        "fio2": NumericSpec("fio2", "FiO2", "%", 21, 100, 1),
        "ti": NumericSpec("ti", "Ti", "s", 0.5, 2.5, 0.1, 1),
        "trigger": NumericSpec("trigger", "Trigger", "L/min", 1, 10, 0.5, 1),
    },
    Category.PEDIATRIC: {
        "vt": NumericSpec("vt", "VT", "mL", 50, 500, 5),
        "pinsp": NumericSpec("pinsp", "Pinsp", "cmH2O", 5, 35, 1),
        "rr": NumericSpec("rr", "RR", "bpm", 10, 60, 1),
        "peep": NumericSpec("peep", "PEEP", "cmH2O", 0, 15, 1),
        "fio2": NumericSpec("fio2", "FiO2", "%", 21, 100, 1),
        "ti": NumericSpec("ti", "Ti", "s", 0.3, 1.5, 0.1, 1),
        "trigger": NumericSpec("trigger", "Trigger", "L/min", 0.5, 5, 0.5, 1),
    },
}
PARAM_DEFAULTS = {
    Category.ADULT: {"vt": 500, "pinsp": 15, "rr": 14, "peep": 5, "fio2": 40, "ti": 1.0, "trigger": 2.0},
    Category.PEDIATRIC: {"vt": 150, "pinsp": 12, "rr": 20, "peep": 5, "fio2": 40, "ti": 0.7, "trigger": 1.0},
}
MAX_VC_FLOW_LPM = {Category.ADULT: 120.0, Category.PEDIATRIC: 60.0}
_EPS = 1e-9


def param_spec(category: Category, key: str) -> NumericSpec:
    return PARAM_SPECS[category][key]


def ie_text(ti: float, te: float) -> str:
    """I:E written as 1:x (e.g. '1:3.3')."""
    if ti <= 0:
        return "--"
    return f"1:{te / ti:.1f}"


@dataclass(frozen=True)
class VentSettings:
    mode: Mode = Mode.VC
    vt: float = 500.0
    pinsp: float = 15.0
    rr: float = 14.0
    peep: float = 5.0
    fio2: float = 40.0
    ti: float = 1.0
    trigger: float = 2.0

    @classmethod
    def defaults_for(cls, patient: PatientProfile) -> "VentSettings":
        values = dict(PARAM_DEFAULTS[patient.category])
        values["vt"] = param_spec(patient.category, "vt").clamp(patient.default_vt())
        return cls(**values)

    def get(self, key: str) -> float:
        return getattr(self, key)

    def with_value(self, key: str, value: float) -> "VentSettings":
        return replace(self, **{key: value})

    def with_mode(self, mode: Mode) -> "VentSettings":
        return replace(self, mode=mode)

    @property
    def cycle_s(self) -> float:
        return 60.0 / self.rr

    @property
    def te(self) -> float:
        return self.cycle_s - self.ti

    @property
    def ie_text(self) -> str:
        return ie_text(self.ti, self.te)

    @property
    def inspiratory_flow_lpm(self) -> float:
        return self.vt / 1000.0 / self.ti * 60.0


def validate_settings(settings: VentSettings, category: Category, ppeak_high: float) -> list[str]:
    """Safety cross-checks. An empty list means the settings may be applied."""
    errors: list[str] = []
    max_ti = 0.5 * settings.cycle_s
    if settings.ti > max_ti + _EPS:
        errors.append(
            f"Ti {settings.ti:.1f} s is too long for RR {settings.rr:.0f}: inverse I:E is not allowed "
            f"(max Ti {max_ti:.2f} s)."
        )
    if settings.mode is Mode.VC:
        flow = settings.inspiratory_flow_lpm
        limit = MAX_VC_FLOW_LPM[category]
        if flow > limit + _EPS:
            errors.append(f"Inspiratory flow {flow:.0f} L/min is above the {limit:.0f} L/min limit (VT / Ti).")
    if settings.mode is Mode.PC and settings.peep + settings.pinsp > ppeak_high - 2 + _EPS:
        errors.append(
            f"PEEP + Pinsp = {settings.peep + settings.pinsp:.0f} cmH2O must be at least 2 below "
            f"the Ppeak high alarm limit ({ppeak_high:.0f})."
        )
    return errors


def advisories(settings: VentSettings, patient: PatientProfile) -> dict[str, str]:
    """Non-blocking notes shown with an orange border (not alarms)."""
    notes: dict[str, str] = {}
    if settings.mode is Mode.VC:
        per_kg = settings.vt / patient.ibw_kg
        if not 6.0 <= per_kg <= 8.0:
            notes["vt"] = f"{per_kg:.1f} mL/kg IBW (lung-protective: 6–8)"
    return notes


def switch_mode(
    settings: VentSettings,
    mode: Mode,
    category: Category,
    last_pip: float | None = None,
    last_vte: float | None = None,
) -> VentSettings:
    """Change mode while keeping ventilation similar: VC->PC uses the last PIP, PC->VC the last Vte."""
    new = settings.with_mode(mode)
    if mode is Mode.PC and last_pip is not None:
        new = new.with_value("pinsp", param_spec(category, "pinsp").clamp(last_pip - settings.peep))
    if mode is Mode.VC and last_vte is not None:
        new = new.with_value("vt", param_spec(category, "vt").clamp(last_vte))
    return new
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_settings.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add hmi/model/settings.py tests/test_settings.py
git commit -m "Add ventilation settings model with ranges and safety cross-checks"
```

---

### Task 3: Alarm limits model

**Files:**
- Create: `hmi/model/alarm_limits.py`
- Test: `tests/test_alarm_limits.py`

**Interfaces:**
- Consumes: `Category`, `PatientProfile`, `NumericSpec`
- Produces: `LIMIT_KEYS`, `limit_spec(category, key)->NumericSpec`, `AlarmLimits` (frozen; fields `ppeak_high, ppeak_low, vte_high, vte_low, mve_high, mve_low, rr_high, apnea_time`; `defaults_for(patient)`, `get`, `with_value`),
  `validate_limits(limits)->list[str]`, `fio2_limits(set_fio2)->tuple[float,float]`, `peep_limits(set_peep)->tuple[float,float]`

- [ ] **Step 1: Write the failing tests**

`tests/test_alarm_limits.py`:
```python
from hmi.model.alarm_limits import (
    AlarmLimits, fio2_limits, limit_spec, peep_limits, validate_limits,
)
from hmi.model.patient import Category, PatientProfile


def test_adult_defaults_from_ibw():
    lim = AlarmLimits.defaults_for(PatientProfile(height_cm=170))  # IBW 66.0
    assert (lim.ppeak_high, lim.ppeak_low) == (40, 8)
    assert (lim.vte_high, lim.vte_low) == (660, 260)
    assert (lim.mve_high, lim.mve_low, lim.rr_high, lim.apnea_time) == (15, 3, 35, 20)


def test_pediatric_defaults_from_ibw():
    lim = AlarmLimits.defaults_for(PatientProfile(category=Category.PEDIATRIC, height_cm=110))  # 18.6
    assert (lim.ppeak_high, lim.ppeak_low) == (35, 6)
    assert (lim.vte_high, lim.vte_low) == (185, 75)
    assert (lim.mve_high, lim.mve_low, lim.rr_high, lim.apnea_time) == (8, 1, 50, 15)


def test_low_must_be_below_high():
    lim = AlarmLimits.defaults_for(PatientProfile()).with_value("vte_low", 700)
    errors = validate_limits(lim)
    assert errors == ["Vte low must be lower than Vte high."]


def test_automatic_fio2_limits_follow_setting():
    assert fio2_limits(40) == (34, 46)
    assert fio2_limits(21) == (18, 27)


def test_automatic_peep_limits_follow_setting():
    assert peep_limits(5) == (2, 10)
    assert peep_limits(0) == (0, 5)


def test_limit_spec_lookup():
    assert limit_spec(Category.PEDIATRIC, "mve_low").step == 0.1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_alarm_limits.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`hmi/model/alarm_limits.py`:
```python
"""Alarm limits the operator can adjust, and their defaults per patient.

Vte limits default to 4 and 10 mL/kg IBW. FiO2 and PEEP limits are automatic: they follow the set
value (FiO2 +/- 6 percentage points, never below 18 %; PEEP -3 / +5 cmH2O). No Qt imports.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from hmi.model.patient import Category, PatientProfile
from hmi.model.spec import NumericSpec

LIMIT_KEYS = ("ppeak_high", "ppeak_low", "vte_high", "vte_low", "mve_high", "mve_low", "rr_high", "apnea_time")

LIMIT_SPECS: dict[Category, dict[str, NumericSpec]] = {
    Category.ADULT: {
        "ppeak_high": NumericSpec("ppeak_high", "Ppeak high", "cmH2O", 10, 60, 1),
        "ppeak_low": NumericSpec("ppeak_low", "Ppeak low", "cmH2O", 3, 40, 1),
        "vte_high": NumericSpec("vte_high", "Vte high", "mL", 50, 2000, 10),
        "vte_low": NumericSpec("vte_low", "Vte low", "mL", 20, 1500, 10),
        "mve_high": NumericSpec("mve_high", "MVe high", "L/min", 2, 40, 0.5, 1),
        "mve_low": NumericSpec("mve_low", "MVe low", "L/min", 0.5, 30, 0.5, 1),
        "rr_high": NumericSpec("rr_high", "RR high", "bpm", 10, 70, 1),
        "apnea_time": NumericSpec("apnea_time", "Apnea time", "s", 10, 60, 1),
    },
    Category.PEDIATRIC: {
        "ppeak_high": NumericSpec("ppeak_high", "Ppeak high", "cmH2O", 10, 50, 1),
        "ppeak_low": NumericSpec("ppeak_low", "Ppeak low", "cmH2O", 3, 35, 1),
        "vte_high": NumericSpec("vte_high", "Vte high", "mL", 20, 1000, 5),
        "vte_low": NumericSpec("vte_low", "Vte low", "mL", 10, 800, 5),
        "mve_high": NumericSpec("mve_high", "MVe high", "L/min", 1, 25, 0.5, 1),
        "mve_low": NumericSpec("mve_low", "MVe low", "L/min", 0.2, 15, 0.1, 1),
        "rr_high": NumericSpec("rr_high", "RR high", "bpm", 15, 90, 1),
        "apnea_time": NumericSpec("apnea_time", "Apnea time", "s", 10, 60, 1),
    },
}
_FIXED_DEFAULTS = {
    Category.ADULT: {"ppeak_high": 40, "ppeak_low": 8, "mve_high": 15, "mve_low": 3, "rr_high": 35, "apnea_time": 20},
    Category.PEDIATRIC: {"ppeak_high": 35, "ppeak_low": 6, "mve_high": 8, "mve_low": 1, "rr_high": 50, "apnea_time": 15},
}
LIMIT_PAIRS = (("ppeak_low", "ppeak_high"), ("vte_low", "vte_high"), ("mve_low", "mve_high"))


def limit_spec(category: Category, key: str) -> NumericSpec:
    return LIMIT_SPECS[category][key]


@dataclass(frozen=True)
class AlarmLimits:
    ppeak_high: float
    ppeak_low: float
    vte_high: float
    vte_low: float
    mve_high: float
    mve_low: float
    rr_high: float
    apnea_time: float

    @classmethod
    def defaults_for(cls, patient: PatientProfile) -> "AlarmLimits":
        cat = patient.category
        values = dict(_FIXED_DEFAULTS[cat])
        values["vte_high"] = limit_spec(cat, "vte_high").clamp(10 * patient.ibw_kg)
        values["vte_low"] = limit_spec(cat, "vte_low").clamp(4 * patient.ibw_kg)
        return cls(**values)

    def get(self, key: str) -> float:
        return getattr(self, key)

    def with_value(self, key: str, value: float) -> "AlarmLimits":
        return replace(self, **{key: value})


def validate_limits(limits: AlarmLimits) -> list[str]:
    errors = []
    for low, high in LIMIT_PAIRS:
        if limits.get(low) >= limits.get(high):
            low_label = LIMIT_SPECS[Category.ADULT][low].label
            high_label = LIMIT_SPECS[Category.ADULT][high].label
            errors.append(f"{low_label} must be lower than {high_label}.")
    return errors


def fio2_limits(set_fio2: float) -> tuple[float, float]:
    return max(18.0, set_fio2 - 6.0), set_fio2 + 6.0


def peep_limits(set_peep: float) -> tuple[float, float]:
    return max(0.0, set_peep - 3.0), set_peep + 5.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_alarm_limits.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add hmi/model/alarm_limits.py tests/test_alarm_limits.py
git commit -m "Add alarm limits model with IBW-based defaults"
```

---

### Task 4: Device messages and serial protocol

**Files:**
- Create: `hmi/device/__init__.py`, `hmi/device/messages.py`, `hmi/device/protocol.py`
- Test: `tests/test_protocol.py`

**Interfaces:**
- Consumes: `VentSettings`, `PARAM_KEYS`
- Produces: dataclasses `Sample(t_ms, pressure, flow, volume, phase)`, `MonitorStatus(fio2, battery_pct, on_battery, o2_supply_ok)`, `TestResult(test, passed, detail)`, `Fault(code, active)`, `Ack(command, ok, reason)`, `Heartbeat(seq)`, `TESTS`;
  `ProtocolError`, `checksum(body)`, `encode(type, *fields)`, `decode(line)`, `encode_sample/status/test_result/fault/ack/heartbeat`, `parse_mcu_message(line)`, `encode_setting(name, value)`, `encode_settings(settings, pmax)->list[str]`, `encode_command(cmd)`, `encode_run_test(test)`, `encode_buzzer(priority, paused)`

- [ ] **Step 1: Write the failing tests**

`tests/test_protocol.py`:
```python
import pytest

from hmi.device.messages import Fault, Heartbeat, MonitorStatus, Sample, TestResult
from hmi.device.protocol import (
    ProtocolError, checksum, decode, encode, encode_buzzer, encode_fault, encode_heartbeat,
    encode_sample, encode_settings, encode_status, encode_test_result, parse_mcu_message,
)
from hmi.model.settings import VentSettings


def test_checksum_is_xor_of_body():
    assert checksum("A") == "41"
    assert checksum("AB") == "03"


def test_encode_formats_numbers_compactly():
    assert encode("D", 12345, 18.2, 500.0, "I") == f"$D,12345,18.2,500,I*{checksum('D,12345,18.2,500,I')}\n"


@pytest.mark.parametrize("msg", [
    Sample(12345, 18.2, -32.5, 410.0, "E"),
    MonitorStatus(40.5, 87.0, False, True),
    MonitorStatus(21.0, 15.0, True, False),
    TestResult("LEAK", True, "Leak 45 mL/min (limit < 200)"),
    Fault("FLOW_SENSOR", True),
    Heartbeat(42),
])
def test_roundtrip_mcu_messages(msg):
    encoders = {
        Sample: encode_sample, MonitorStatus: encode_status, TestResult: encode_test_result,
        Fault: encode_fault, Heartbeat: lambda m: encode_heartbeat(m.seq),
    }
    assert parse_mcu_message(encoders[type(msg)](msg)) == msg


def test_bad_checksum_rejected():
    line = encode_heartbeat(1).replace("*", "*F")
    with pytest.raises(ProtocolError):
        decode(line)


@pytest.mark.parametrize("line", ["", "hello", "$H,1", "$Z,1*" + checksum("Z,1"), "$D,1,2*" + checksum("D,1,2")])
def test_garbage_rejected(line):
    with pytest.raises(ProtocolError):
        parse_mcu_message(line)


def test_fields_cannot_contain_separators():
    with pytest.raises(ProtocolError):
        encode("R", "LEAK", "PASS", "a,b")


def test_buzzer_command():
    assert encode_buzzer(3, False) == f"$B,3,0*{checksum('B,3,0')}\n"


def test_settings_are_sent_as_nine_lines_mode_first():
    lines = encode_settings(VentSettings(), pmax=40)
    assert len(lines) == 9
    assert lines[0].startswith("$S,MODE,VC*")
    assert lines[-1].startswith("$S,PMAX,40*")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_protocol.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`hmi/device/__init__.py`:
```python
"""Everything that talks to the ventilator hardware (or simulates it)."""
```

`hmi/device/messages.py`:
```python
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
```

`hmi/device/protocol.py`:
```python
"""Serial text protocol between the Raspberry Pi and the MCU (see docs/05-serial-protocol.md).

Each message is one line:  $<TYPE>,<field>,<field>...*<CS>\\n
CS = XOR of every character between '$' and '*', as two uppercase hex digits (like GPS/NMEA).
No Qt imports, so the MCU team can read this file as the reference.
"""
from __future__ import annotations

from hmi.device.messages import Ack, Fault, Heartbeat, MonitorStatus, Sample, TestResult
from hmi.model.settings import PARAM_KEYS, VentSettings

SETTING_NAMES = {"vt": "VT", "pinsp": "PINSP", "rr": "RR", "peep": "PEEP", "fio2": "FIO2", "ti": "TI", "trigger": "TRIG"}
COMMANDS = ("START", "STANDBY")
_FORBIDDEN = set(",*$\r\n")


class ProtocolError(ValueError):
    """A line that is not a valid protocol message."""


def checksum(body: str) -> str:
    value = 0
    for ch in body:
        value ^= ord(ch)
    return f"{value:02X}"


def _fmt(value) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        text = f"{value:.3f}".rstrip("0").rstrip(".")
        return text if text not in ("", "-0") else "0"
    text = str(value)
    if _FORBIDDEN & set(text):
        raise ProtocolError(f"field contains a reserved character: {text!r}")
    return text


def encode(msg_type: str, *fields) -> str:
    body = ",".join([msg_type, *(_fmt(f) for f in fields)])
    return f"${body}*{checksum(body)}\n"


def decode(line: str) -> tuple[str, list[str]]:
    line = line.strip()
    if not line.startswith("$") or "*" not in line:
        raise ProtocolError(f"not a message: {line!r}")
    body, cs = line[1:].rsplit("*", 1)
    if cs.upper() != checksum(body):
        raise ProtocolError(f"bad checksum: {line!r}")
    parts = body.split(",")
    return parts[0], parts[1:]


# ----- MCU -> Pi ---------------------------------------------------------------------------------

def encode_sample(s: Sample) -> str:
    return encode("D", s.t_ms, float(s.pressure), float(s.flow), float(s.volume), s.phase)


def encode_status(m: MonitorStatus) -> str:
    return encode("M", float(m.fio2), float(m.battery_pct), "BAT" if m.on_battery else "AC",
                  "OK" if m.o2_supply_ok else "FAIL")


def encode_test_result(r: TestResult) -> str:
    return encode("R", r.test, "PASS" if r.passed else "FAIL", r.detail)


def encode_fault(f: Fault) -> str:
    return encode("F", f.code, f.active)


def encode_ack(a: Ack) -> str:
    return encode("K", a.command, "OK" if a.ok else "ERR", a.reason)


def encode_heartbeat(seq: int) -> str:
    return encode("H", seq)


def parse_mcu_message(line: str):
    """Turn one line from the MCU into Sample / MonitorStatus / TestResult / Fault / Ack / Heartbeat."""
    kind, f = decode(line)
    try:
        if kind == "D":
            if f[4] not in ("I", "E"):
                raise ValueError("phase must be I or E")
            return Sample(int(f[0]), float(f[1]), float(f[2]), float(f[3]), f[4])
        if kind == "M":
            return MonitorStatus(float(f[0]), float(f[1]), f[2] == "BAT", f[3] == "OK")
        if kind == "R":
            return TestResult(f[0], f[1] == "PASS", f[2] if len(f) > 2 else "")
        if kind == "F":
            return Fault(f[0], f[1] == "1")
        if kind == "K":
            return Ack(f[0], f[1] == "OK", f[2] if len(f) > 2 else "")
        if kind == "H":
            return Heartbeat(int(f[0]))
    except (IndexError, ValueError) as exc:
        raise ProtocolError(f"bad {kind} message: {line!r}") from exc
    raise ProtocolError(f"unknown message type {kind!r}")


# ----- Pi -> MCU ---------------------------------------------------------------------------------

def encode_setting(name: str, value) -> str:
    return encode("S", name, value)


def encode_settings(settings: VentSettings, pmax: float) -> list[str]:
    lines = [encode_setting("MODE", settings.mode.value)]
    lines += [encode_setting(SETTING_NAMES[k], float(settings.get(k))) for k in PARAM_KEYS]
    lines.append(encode_setting("PMAX", float(pmax)))
    return lines


def encode_command(cmd: str) -> str:
    if cmd not in COMMANDS:
        raise ProtocolError(f"unknown command {cmd!r}")
    return encode("C", cmd)


def encode_run_test(test: str) -> str:
    return encode("X", test)


def encode_buzzer(priority: int, paused: bool) -> str:
    return encode("B", int(priority), bool(paused))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_protocol.py -v`
Expected: all passed (16 tests incl. parametrized)

- [ ] **Step 5: Commit**

```bash
git add hmi/device tests/test_protocol.py
git commit -m "Add device messages and NMEA-style serial protocol"
```

---

### Task 5: Lung model (simulator physics)

**Files:**
- Create: `hmi/device/lung_model.py`
- Test: `tests/test_lung_model.py`

**Interfaces:**
- Consumes: `Sample`, `Category`, `Mode`, `VentSettings`
- Produces: `LungParams(compliance, resistance)`, `DEFAULT_LUNGS[category]`, `LungFaults(disconnected, occluded, leak_fraction, stiff, patient_rate)`,
  `LungSimulator(params=..., noise=1.0, seed=None)` with attributes `params, faults, settings, pmax, running, t, phase` and methods `apply(settings, pmax=None)`, `start()`, `stop()`, `step(dt)->Sample`, properties `compliance, resistance, tau`

- [ ] **Step 1: Write the failing tests**

`tests/test_lung_model.py`:
```python
import math

import pytest

from hmi.device.lung_model import LungSimulator
from hmi.model.settings import Mode, VentSettings

DT = 0.02


def run(sim, seconds):
    return [sim.step(DT) for _ in range(int(round(seconds / DT)))]


def make(settings, **faults):
    sim = LungSimulator(noise=0.0)
    for name, value in faults.items():
        setattr(sim.faults, name, value)
    sim.apply(settings, pmax=40)
    sim.start()
    return sim


def breath_starts(samples):
    return [i for i in range(1, len(samples)) if samples[i].phase == "I" and samples[i - 1].phase == "E"]


def test_vc_delivers_set_volume_with_expected_pip():
    samples = run(make(VentSettings(vt=500, rr=15, ti=1.0, peep=5)), 20)
    window = samples[600:800]  # one full 4 s breath
    assert max(s.volume for s in window) == pytest.approx(500, abs=2)
    assert max(s.pressure for s in window) == pytest.approx(20, abs=0.3)  # PEEP + V/C + R*flow


def test_pc_holds_pressure_and_volume_follows_lungs():
    samples = run(make(VentSettings(mode=Mode.PC, pinsp=15, peep=5, rr=15, ti=1.0)), 20)
    window = samples[600:800]
    assert all(s.pressure == pytest.approx(20) for s in window if s.phase == "I")
    assert max(s.volume for s in window) == pytest.approx(750 * (1 - math.exp(-2)), abs=5)


def test_expiration_follows_time_constant():
    sim = make(VentSettings(vt=500, rr=15, ti=1.0, peep=5))
    samples = run(sim, 20)
    first_e = next(i for i in range(600, 800) if samples[i].phase == "E")
    v0 = samples[first_e - 1].volume
    after_tau = samples[first_e - 1 + int(round(sim.tau / DT))].volume
    assert after_tau == pytest.approx(v0 * math.exp(-1), abs=3)


def test_disconnection_gives_no_pressure_and_no_expired_flow():
    samples = run(make(VentSettings(), disconnected=True), 8)
    assert max(s.pressure for s in samples) < 1
    assert min(s.flow for s in samples) >= 0


def test_expiratory_occlusion_keeps_pressure_high_in_vc():
    samples = run(make(VentSettings(vt=500, rr=15, ti=1.0), occluded=True), 20)
    assert min(s.pressure for s in samples[-250:]) > 20
    assert max(s.pressure for s in samples) > 40


def test_stiff_lungs_hit_the_pressure_limit_in_vc():
    samples = run(make(VentSettings(vt=500, rr=15, ti=1.0), stiff=True), 8)
    assert 40 < max(s.pressure for s in samples) < 42


def test_leak_halves_expired_volume_and_drops_peep():
    samples = run(make(VentSettings(vt=500, rr=15, ti=1.0, peep=5), leak_fraction=0.5), 20)
    last_e = samples[798]
    assert last_e.phase == "E"
    assert last_e.volume == pytest.approx(250, abs=10)
    assert last_e.pressure == pytest.approx(1.25, abs=0.01)


def test_patient_effort_triggers_extra_breaths():
    samples = run(make(VentSettings(rr=14, ti=1.0), patient_rate=40), 30)
    assert 17 <= len(breath_starts(samples)) <= 21


def test_standby_outputs_zero():
    sim = LungSimulator(noise=0.0)
    samples = run(sim, 2)
    assert all(s.pressure == 0 and s.flow == 0 and s.phase == "E" for s in samples)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_lung_model.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`hmi/device/lung_model.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_lung_model.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add hmi/device/lung_model.py tests/test_lung_model.py
git commit -m "Add single-compartment lung model with fault injection"
```

---

### Task 6: Breath analyzer

**Files:**
- Create: `hmi/core/__init__.py`, `hmi/core/breath_analyzer.py`
- Test: `tests/test_breath_analyzer.py`

**Interfaces:**
- Consumes: `Sample`, `ie_text`, `LungSimulator` (tests only)
- Produces: `BreathResult(end_t_ms, pip, peep, pmean, vti, vte, ti, te, rr, mve)` with `.ie_text`; `BreathAnalyzer()` with `add(sample)->BreathResult|None`, `reset()`

- [ ] **Step 1: Write the failing tests**

`tests/test_breath_analyzer.py`:
```python
import pytest

from hmi.core.breath_analyzer import BreathAnalyzer
from hmi.device.lung_model import LungSimulator
from hmi.model.settings import VentSettings


def run(seconds, start=True):
    sim = LungSimulator(noise=0.0)
    sim.apply(VentSettings(vt=500, rr=15, ti=1.0, peep=5))
    if start:
        sim.start()
    analyzer = BreathAnalyzer()
    results = []
    for _ in range(int(round(seconds / 0.02))):
        r = analyzer.add(sim.step(0.02))
        if r:
            results.append(r)
    return results


def test_one_result_per_completed_breath():
    assert len(run(39.0)) == 9  # breaths start at 0, 4, ..., 36 s


def test_measurements_match_the_lung_model():
    r = run(40.0)[-1]
    assert r.pip == pytest.approx(20, abs=0.3)
    assert r.peep == pytest.approx(5, abs=0.1)
    assert r.vti == pytest.approx(500, abs=5)
    assert r.vte == pytest.approx(500, abs=10)
    assert r.ti == pytest.approx(1.0) and r.te == pytest.approx(3.0)
    assert r.rr == pytest.approx(15, abs=0.1)
    assert r.mve == pytest.approx(7.5, abs=0.2)
    assert r.ie_text == "1:3.0"
    assert r.peep < r.pmean < r.pip


def test_standby_samples_give_no_breaths():
    assert run(10.0, start=False) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_breath_analyzer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`hmi/core/__init__.py`:
```python
"""HMI logic: screen flow, breath measurements and the alarm system. No Qt imports."""
```

`hmi/core/breath_analyzer.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_breath_analyzer.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add hmi/core tests/test_breath_analyzer.py
git commit -m "Add breath analyzer computing PIP, PEEP, Vte, RR and MVe"
```

---

### Task 7: Alarm definitions and alarm engine

**Files:**
- Create: `hmi/core/alarms/__init__.py`, `hmi/core/alarms/definitions.py`, `hmi/core/alarms/engine.py`
- Test: `tests/test_alarm_engine.py`

**Interfaces:**
- Consumes: `BreathResult`, `Sample`, `MonitorStatus`, `VentSettings`, `AlarmLimits`, `fio2_limits`, `peep_limits`
- Produces: `Priority(IntEnum: NONE=0, LOW=1, MEDIUM=2, HIGH=3)`, `PRIORITY_MARK`, `AlarmDef`, `ALARMS: dict[str, AlarmDef]`;
  `AlarmState` (`.id, .priority, .definition, .onset, .detail, .active, .message`), `AlarmEvent(kind, alarm_id, priority, detail)`,
  `AlarmEngine(settings, limits)` with `update_context(settings, limits)`, `ventilating`, `set_ventilating(on, now)`, `on_sample(sample, now)`, `on_breath(result, now)`, `on_status(status, now)`, `set_condition(alarm_id, active, now, detail="")`, `tick(now)`, `audio_pause(now)`, `audio_paused(now)->bool`, `audio_pause_remaining(now)->float`, `reset(now)`, `alarms()->list[AlarmState]`, `audible_priority()->Priority`, `readout_priorities()->dict[str, Priority]`, `drain_events()->list[AlarmEvent]`;
  constants `GRACE_S=30`, `AUDIO_PAUSE_S=120`

- [ ] **Step 1: Write the failing tests**

`tests/test_alarm_engine.py`:
```python
import pytest

from hmi.core.alarms.definitions import ALARMS, Priority
from hmi.core.alarms.engine import AlarmEngine
from hmi.core.breath_analyzer import BreathResult
from hmi.device.messages import MonitorStatus, Sample
from hmi.model.alarm_limits import AlarmLimits
from hmi.model.patient import PatientProfile
from hmi.model.settings import VentSettings

PATIENT = PatientProfile(height_cm=170)  # limits: Ppeak 8-40, Vte 260-660, MVe 3-15, RR 35, apnea 20


def make_engine(ventilating_at=0.0):
    e = AlarmEngine(VentSettings.defaults_for(PATIENT), AlarmLimits.defaults_for(PATIENT))
    if ventilating_at is not None:
        e.set_ventilating(True, ventilating_at)
    return e


def breath(**kw):
    values = dict(end_t_ms=0, pip=20.0, peep=5.0, pmean=9.0, vti=460.0, vte=460.0,
                  ti=1.0, te=3.3, rr=14.0, mve=6.4)
    values.update(kw)
    return BreathResult(**values)


def sample(p):
    return Sample(0, p, 0.0, 0.0, "I")


def status(fio2=40.0, battery=100.0, on_battery=False, o2_ok=True):
    return MonitorStatus(fio2, battery, on_battery, o2_ok)


def ids(e):
    return [s.id for s in e.alarms()]


def test_definitions_cover_the_spec_and_only_high_priority_latches():
    assert set(ALARMS) == {
        "HIGH_PRESSURE", "LOW_PRESSURE", "SUSTAINED_PRESSURE", "APNEA", "LOW_FIO2", "HIGH_FIO2",
        "LOW_VTE", "HIGH_VTE", "LOW_MVE", "HIGH_MVE", "HIGH_RR", "LOW_PEEP", "HIGH_PEEP",
        "O2_SUPPLY", "LINK_LOST", "DEVICE_FAULT", "ON_BATTERY", "BATTERY_LOW", "BATTERY_DEPLETED",
        "NO_PRECHECK",
    }
    assert all(d.latching == (d.priority is Priority.HIGH) for d in ALARMS.values())


def test_physiological_alarms_ignored_in_standby():
    e = make_engine(ventilating_at=None)
    e.on_breath(breath(pip=2), 1)
    e.on_breath(breath(pip=2), 2)
    assert ids(e) == []


def test_high_pressure_is_immediate_and_latches_until_reset():
    e = make_engine()
    e.on_sample(sample(45.0), 1.0)
    top = e.alarms()[0]
    assert top.id == "HIGH_PRESSURE" and top.active and top.priority is Priority.HIGH
    assert top.message.startswith("!!! HIGH PRESSURE")
    e.on_breath(breath(pip=20), 5.0)
    top = e.alarms()[0]
    assert not top.active and "(resolved)" in top.message
    assert e.audible_priority() is Priority.NONE
    e.reset(6.0)
    assert ids(e) == []


def test_low_pressure_needs_two_breaths():
    e = make_engine()
    e.on_breath(breath(pip=2), 1)
    assert ids(e) == []
    e.on_breath(breath(pip=2), 5)
    assert ids(e) == ["LOW_PRESSURE"]


def test_low_vte_needs_three_breaths_and_clears_by_itself():
    e = make_engine()
    e.on_breath(breath(vte=100), 31)
    e.on_breath(breath(vte=100), 35)
    assert ids(e) == []
    e.on_breath(breath(vte=100), 39)
    assert ids(e) == ["LOW_VTE"]
    e.on_breath(breath(), 43)
    assert ids(e) == []


def test_grace_period_suppresses_volume_alarms():
    e = make_engine()
    for t in (1, 5, 9, 13):
        e.on_breath(breath(vte=100), t)
    assert ids(e) == []


def test_minute_volume_needs_ten_seconds():
    e = make_engine()
    for t in (31, 35, 40):
        e.on_breath(breath(mve=1.0), t)
    assert ids(e) == []
    e.on_breath(breath(mve=1.0), 41.5)
    assert ids(e) == ["LOW_MVE"]


def test_alarms_sorted_by_priority():
    e = make_engine()
    e.set_condition("NO_PRECHECK", True, 1)
    e.on_sample(sample(45.0), 2)
    assert ids(e) == ["HIGH_PRESSURE", "NO_PRECHECK"]
    assert e.audible_priority() is Priority.HIGH


def test_audio_pause_lasts_120_seconds():
    e = make_engine()
    e.on_sample(sample(45.0), 1)
    e.audio_pause(10)
    assert e.audio_paused(100)
    assert e.audio_pause_remaining(100) == pytest.approx(30)
    e.tick(130.5)
    assert not e.audio_paused(130.5)


def test_new_alarm_ends_audio_pause():
    e = make_engine()
    e.on_sample(sample(45.0), 1)
    e.audio_pause(10)
    e.set_condition("NO_PRECHECK", True, 20)
    assert not e.audio_paused(21)


def test_standby_clears_physiological_but_keeps_technical():
    e = make_engine()
    e.on_sample(sample(45.0), 1)
    e.set_condition("LINK_LOST", True, 1)
    e.set_ventilating(False, 2)
    assert ids(e) == ["LINK_LOST"]


def test_apnea_after_apnea_time():
    e = make_engine(0)
    e.tick(19)
    assert ids(e) == []
    e.tick(21)
    assert ids(e) == ["APNEA"]
    e.on_breath(breath(), 22)
    e.tick(22.2)
    assert not e.alarms()[0].active


def test_battery_shows_only_the_most_severe():
    e = make_engine()
    e.on_status(status(battery=50, on_battery=True), 1)
    assert ids(e) == ["ON_BATTERY"]
    e.on_status(status(battery=15, on_battery=True), 2)
    assert ids(e) == ["BATTERY_LOW"]
    e.on_status(status(battery=3, on_battery=True), 3)
    assert ids(e) == ["BATTERY_DEPLETED"]


def test_low_fio2_needs_30_seconds_after_grace():
    e = make_engine()
    e.on_status(status(fio2=30), 31)
    e.on_status(status(fio2=30), 60)
    assert ids(e) == []
    e.on_status(status(fio2=30), 61.5)
    assert ids(e) == ["LOW_FIO2"]


def test_sustained_pressure_must_be_continuous():
    e = make_engine()
    t = 0.0
    while t <= 14.0:
        e.on_sample(sample(25.0), t)
        t += 0.5
    e.on_sample(sample(18.0), 14.5)
    t = 15.0
    while t <= 29.5:
        e.on_sample(sample(25.0), t)
        t += 0.5
    assert ids(e) == []
    e.on_sample(sample(25.0), 30.0)
    assert ids(e) == ["SUSTAINED_PRESSURE"]


def test_events_are_recorded_once():
    e = make_engine()
    e.on_sample(sample(45.0), 1)
    e.on_breath(breath(), 5)
    e.reset(6)
    assert [ev.kind for ev in e.drain_events()] == ["ALARM_ON", "ALARM_OFF", "ALARM_RESET"]
    assert e.drain_events() == []


def test_readout_priorities_color_the_measured_values():
    e = make_engine()
    e.on_sample(sample(45.0), 1)
    assert e.readout_priorities() == {"pip": Priority.HIGH}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_alarm_engine.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement definitions**

`hmi/core/alarms/__init__.py`:
```python
"""Alarm system designed per IEC 60601-1-8 and ISO 80601-2-12 (see docs/02-alarms.md)."""
```

`hmi/core/alarms/definitions.py`:
```python
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
```

- [ ] **Step 4: Implement the engine**

`hmi/core/alarms/engine.py`:
```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_alarm_engine.py -v`
Expected: 17 passed

- [ ] **Step 6: Commit**

```bash
git add hmi/core/alarms tests/test_alarm_engine.py
git commit -m "Add alarm definitions and IEC 60601-1-8 style alarm engine"
```

---

### Task 8: Event log

**Files:**
- Create: `hmi/core/alarms/event_log.py`
- Test: `tests/test_event_log.py`

**Interfaces:**
- Produces: `DEFAULT_LOG_DIR`, `EventLog(directory=DEFAULT_LOG_DIR, max_recent=500, clock=datetime.now)` with `add(kind, **fields)->dict`, `recent()->list[dict]` (newest first), `.path`; `describe(entry)->str`

- [ ] **Step 1: Write the failing tests**

`tests/test_event_log.py`:
```python
import json
from datetime import datetime

from hmi.core.alarms.event_log import EventLog, describe


def clock():
    return datetime(2026, 9, 22, 12, 0, 5)


def test_entries_are_written_as_json_lines(tmp_path):
    log = EventLog(tmp_path, clock=clock)
    log.add("ALARM_ON", alarm_id="LOW_VTE", priority="MEDIUM", detail="100 < 260 mL")
    log.add("SETTING", key="vt", old=460, new=500)
    lines = (tmp_path / "events-2026-09-22.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["kind"] for line in lines] == ["ALARM_ON", "SETTING"]
    assert json.loads(lines[0])["time"] == "2026-09-22T12:00:05"


def test_recent_is_newest_first_and_bounded():
    log = EventLog(None, max_recent=2, clock=clock)
    for n in range(3):
        log.add("TEST", n=n)
    assert [e["n"] for e in log.recent()] == [2, 1]


def test_unwritable_directory_keeps_log_in_memory(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    log = EventLog(blocker / "sub", clock=clock)  # parent is a file: directory cannot be created
    log.add("TEST")
    assert len(log.recent()) == 1


def test_describe_is_human_readable():
    assert describe({"time": "t", "kind": "SETTING", "key": "vt", "old": 460, "new": 500}) == "vt: 460 → 500"
    assert describe({"time": "t", "kind": "ALARM_ON", "alarm_id": "LOW_VTE", "priority": "MEDIUM",
                     "detail": "100 < 260 mL"}) == "LOW_VTE (medium) 100 < 260 mL"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_event_log.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`hmi/core/alarms/event_log.py`:
```python
"""Event log: alarms, setting changes and operator actions, saved as JSON Lines. No Qt imports.

One JSON object per line in <directory>/events-YYYY-MM-DD.jsonl, so the log survives restarts and
can be opened in any text editor. If the file cannot be written, the HMI keeps running and the log
stays in memory.
"""
from __future__ import annotations

import json
import sys
from collections import deque
from datetime import datetime
from pathlib import Path

DEFAULT_LOG_DIR = Path.home() / ".ventilator-hmi" / "logs"


class EventLog:
    def __init__(self, directory: Path | None = DEFAULT_LOG_DIR, max_recent: int = 500,
                 clock=datetime.now):
        self.directory = Path(directory) if directory is not None else None
        self._recent: deque[dict] = deque(maxlen=max_recent)
        self._clock = clock
        self._write_failed = False

    @property
    def path(self) -> Path | None:
        if self.directory is None:
            return None
        return self.directory / f"events-{self._clock():%Y-%m-%d}.jsonl"

    def add(self, kind: str, **fields) -> dict:
        entry = {"time": self._clock().isoformat(timespec="seconds"), "kind": kind, **fields}
        self._recent.append(entry)
        self._write(entry)
        return entry

    def recent(self) -> list[dict]:
        return list(reversed(self._recent))

    def _write(self, entry: dict) -> None:
        path = self.path
        if path is None or self._write_failed:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            self._write_failed = True
            print(f"[event log] cannot write {path}: {exc}; keeping the log in memory only", file=sys.stderr)


def describe(entry: dict) -> str:
    """One-line human description of a log entry (used by the Log tab)."""
    fields = {k: v for k, v in entry.items() if k not in ("time", "kind")}
    if entry.get("kind") in ("ALARM_ON", "ALARM_OFF"):
        text = f"{fields.get('alarm_id', '')} ({str(fields.get('priority', '')).lower()}) {fields.get('detail', '')}"
        return text.strip()
    if {"key", "old", "new"} <= fields.keys():
        return f"{fields['key']}: {fields['old']} → {fields['new']}"
    return " · ".join(f"{k}={v}" for k, v in fields.items() if v not in ("", None))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_event_log.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add hmi/core/alarms/event_log.py tests/test_event_log.py
git commit -m "Add JSON Lines event log"
```

---

### Task 9: Screen-flow state machine

**Files:**
- Create: `hmi/core/flow.py`
- Test: `tests/test_flow.py`

**Interfaces:**
- Produces: `Step(IntEnum: PATIENT=1, PRECHECK=2, SETTINGS=3, VENTILATING=4)`, `InvalidTransition`, `ScreenFlow` with `.step`, `.precheck_passed`, `.precheck_skipped`, methods `patient_done()`, `quick_start()`, `complete_precheck()`, `skip_precheck()`, `back()`, `start_ventilation()`, `standby()`

- [ ] **Step 1: Write the failing tests**

`tests/test_flow.py`:
```python
import pytest

from hmi.core.flow import InvalidTransition, ScreenFlow, Step


def test_normal_path():
    f = ScreenFlow()
    assert f.step is Step.PATIENT
    f.patient_done()
    assert f.step is Step.PRECHECK
    f.complete_precheck()
    assert f.step is Step.SETTINGS and f.precheck_passed and not f.precheck_skipped
    f.start_ventilation()
    assert f.step is Step.VENTILATING
    f.standby()
    assert f.step is Step.SETTINGS


def test_quick_start_skips_precheck():
    f = ScreenFlow()
    f.quick_start()
    assert f.step is Step.SETTINGS and f.precheck_skipped


def test_skip_precheck():
    f = ScreenFlow()
    f.patient_done()
    f.skip_precheck()
    assert f.step is Step.SETTINGS and f.precheck_skipped and not f.precheck_passed


def test_back_goes_one_step():
    f = ScreenFlow()
    f.patient_done()
    f.back()
    assert f.step is Step.PATIENT


@pytest.mark.parametrize("action", ["back", "start_ventilation", "standby", "complete_precheck"])
def test_invalid_transitions_from_patient(action):
    with pytest.raises(InvalidTransition):
        getattr(ScreenFlow(), action)()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_flow.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`hmi/core/flow.py`:
```python
"""Screen-flow state machine: Patient -> Pre-use check -> Settings -> Ventilating. No Qt imports.

Back is allowed from Pre-use check and Settings. Standby returns from Ventilating to Settings.
Quick Start and Skip jump to Settings and mark the pre-use check as skipped.
"""
from __future__ import annotations

from enum import IntEnum


class Step(IntEnum):
    PATIENT = 1
    PRECHECK = 2
    SETTINGS = 3
    VENTILATING = 4


class InvalidTransition(RuntimeError):
    """Raised when a screen change is not allowed from the current step."""


class ScreenFlow:
    def __init__(self) -> None:
        self.step = Step.PATIENT
        self.precheck_passed = False
        self.precheck_skipped = False

    def _require(self, action: str, *allowed: Step) -> None:
        if self.step not in allowed:
            raise InvalidTransition(f"cannot {action} from {self.step.name}")

    def patient_done(self) -> None:
        self._require("continue", Step.PATIENT)
        self.step = Step.PRECHECK

    def quick_start(self) -> None:
        self._require("quick start", Step.PATIENT)
        self.precheck_skipped = True
        self.step = Step.SETTINGS

    def complete_precheck(self) -> None:
        self._require("complete the pre-use check", Step.PRECHECK)
        self.precheck_passed = True
        self.precheck_skipped = False
        self.step = Step.SETTINGS

    def skip_precheck(self) -> None:
        self._require("skip the pre-use check", Step.PRECHECK)
        self.precheck_skipped = True
        self.step = Step.SETTINGS

    def back(self) -> None:
        self._require("go back", Step.PRECHECK, Step.SETTINGS)
        self.step = Step(self.step - 1)

    def start_ventilation(self) -> None:
        self._require("start ventilation", Step.SETTINGS)
        self.step = Step.VENTILATING

    def standby(self) -> None:
        self._require("go to standby", Step.VENTILATING)
        self.step = Step.SETTINGS
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_flow.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add hmi/core/flow.py tests/test_flow.py
git commit -m "Add screen-flow state machine"
```

---

### Task 10: DeviceLink interface, buzzer sound and SimulatedDevice

**Files:**
- Create: `hmi/device/base.py`, `hmi/device/buzzer_sound.py`, `hmi/device/simulator.py`
- Test: `tests/test_buzzer_sound.py`, `tests/test_simulator.py`, `tests/test_fault_scenarios.py`

**Interfaces:**
- Consumes: `LungSimulator`, `LungFaults`, `DEFAULT_LUNGS`, messages, `Priority`, `AlarmEngine`, `BreathAnalyzer` (scenario tests)
- Produces:
  - `DeviceLink(QObject)` signals `sample_received(object)`, `status_received(object)`, `test_finished(object)`, `fault_changed(str, bool)`, `link_changed(bool)`; methods `open()`, `close()`, `set_patient(category)`, `apply_settings(settings, pmax)`, `start_ventilation()`, `standby()`, `run_test(test)`, `set_buzzer(priority:int, paused:bool)`
  - `BURSTS`, `REPEAT_S`, `render_wav(pattern)->bytes`, `BuzzerSound(parent=None, enabled=True)` with `update(priority, paused)`, `play_test()`, `shutdown()`, `.state_text`, `.available`
  - `SimulatedDevice(parent=None, seed=None, sound=True)` with `.lung`, `.buzzer`, `.sim_time`, `.fio2_measured`, `.battery_pct`, `.on_battery`, `.o2_supply_ok`, `.link_lost`, `.force_fail`, `tick()`, `set_o2_supply(ok)`, `set_battery_mode(on)`, `set_link_lost(lost)`, `reset_faults()`

- [ ] **Step 1: Write the failing tests**

`tests/test_buzzer_sound.py`:
```python
import io
import wave

import pytest

from hmi.core.alarms.definitions import Priority
from hmi.device.buzzer_sound import BURSTS, BuzzerSound, render_wav


def test_burst_pulse_counts_follow_iec_60601_1_8():
    assert len(BURSTS[Priority.HIGH]) == 10
    assert len(BURSTS[Priority.MEDIUM]) == 3
    assert len(BURSTS[Priority.LOW]) == 1


def test_rendered_wav_has_the_pattern_duration():
    pattern = BURSTS[Priority.MEDIUM]
    with wave.open(io.BytesIO(render_wav(pattern))) as w:
        seconds = w.getnframes() / w.getframerate()
        assert w.getnchannels() == 1
    assert seconds == pytest.approx(sum(on + off for on, off in pattern), abs=0.01)


def test_state_text_follows_priority_and_pause(qapp):
    b = BuzzerSound(enabled=False)
    b.update(Priority.HIGH, False)
    assert b.state_text == "HIGH burst every 5 s"
    b.update(Priority.HIGH, True)
    assert b.state_text == "silent (audio paused)"
    b.update(Priority.NONE, False)
    assert b.state_text == "silent"
    b.shutdown()
```

`tests/test_simulator.py`:
```python
from hmi.device.simulator import SimulatedDevice
from hmi.model.settings import VentSettings


def collect(device, signal_name):
    items = []
    getattr(device, signal_name).connect(items.append)
    return items


def test_emits_samples_at_50_hz_and_status_at_1_hz(qapp):
    dev = SimulatedDevice(seed=1, sound=False)
    samples, statuses = collect(dev, "sample_received"), collect(dev, "status_received")
    for _ in range(100):
        dev.tick()
    assert len(samples) == 100 and len(statuses) == 2


def test_fio2_moves_toward_setting_while_ventilating(qapp):
    dev = SimulatedDevice(seed=1, sound=False)
    dev.apply_settings(VentSettings(fio2=60), 40)
    dev.start_ventilation()
    for _ in range(50 * 30):
        dev.tick()
    assert 55 < dev.fio2_measured < 60


def test_pre_use_tests_finish_after_their_duration(qapp):
    dev = SimulatedDevice(seed=1, sound=False)
    results = collect(dev, "test_finished")
    dev.run_test("LEAK")
    for _ in range(50 * 2):
        dev.tick()
    assert results == []
    for _ in range(50 * 2):
        dev.tick()
    assert len(results) == 1 and results[0].test == "LEAK" and results[0].passed
    assert "," not in results[0].detail


def test_forced_failure(qapp):
    dev = SimulatedDevice(seed=1, sound=False)
    results = collect(dev, "test_finished")
    dev.force_fail = "COMP"
    dev.run_test("COMP")
    for _ in range(50 * 4):
        dev.tick()
    assert not results[0].passed


def test_link_loss_stops_data_and_reports_link(qapp):
    dev = SimulatedDevice(seed=1, sound=False)
    samples, links = collect(dev, "sample_received"), collect(dev, "link_changed")
    dev.set_link_lost(True)
    for _ in range(10):
        dev.tick()
    assert samples == [] and links == [False]
    dev.reset_faults()
    assert links == [False, True]
```

`tests/test_fault_scenarios.py` (checks every Demo Panel fault produces the alarms promised in the demo guide):
```python
import pytest

from hmi.core.alarms.engine import AlarmEngine
from hmi.core.breath_analyzer import BreathAnalyzer
from hmi.device.simulator import SimulatedDevice
from hmi.model.alarm_limits import AlarmLimits
from hmi.model.patient import PatientProfile
from hmi.model.settings import Mode, VentSettings


def run_scenario(inject, seconds, mode=Mode.VC):
    patient = PatientProfile()
    settings = VentSettings.defaults_for(patient).with_mode(mode)
    limits = AlarmLimits.defaults_for(patient)
    dev = SimulatedDevice(seed=7, sound=False)
    dev.apply_settings(settings, limits.ppeak_high)
    engine, analyzer = AlarmEngine(settings, limits), BreathAnalyzer()

    def on_sample(s):
        engine.on_sample(s, dev.sim_time)
        result = analyzer.add(s)
        if result:
            engine.on_breath(result, dev.sim_time)

    dev.sample_received.connect(on_sample)
    dev.status_received.connect(lambda m: engine.on_status(m, dev.sim_time))
    dev.link_changed.connect(lambda ok: engine.set_condition("LINK_LOST", not ok, dev.sim_time))
    dev.start_ventilation()
    engine.set_ventilating(True, dev.sim_time)

    def advance(duration):
        for _ in range(int(duration / 0.02)):
            dev.tick()
            engine.tick(dev.sim_time)

    advance(40)
    baseline = {s.id for s in engine.alarms()}
    inject(dev)
    advance(seconds)
    return baseline, {s.id for s in engine.alarms()}


def set_fault(name, value):
    return lambda dev: setattr(dev.lung.faults, name, value)


@pytest.mark.parametrize("inject, seconds, mode, expected", [
    (set_fault("disconnected", True), 40, Mode.VC, {"LOW_PRESSURE", "LOW_VTE", "LOW_MVE"}),
    (set_fault("occluded", True), 30, Mode.VC, {"HIGH_PRESSURE", "SUSTAINED_PRESSURE", "LOW_VTE"}),
    (set_fault("occluded", True), 40, Mode.PC, {"LOW_VTE", "LOW_MVE"}),
    (set_fault("leak_fraction", 0.5), 30, Mode.VC, {"LOW_VTE", "LOW_PEEP"}),
    (set_fault("stiff", True), 20, Mode.VC, {"HIGH_PRESSURE"}),
    (set_fault("stiff", True), 30, Mode.PC, {"LOW_VTE"}),
    (set_fault("patient_rate", 40), 40, Mode.VC, {"HIGH_RR", "HIGH_MVE"}),
    (lambda dev: dev.set_o2_supply(False), 45, Mode.VC, {"O2_SUPPLY", "LOW_FIO2"}),
    (lambda dev: dev.set_battery_mode(True), 50, Mode.VC, {"BATTERY_DEPLETED"}),
    (lambda dev: dev.set_link_lost(True), 25, Mode.VC, {"LINK_LOST", "APNEA"}),
])
def test_demo_fault_raises_expected_alarms(qapp, inject, seconds, mode, expected):
    baseline, raised = run_scenario(inject, seconds, mode)
    assert baseline == set()
    assert expected <= raised
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_buzzer_sound.py tests/test_simulator.py tests/test_fault_scenarios.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the DeviceLink interface**

`hmi/device/base.py`:
```python
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
```

- [ ] **Step 4: Implement the buzzer sound**

`hmi/device/buzzer_sound.py`:
```python
"""Plays IEC 60601-1-8 style alarm bursts on the computer speaker. Demo only.

On the real ventilator the MCU drives a buzzer; this class imitates it so the demo can be heard.
Timings approximate IEC 60601-1-8:
  HIGH   10 pulses  x-x-x--x-x  pause  x-x-x--x-x   repeated every 5 s
  MEDIUM  3 pulses  x-x-x                           repeated every 10 s
  LOW     1 pulse                                   once
Tone: 523 Hz fundamental plus harmonics (the standard asks for at least 4 harmonics).
Windows plays through `winsound`; Linux/Raspberry Pi through `aplay`. Without either, it is silent.
"""
from __future__ import annotations

import io
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from functools import lru_cache
from pathlib import Path

from hmi.core.alarms.definitions import Priority
from hmi.qt import QtCore

TONE_HZ = 523.0
SAMPLE_RATE = 22050
FADE_SAMPLES = 220  # 10 ms fade in/out avoids clicks


def _high_group(gap_after: float) -> list[tuple[float, float]]:
    return [(0.15, 0.10), (0.15, 0.10), (0.15, 0.35), (0.15, 0.10), (0.15, gap_after)]


BURSTS: dict[Priority, list[tuple[float, float]]] = {
    Priority.HIGH: _high_group(0.8) + _high_group(0.0),
    Priority.MEDIUM: [(0.2, 0.2), (0.2, 0.2), (0.2, 0.0)],
    Priority.LOW: [(0.25, 0.0)],
}
REPEAT_S: dict[Priority, float | None] = {Priority.HIGH: 5.0, Priority.MEDIUM: 10.0, Priority.LOW: None}


def render_wav(pattern: list[tuple[float, float]]) -> bytes:
    """Render (pulse_seconds, silence_after_seconds) pairs to a 16-bit mono WAV file in memory."""
    frames = bytearray()
    for on, off in pattern:
        n_on = int(on * SAMPLE_RATE)
        for i in range(n_on):
            t = i / SAMPLE_RATE
            envelope = min(1.0, i / FADE_SAMPLES, (n_on - i) / FADE_SAMPLES)
            value = sum(math.sin(2 * math.pi * TONE_HZ * k * t) / k for k in range(1, 6))
            frames += struct.pack("<h", int(value * envelope * 9000))
        frames += b"\x00\x00" * int(off * SAMPLE_RATE)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(frames))
    return buffer.getvalue()


@lru_cache(maxsize=None)
def _rendered(priority: Priority) -> bytes:
    return render_wav(BURSTS[priority])


class _Player:
    """Plays one WAV file asynchronously; stop() cuts it off."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._winsound = None
        if sys.platform.startswith("win"):
            import winsound

            self._winsound = winsound
            self.available = True
        else:
            self.available = shutil.which("aplay") is not None

    def play(self, path: Path) -> None:
        if not self.available:
            return
        self.stop()
        try:
            if self._winsound:
                self._winsound.PlaySound(str(path), self._winsound.SND_FILENAME | self._winsound.SND_ASYNC)
            else:
                self._proc = subprocess.Popen(["aplay", "-q", str(path)],
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, RuntimeError):
            self.available = False

    def stop(self) -> None:
        if self._winsound:
            self._winsound.PlaySound(None, 0)
        elif self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
        self._proc = None


class BuzzerSound(QtCore.QObject):
    def __init__(self, parent: QtCore.QObject | None = None, enabled: bool = True):
        super().__init__(parent)
        self._dir = Path(tempfile.mkdtemp(prefix="vent-hmi-buzzer-"))
        self._files: dict[Priority, Path] = {}
        for priority in BURSTS:
            path = self._dir / f"{priority.name.lower()}.wav"
            path.write_bytes(_rendered(priority))
            self._files[priority] = path
        self._player = _Player() if enabled else None
        self._priority = Priority.NONE
        self._paused = False
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._play_current)
        self.state_text = "silent"

    @property
    def available(self) -> bool:
        return self._player is not None and self._player.available

    def update(self, priority: int, paused: bool) -> None:
        priority = Priority(priority)
        if (priority, paused) == (self._priority, self._paused):
            return
        rising = priority > self._priority
        self._priority, self._paused = priority, paused
        self._timer.stop()
        if paused or priority is Priority.NONE:
            self._stop()
            self.state_text = "silent (audio paused)" if paused and priority else "silent"
            return
        repeat = REPEAT_S[priority]
        if repeat:
            self._play_current()
            self._timer.start(int(repeat * 1000))
            self.state_text = f"{priority.name} burst every {repeat:.0f} s"
        else:
            if rising:
                self._play_current()
            self.state_text = f"{priority.name} burst (once)"

    def play_test(self) -> None:
        """Alarm test during the pre-use check: one high-priority burst."""
        if self._player:
            self._player.play(self._files[Priority.HIGH])

    def shutdown(self) -> None:
        self._timer.stop()
        self._stop()
        shutil.rmtree(self._dir, ignore_errors=True)

    def _play_current(self) -> None:
        if self._player and self._priority in self._files:
            self._player.play(self._files[self._priority])

    def _stop(self) -> None:
        if self._player:
            self._player.stop()
```

- [ ] **Step 5: Implement the simulator**

`hmi/device/simulator.py`:
```python
"""SimulatedDevice: a fake ventilator MCU for the demo (implements DeviceLink).

Every 20 ms (50 Hz) it advances the lung model and emits a Sample; every second it emits a
MonitorStatus (FiO2, battery, O2 supply). It answers pre-use tests after a realistic delay and
plays the alarm buzzer on the computer speaker. The Demo Panel changes its faults at runtime
(see docs/04-simulator.md for the list and the alarms each fault causes).
"""
from __future__ import annotations

import random

from hmi.device.base import DeviceLink
from hmi.device.buzzer_sound import BuzzerSound
from hmi.device.lung_model import DEFAULT_LUNGS, LungFaults, LungSimulator
from hmi.device.messages import MonitorStatus, TestResult
from hmi.model.patient import Category
from hmi.model.settings import VentSettings
from hmi.qt import QtCore

TICK_S = 0.02
STATUS_EVERY_TICKS = 50
FIO2_TAU_S = 10.0
BATTERY_DEMO_START_PCT = 25.0
BATTERY_DRAIN_PER_S = 0.5
TEST_DURATION_S = {"SELF": 2.0, "LEAK": 3.0, "COMP": 3.0, "CAL": 2.5, "ALARM": 3.0}


class SimulatedDevice(DeviceLink):
    def __init__(self, parent: QtCore.QObject | None = None, seed: int | None = None, sound: bool = True):
        super().__init__(parent)
        self._rng = random.Random(seed)
        self.lung = LungSimulator(noise=1.0, seed=seed)
        self.buzzer = BuzzerSound(self, enabled=sound)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(int(TICK_S * 1000))
        self._timer.timeout.connect(self.tick)
        self._ticks = 0
        self.fio2_measured = 21.0
        self.battery_pct = 100.0
        self.on_battery = False
        self.o2_supply_ok = True
        self.link_lost = False
        self.force_fail: str | None = None
        self._pending_tests: list[tuple[float, str]] = []

    @property
    def sim_time(self) -> float:
        return self.lung.t

    # ----- DeviceLink ----------------------------------------------------------------------------
    def open(self) -> None:
        self._timer.start()
        self.link_changed.emit(True)

    def close(self) -> None:
        self._timer.stop()
        self.buzzer.shutdown()

    def set_patient(self, category: Category) -> None:
        self.lung.params = DEFAULT_LUNGS[category]

    def apply_settings(self, settings: VentSettings, pmax: float) -> None:
        self.lung.apply(settings, pmax)

    def start_ventilation(self) -> None:
        self.lung.start()

    def standby(self) -> None:
        self.lung.stop()

    def run_test(self, test: str) -> None:
        self._pending_tests.append((self.sim_time + TEST_DURATION_S[test], test))
        if test == "ALARM" and not self.link_lost and self.force_fail != "ALARM":
            self.buzzer.play_test()

    def set_buzzer(self, priority: int, paused: bool) -> None:
        if not self.link_lost:
            self.buzzer.update(priority, paused)

    # ----- Demo Panel controls -------------------------------------------------------------------
    def set_o2_supply(self, ok: bool) -> None:
        self.o2_supply_ok = ok

    def set_battery_mode(self, on: bool) -> None:
        self.on_battery = on
        self.battery_pct = min(self.battery_pct, BATTERY_DEMO_START_PCT) if on else 100.0

    def set_link_lost(self, lost: bool) -> None:
        if lost == self.link_lost:
            return
        self.link_lost = lost
        if lost:
            self.buzzer.update(0, False)  # a dead MCU cannot sound its buzzer
        self.link_changed.emit(not lost)

    def reset_faults(self) -> None:
        self.lung.faults = LungFaults()
        self.set_o2_supply(True)
        self.set_battery_mode(False)
        self.set_link_lost(False)
        self.force_fail = None

    # ----- simulation ----------------------------------------------------------------------------
    def tick(self) -> None:
        sample = self.lung.step(TICK_S)
        self._ticks += 1
        target = self.lung.settings.fio2 if (self.lung.running and self.o2_supply_ok) else 21.0
        self.fio2_measured += (target - self.fio2_measured) * TICK_S / FIO2_TAU_S
        if self.on_battery:
            self.battery_pct = max(0.0, self.battery_pct - BATTERY_DRAIN_PER_S * TICK_S)
        due = [t for t in self._pending_tests if t[0] <= self.sim_time]
        self._pending_tests = [t for t in self._pending_tests if t[0] > self.sim_time]
        if self.link_lost:
            return
        for _, test in due:
            self.test_finished.emit(self._result_for(test))
        self.sample_received.emit(sample)
        if self._ticks % STATUS_EVERY_TICKS == 0:
            self.status_received.emit(MonitorStatus(
                fio2=round(self.fio2_measured + self._rng.uniform(-0.3, 0.3), 1),
                battery_pct=round(self.battery_pct),
                on_battery=self.on_battery,
                o2_supply_ok=self.o2_supply_ok,
            ))

    def _result_for(self, test: str) -> TestResult:
        """Realistic pre-use test answers. Details never contain commas (serial protocol rule)."""
        fail = self.force_fail == test
        r = self._rng
        if test == "SELF":
            if not fail and self.battery_pct < 20:
                return TestResult(test, False, f"Battery {self.battery_pct:.0f} % (needs at least 20 %)")
            if fail:
                return TestResult(test, False, "Flow sensor not responding")
            return TestResult(test, True, f"MCU link · sensors · valves OK · battery {self.battery_pct:.0f} %")
        if test == "LEAK":
            leak = r.randint(300, 450) if fail else r.randint(30, 80)
            return TestResult(test, not fail, f"Leak {leak} mL/min (limit < 200)")
        if test == "COMP":
            if fail:
                return TestResult(test, False, f"C {r.uniform(7.5, 8.5):.1f} mL/cmH2O (limit 0.5–5.0)")
            return TestResult(test, True, f"C {r.uniform(1.8, 2.6):.1f} mL/cmH2O · R {r.uniform(2.8, 4.2):.1f} cmH2O/(L/s)")
        if test == "CAL":
            if fail:
                return TestResult(test, False, "O2 cell reads 14.8 % on air (expected 21 ± 2)")
            return TestResult(test, True, f"O2 {r.uniform(20.6, 21.6):.1f} % on air · flow zero {r.uniform(0.0, 0.2):.1f} L/min")
        if test == "ALARM":
            return TestResult(test, not fail, "Buzzer driver fault" if fail else "Buzzer burst played")
        return TestResult(test, False, f"Unknown test {test}")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_buzzer_sound.py tests/test_simulator.py tests/test_fault_scenarios.py -v`
Expected: all passed (3 + 5 + 10). If a fault scenario fails, print `raised` and adjust the **scenario duration** (not the thresholds) — thresholds come from the spec.

- [ ] **Step 7: Commit**

```bash
git add hmi/device tests/test_buzzer_sound.py tests/test_simulator.py tests/test_fault_scenarios.py
git commit -m "Add DeviceLink interface, simulated device and demo buzzer"
```

---

### Task 11: SerialDevice (real MCU link)

**Files:**
- Create: `hmi/device/serial_device.py`
- Test: `tests/test_serial_device.py`

**Interfaces:**
- Consumes: `DeviceLink`, protocol functions, messages
- Produces: `SerialDevice(port, baudrate=115200, parent=None, serial_factory=None, clock=time.monotonic)` with `open()`, `close()`, `poll()`, `heartbeat()`, `.bad_lines`, plus all `DeviceLink` methods

- [ ] **Step 1: Write the failing tests**

`tests/test_serial_device.py`:
```python
from hmi.device.messages import Fault, Heartbeat, Sample
from hmi.device.protocol import encode_fault, encode_heartbeat, encode_sample
from hmi.device.serial_device import SerialDevice
from hmi.model.settings import VentSettings


class FakeSerial:
    def __init__(self):
        self.incoming = b""
        self.written = []

    @property
    def in_waiting(self):
        return len(self.incoming)

    def read(self, n):
        data, self.incoming = self.incoming[:n], self.incoming[n:]
        return data

    def write(self, data):
        self.written.append(data.decode("ascii"))

    def close(self):
        pass


def make(qapp, clock_value):
    fake = FakeSerial()
    dev = SerialDevice("TEST", serial_factory=lambda: fake, clock=lambda: clock_value[0])
    dev.open()
    return dev, fake


def test_parses_samples_and_faults(qapp):
    now = [0.0]
    dev, fake = make(qapp, now)
    samples, faults = [], []
    dev.sample_received.connect(samples.append)
    dev.fault_changed.connect(lambda code, active: faults.append((code, active)))
    fake.incoming = (encode_sample(Sample(20, 5.0, 30.0, 10.0, "I")) + encode_fault(Fault("FLOW_SENSOR", True))).encode()
    dev.poll()
    assert samples == [Sample(20, 5.0, 30.0, 10.0, "I")]
    assert faults == [("FLOW_SENSOR", True)]
    dev.close()


def test_bad_lines_are_counted_not_raised(qapp):
    now = [0.0]
    dev, fake = make(qapp, now)
    fake.incoming = b"garbage\n$H,1*00\n"
    dev.poll()
    assert dev.bad_lines == 2
    dev.close()


def test_link_goes_up_on_heartbeat_and_down_after_timeout(qapp):
    now = [0.0]
    dev, fake = make(qapp, now)
    links = []
    dev.link_changed.connect(links.append)
    fake.incoming = encode_heartbeat(1).encode()
    dev.poll()
    assert links == [True]
    now[0] = 1.5
    dev.heartbeat()
    assert links == [True, False]
    assert fake.written[-1].startswith("$H,")
    dev.close()


def test_settings_are_written_as_protocol_lines(qapp):
    now = [0.0]
    dev, fake = make(qapp, now)
    dev.apply_settings(VentSettings(), 40)
    assert len(fake.written) == 9 and fake.written[0].startswith("$S,MODE,VC*")
    dev.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_serial_device.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`hmi/device/serial_device.py`:
```python
"""SerialDevice: talks to the real ventilator MCU over USB/UART (implements DeviceLink).

Reads protocol lines (docs/05-serial-protocol.md) every 10 ms and turns them into signals, sends a
heartbeat every 200 ms, and reports the link as lost when no MCU heartbeat arrives for 1 s.
Not yet tested against real firmware; the unit tests use a fake serial port.
"""
from __future__ import annotations

import time

from hmi.device.base import DeviceLink
from hmi.device.messages import Ack, Fault, Heartbeat, MonitorStatus, Sample, TestResult
from hmi.device.protocol import (
    ProtocolError, encode_buzzer, encode_command, encode_heartbeat, encode_run_test,
    encode_settings, parse_mcu_message,
)
from hmi.model.settings import VentSettings
from hmi.qt import QtCore

POLL_MS = 10
HEARTBEAT_MS = 200
LINK_TIMEOUT_S = 1.0


class SerialDevice(DeviceLink):
    def __init__(self, port: str, baudrate: int = 115200, parent: QtCore.QObject | None = None,
                 serial_factory=None, clock=time.monotonic):
        super().__init__(parent)
        self._factory = serial_factory or (lambda: self._open_port(port, baudrate))
        self._clock = clock
        self._serial = None
        self._buffer = b""
        self._seq = 0
        self._opened_at = 0.0
        self._last_heartbeat: float | None = None
        self._link_state: bool | None = None  # None = not known yet
        self.bad_lines = 0
        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.timeout.connect(self.poll)
        self._beat_timer = QtCore.QTimer(self)
        self._beat_timer.timeout.connect(self.heartbeat)

    @staticmethod
    def _open_port(port: str, baudrate: int):
        import serial  # pyserial, imported here so the demo runs without it

        return serial.Serial(port, baudrate, timeout=0)

    # ----- DeviceLink ----------------------------------------------------------------------------
    def open(self) -> None:
        self._serial = self._factory()
        self._opened_at = self._clock()
        self._poll_timer.start(POLL_MS)
        self._beat_timer.start(HEARTBEAT_MS)

    def close(self) -> None:
        self._poll_timer.stop()
        self._beat_timer.stop()
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def apply_settings(self, settings: VentSettings, pmax: float) -> None:
        for line in encode_settings(settings, pmax):
            self._send(line)

    def start_ventilation(self) -> None:
        self._send(encode_command("START"))

    def standby(self) -> None:
        self._send(encode_command("STANDBY"))

    def run_test(self, test: str) -> None:
        self._send(encode_run_test(test))

    def set_buzzer(self, priority: int, paused: bool) -> None:
        self._send(encode_buzzer(priority, paused))

    # ----- I/O -----------------------------------------------------------------------------------
    def poll(self) -> None:
        if self._serial is None:
            return
        waiting = self._serial.in_waiting
        if waiting:
            self._buffer += self._serial.read(waiting)
        *lines, self._buffer = self._buffer.split(b"\n")
        for raw in lines:
            self._handle_line(raw.decode("ascii", errors="replace"))

    def heartbeat(self) -> None:
        """Send our heartbeat; report the link lost once if the MCU has been silent for > 1 s."""
        self._seq += 1
        self._send(encode_heartbeat(self._seq))
        last = self._last_heartbeat if self._last_heartbeat is not None else self._opened_at
        if self._clock() - last > LINK_TIMEOUT_S and self._link_state is not False:
            self._set_link(False)

    def _send(self, line: str) -> None:
        if self._serial is not None:
            self._serial.write(line.encode("ascii"))

    def _set_link(self, ok: bool) -> None:
        self._link_state = ok
        self.link_changed.emit(ok)

    def _handle_line(self, line: str) -> None:
        if not line.strip():
            return
        try:
            msg = parse_mcu_message(line)
        except ProtocolError:
            self.bad_lines += 1
            return
        if isinstance(msg, Sample):
            self.sample_received.emit(msg)
        elif isinstance(msg, MonitorStatus):
            self.status_received.emit(msg)
        elif isinstance(msg, TestResult):
            self.test_finished.emit(msg)
        elif isinstance(msg, Fault):
            self.fault_changed.emit(msg.code, msg.active)
        elif isinstance(msg, Heartbeat):
            self._last_heartbeat = self._clock()
            if self._link_state is not True:
                self._set_link(True)
        elif isinstance(msg, Ack) and not msg.ok:
            self.fault_changed.emit(f"CMD_{msg.command}_REJECTED", True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_serial_device.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add hmi/device/serial_device.py tests/test_serial_device.py
git commit -m "Add SerialDevice for the real MCU link"
```

---

### Task 12: Theme, basic widgets and basic dialogs

**Files:**
- Modify: `hmi/qt.py` (add `QShortcut` compatibility)
- Create: `hmi/ui/__init__.py`, `hmi/ui/theme.py`, `hmi/ui/widgets/__init__.py`, `hmi/ui/widgets/toggle_group.py`, `hmi/ui/widgets/inline_adjuster.py`, `hmi/ui/widgets/param_tile.py`, `hmi/ui/widgets/step_indicator.py`, `hmi/ui/widgets/numeric_readout.py`, `hmi/ui/dialogs/__init__.py`, `hmi/ui/dialogs/base.py`, `hmi/ui/dialogs/confirm.py`, `hmi/ui/dialogs/value_adjust.py`, `hmi/ui/dialogs/keyboard.py`
- Test: `tests/test_ui_basics.py`

**Interfaces:**
- Consumes: `NumericSpec`, `Priority`, `Step`
- Produces:
  - theme: color constants `BG, SURFACE, SURFACE_2, BORDER, TEXT, MUTED, PRIMARY, GO, DANGER, ADVISORY, ALARM_COLORS, ALARM_TEXT, WAVE_COLORS`, `apply_theme(app)`, `make_button(text, role=None)`, `make_label(text="", size=16, bold=False, muted=False, color=None)`, `make_card()`, `transparent_for_mouse(*widgets)`, `ALIGN_CENTER`
  - `ToggleGroup(options, value)` signal `changed(str)`, `value()`, `set_value(key)`, `button(key)`
  - `InlineAdjuster(spec, value)` signal `changed(float)`, `value()`, `set_spec(spec, value)`, `step(direction)`
  - `ParamTile(title, unit="", compact=False)` (a `QPushButton`) with `set_title`, `set_unit`, `set_value(text)`, `value_text()`, `set_note(text|None)`, `note_text()`
  - `StepIndicator()` with `set_step(step)`, `text_of(step)`
  - `NumericReadout(title, unit, accent=TEXT)` with `set_value(text)`, `value_text()`, `set_limits(low=None, high=None)`, `set_alarm(priority)`, `.alarm_priority`
  - `HmiDialog(parent, title, min_width=560)` with `.body` layout; `ConfirmDialog.ask(parent, title, text, confirm_text="Confirm", role="primary", cancel_text="Cancel")->bool`, `ConfirmDialog.inform(parent, title, text)`
  - `ValueAdjustDialog(parent, spec, value, title=None, validator=None, hint="")` with `step(n)`, `value()`, `.confirm_button`, `error_text()`, static `ask(...)->float|None`
  - `KeyboardDialog(parent, title, text="")` with `type(ch)`, `backspace()`, `clear()`, `text()`, static `ask(parent, title, text="")->str|None`

- [ ] **Step 1: Write the failing tests**

`tests/test_ui_basics.py`:
```python
from hmi.core.alarms.definitions import Priority
from hmi.core.flow import Step
from hmi.model.patient import Category, height_spec
from hmi.model.settings import param_spec
from hmi.ui.dialogs.confirm import ConfirmDialog
from hmi.ui.dialogs.keyboard import KeyboardDialog
from hmi.ui.dialogs.value_adjust import ValueAdjustDialog
from hmi.ui.widgets.inline_adjuster import InlineAdjuster
from hmi.ui.widgets.numeric_readout import NumericReadout
from hmi.ui.widgets.param_tile import ParamTile
from hmi.ui.widgets.step_indicator import StepIndicator
from hmi.ui.widgets.toggle_group import ToggleGroup


def test_toggle_group_emits_only_on_change(qapp):
    tg = ToggleGroup([("a", "A"), ("b", "B")], "a")
    seen = []
    tg.changed.connect(seen.append)
    tg.button("b").click()
    tg.button("b").click()
    assert seen == ["b"] and tg.value() == "b"


def test_inline_adjuster_clamps_to_range(qapp):
    adj = InlineAdjuster(height_spec(Category.ADULT), 209)
    seen = []
    adj.changed.connect(seen.append)
    adj.step(+1)
    adj.step(+1)
    assert adj.value() == 210 and seen == [210]


def test_param_tile_note(qapp):
    tile = ParamTile("VT", "mL")
    tile.set_value("460")
    tile.set_note("10.6 mL/kg IBW")
    assert tile.value_text() == "460" and tile.note_text() == "10.6 mL/kg IBW"
    tile.set_note(None)
    assert tile.note_text() == ""


def test_step_indicator_marks_done_steps(qapp):
    si = StepIndicator()
    si.set_step(Step.SETTINGS)
    assert si.text_of(Step.PATIENT).startswith("✔")
    assert si.text_of(Step.SETTINGS) == "3. Settings"


def test_numeric_readout_alarm_state(qapp):
    r = NumericReadout("PIP", "cmH2O")
    r.set_value("45")
    r.set_limits(8, 40)
    r.set_alarm(Priority.HIGH)
    assert r.value_text() == "45" and r.alarm_priority is Priority.HIGH


def test_value_adjust_dialog_validates(qapp):
    spec = param_spec(Category.ADULT, "vt")
    dlg = ValueAdjustDialog(None, spec, 460, validator=lambda v: "too high" if v > 600 else None)
    dlg.step(10)
    assert dlg.value() == 560 and dlg.confirm_button.isEnabled()
    dlg.step(10)
    assert dlg.value() == 660 and not dlg.confirm_button.isEnabled() and dlg.error_text() == "too high"
    dlg.step(1000)
    assert dlg.value() == 1000


def test_keyboard_dialog_typing(qapp):
    kb = KeyboardDialog(None, "Name", "J")
    kb.type(".")
    kb.type("X")
    kb.backspace()
    assert kb.text() == "J."
    kb.clear()
    assert kb.text() == ""


def test_confirm_dialog_buttons(qapp):
    dlg = ConfirmDialog(None, "Title", "Text", confirm_text="Start", cancel_text=None)
    assert dlg.confirm_button.text() == "Start" and dlg.cancel_button is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_ui_basics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'hmi.ui'`

- [ ] **Step 3: Add QShortcut compatibility to `hmi/qt.py`**

Append to `hmi/qt.py`:
```python

# QShortcut lives in QtGui on Qt 6 and in QtWidgets on Qt 5.
QShortcut = getattr(QtGui, "QShortcut", None) or QtWidgets.QShortcut
```

- [ ] **Step 4: Implement the theme**

`hmi/ui/__init__.py`:
```python
"""Qt user interface: theme, widgets, dialogs, screens and the main window."""
```

`hmi/ui/theme.py`:
```python
"""Colors, fonts, the Qt stylesheet and small widget helpers for the whole HMI.

Red, yellow and cyan are reserved for alarms (IEC 60601-1-8 alarm colors). Waveforms use green,
magenta and periwinkle; advisories (not alarms) use orange. The dark background suits ICU use and
keeps contrast high through VNC.
"""
from __future__ import annotations

from hmi.core.alarms.definitions import Priority
from hmi.qt import QtCore, QtGui, QtWidgets

BG = "#0b0f14"
SURFACE = "#141b24"
SURFACE_2 = "#1c2530"
BORDER = "#2a3645"
TEXT = "#e6edf3"
MUTED = "#8b98a5"
PRIMARY = "#4f6bff"
GO = "#1f9d55"
DANGER = "#8e2431"
ADVISORY = "#ff8a3d"
ALARM_COLORS = {Priority.HIGH: "#ff3b3b", Priority.MEDIUM: "#ffd000", Priority.LOW: "#22d3ee"}
ALARM_TEXT = {Priority.HIGH: "#ffffff", Priority.MEDIUM: "#111111", Priority.LOW: "#111111"}
WAVE_COLORS = {"pressure": "#7ee081", "flow": "#e879f9", "volume": "#a5b4fc"}

ALIGN_CENTER = QtCore.Qt.AlignmentFlag.AlignCenter

STYLESHEET = f"""
QMainWindow {{ background: {BG}; }}
QWidget {{ color: {TEXT}; font-size: 16px; }}
QLabel {{ background: transparent; }}
QFrame#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
QPushButton {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 10px;
              padding: 6px 14px; min-height: 48px; font-size: 18px; color: {TEXT}; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: #55606c; background: #11161d; border-color: #1a222c; }}
QPushButton[role="primary"] {{ background: {PRIMARY}; border-color: {PRIMARY}; font-weight: 600; }}
QPushButton[role="go"] {{ background: {GO}; border-color: {GO}; font-weight: 700; }}
QPushButton[role="danger"] {{ background: {DANGER}; border-color: #b33a48; font-weight: 700; }}
QPushButton[role="toggle"]:checked {{ background: {PRIMARY}; border-color: {PRIMARY}; font-weight: 600; }}
QPushButton[role="primary"]:disabled, QPushButton[role="go"]:disabled {{
    background: #11161d; border-color: #1a222c; color: #55606c; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: {SURFACE}; color: {MUTED}; padding: 12px 28px; margin-right: 6px;
               border-top-left-radius: 10px; border-top-right-radius: 10px; font-size: 18px; min-width: 150px; }}
QTabBar::tab:selected {{ background: {SURFACE_2}; color: {TEXT}; border-bottom: 3px solid {PRIMARY}; }}
QListWidget, QTableWidget {{ background: {SURFACE}; border: 1px solid {BORDER}; gridline-color: {BORDER}; }}
QHeaderView::section {{ background: {SURFACE_2}; color: {MUTED}; border: none; padding: 6px; }}
QCheckBox {{ spacing: 12px; font-size: 18px; min-height: 44px; }}
QCheckBox::indicator {{ width: 28px; height: 28px; }}
QComboBox {{ min-height: 44px; font-size: 18px; padding: 4px 12px; background: {SURFACE_2};
            border: 1px solid {BORDER}; border-radius: 8px; }}
QScrollBar:vertical {{ width: 22px; background: {SURFACE}; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 8px; min-height: 40px; }}
"""


def apply_theme(app: QtWidgets.QApplication) -> None:
    app.setStyle("Fusion")
    palette = QtGui.QPalette()
    role = QtGui.QPalette.ColorRole
    for r, color in ((role.Window, BG), (role.Base, SURFACE), (role.AlternateBase, SURFACE_2),
                     (role.Button, SURFACE_2), (role.Text, TEXT), (role.WindowText, TEXT),
                     (role.ButtonText, TEXT), (role.Highlight, PRIMARY), (role.HighlightedText, "#ffffff")):
        palette.setColor(r, QtGui.QColor(color))
    app.setPalette(palette)
    font = QtGui.QFont()
    font.setFamilies(["Segoe UI", "DejaVu Sans", "Noto Sans", "Arial"])
    font.setPixelSize(16)
    app.setFont(font)
    app.setStyleSheet(STYLESHEET)


def make_button(text: str, role: str | None = None) -> QtWidgets.QPushButton:
    button = QtWidgets.QPushButton(text)
    if role:
        button.setProperty("role", role)
    return button


def make_label(text: str = "", size: int = 16, bold: bool = False, muted: bool = False,
               color: str | None = None) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    style = [f"font-size: {size}px"]
    if bold:
        style.append("font-weight: 700")
    if muted or color:
        style.append(f"color: {color or MUTED}")
    label.setStyleSheet("; ".join(style) + ";")
    return label


def make_card() -> QtWidgets.QFrame:
    frame = QtWidgets.QFrame()
    frame.setObjectName("card")
    return frame


def transparent_for_mouse(*widgets: QtWidgets.QWidget) -> None:
    """Let clicks pass through labels placed inside a button."""
    for widget in widgets:
        widget.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
```

- [ ] **Step 5: Implement the widgets**

`hmi/ui/widgets/__init__.py`:
```python
"""Reusable HMI widgets (tiles, readouts, waveforms, alarm banner...)."""
```

`hmi/ui/widgets/toggle_group.py`:
```python
"""ToggleGroup: a row of big buttons where exactly one is selected (like Adult / Pediatric)."""
from __future__ import annotations

from hmi.qt import QtWidgets, Signal
from hmi.ui.theme import make_button


class ToggleGroup(QtWidgets.QWidget):
    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], value: str, min_width: int = 140):
        super().__init__()
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self._group = QtWidgets.QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QtWidgets.QPushButton] = {}
        for key, text in options:
            button = make_button(text, "toggle")
            button.setCheckable(True)
            button.setMinimumWidth(min_width)
            button.clicked.connect(lambda _checked=False, k=key: self._select(k))
            self._group.addButton(button)
            self._buttons[key] = button
            layout.addWidget(button)
        layout.addStretch(1)
        self._value = value
        self._buttons[value].setChecked(True)

    def value(self) -> str:
        return self._value

    def set_value(self, key: str) -> None:
        self._value = key
        self._buttons[key].setChecked(True)

    def button(self, key: str) -> QtWidgets.QPushButton:
        return self._buttons[key]

    def _select(self, key: str) -> None:
        if key != self._value:
            self._value = key
            self.changed.emit(key)
```

`hmi/ui/widgets/inline_adjuster.py`:
```python
"""InlineAdjuster: big  -  value  +  buttons for a number, used on the Patient screen (height)."""
from __future__ import annotations

from hmi.model.spec import NumericSpec
from hmi.qt import QtWidgets, Signal
from hmi.ui.theme import ALIGN_CENTER, make_button, make_label


class InlineAdjuster(QtWidgets.QWidget):
    changed = Signal(float)

    def __init__(self, spec: NumericSpec, value: float):
        super().__init__()
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        minus, plus = make_button("−"), make_button("+")
        for button, direction in ((minus, -1), (plus, +1)):
            button.setFixedSize(76, 60)
            button.setStyleSheet("font-size: 28px;")
            button.setAutoRepeat(True)
            button.setAutoRepeatDelay(400)
            button.setAutoRepeatInterval(60)
            button.clicked.connect(lambda _checked=False, d=direction: self.step(d))
        self._label = make_label("", 32, bold=True)
        self._label.setMinimumWidth(110)
        self._label.setAlignment(ALIGN_CENTER)
        self._unit = make_label("", 16, muted=True)
        layout.addWidget(minus)
        layout.addWidget(self._label)
        layout.addWidget(plus)
        layout.addWidget(self._unit)
        layout.addStretch(1)
        self._value: float | None = None
        self.set_spec(spec, value)

    def value(self) -> float:
        return self._value

    def set_spec(self, spec: NumericSpec, value: float) -> None:
        self._spec = spec
        self._unit.setText(spec.unit)
        self._set(value, emit=False)

    def step(self, direction: int) -> None:
        self._set(self._value + direction * self._spec.step, emit=True)

    def _set(self, value: float, emit: bool) -> None:
        value = self._spec.clamp(value)
        changed = value != self._value
        self._value = value
        self._label.setText(self._spec.fmt(value))
        if emit and changed:
            self.changed.emit(value)
```

`hmi/ui/widgets/param_tile.py`:
```python
"""ParamTile: a big tappable tile showing one setting (title, value, unit, optional advisory)."""
from __future__ import annotations

from hmi.qt import QtWidgets
from hmi.ui.theme import ADVISORY, make_label, transparent_for_mouse


class ParamTile(QtWidgets.QPushButton):
    def __init__(self, title: str, unit: str = "", compact: bool = False):
        super().__init__()
        self.setMinimumSize(118 if compact else 170, 84 if compact else 112)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(0)
        self._title = make_label(title, 14 if compact else 16, muted=True)
        self._value = make_label("--", 26 if compact else 34, bold=True)
        self._unit = make_label(unit, 12 if compact else 14, muted=True)
        self._note = make_label("", 12, color=ADVISORY)
        self._note.setWordWrap(True)
        self._note.hide()
        for widget in (self._title, self._value, self._unit, self._note):
            layout.addWidget(widget)
        transparent_for_mouse(self._title, self._value, self._unit, self._note)

    def set_title(self, text: str) -> None:
        self._title.setText(text)

    def set_unit(self, text: str) -> None:
        self._unit.setText(text)

    def set_value(self, text: str) -> None:
        self._value.setText(text)

    def value_text(self) -> str:
        return self._value.text()

    def set_note(self, text: str | None) -> None:
        self._note.setText(text or "")
        self._note.setVisible(bool(text))
        self.setStyleSheet(f"QPushButton {{ border: 2px solid {ADVISORY}; }}" if text else "")

    def note_text(self) -> str:
        return self._note.text()
```

`hmi/ui/widgets/step_indicator.py`:
```python
"""StepIndicator: '1. Patient > 2. Pre-use check > 3. Settings > 4. Ventilate' with the current step highlighted."""
from __future__ import annotations

from hmi.core.flow import Step
from hmi.qt import QtWidgets
from hmi.ui.theme import MUTED, PRIMARY, TEXT, make_label

STEP_NAMES = {Step.PATIENT: "Patient", Step.PRECHECK: "Pre-use check",
              Step.SETTINGS: "Settings", Step.VENTILATING: "Ventilate"}


class StepIndicator(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(10)
        self._labels: dict[Step, QtWidgets.QLabel] = {}
        for i, step in enumerate(Step):
            if i:
                layout.addWidget(make_label("›", 22, muted=True))
            label = QtWidgets.QLabel()
            self._labels[step] = label
            layout.addWidget(label)
        layout.addStretch(1)
        self.set_step(Step.PATIENT)

    def set_step(self, current: Step) -> None:
        for step, label in self._labels.items():
            if step < current:
                label.setText(f"✔ {STEP_NAMES[step]}")
                label.setStyleSheet(f"color: {TEXT}; font-size: 17px;")
            elif step == current:
                label.setText(f"{int(step)}. {STEP_NAMES[step]}")
                label.setStyleSheet(f"color: #ffffff; background: {PRIMARY}; border-radius: 14px; "
                                    f"padding: 4px 14px; font-size: 17px; font-weight: 700;")
            else:
                label.setText(f"{int(step)}. {STEP_NAMES[step]}")
                label.setStyleSheet(f"color: {MUTED}; font-size: 17px;")

    def text_of(self, step: Step) -> str:
        return self._labels[step].text()
```

`hmi/ui/widgets/numeric_readout.py`:
```python
"""NumericReadout: one measured value (e.g. PIP) with unit and alarm limits.

The value and border take the alarm color while an alarm on this value is active.
"""
from __future__ import annotations

from hmi.core.alarms.definitions import Priority
from hmi.qt import QtCore, QtWidgets
from hmi.ui.theme import ALARM_COLORS, TEXT, make_label

_RIGHT_TOP = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignTop
_RIGHT_BOTTOM = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignBottom
_VALUE_STYLE = "font-size: 40px; font-weight: 700;"


class NumericReadout(QtWidgets.QFrame):
    def __init__(self, title: str, unit: str, accent: str = TEXT):
        super().__init__()
        self.setObjectName("card")
        grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(12, 8, 12, 8)
        grid.setSpacing(2)
        self._title = make_label(title, 16, bold=True, color=accent)
        self._unit = make_label(unit, 13, muted=True)
        self._value = make_label("--")
        self._value.setStyleSheet(_VALUE_STYLE)
        self._high = make_label("", 13, muted=True)
        self._low = make_label("", 13, muted=True)
        grid.addWidget(self._title, 0, 0)
        grid.addWidget(self._unit, 0, 1, _RIGHT_TOP)
        grid.addWidget(self._value, 1, 0, 2, 1)
        grid.addWidget(self._high, 1, 1, _RIGHT_TOP)
        grid.addWidget(self._low, 2, 1, _RIGHT_BOTTOM)
        self.alarm_priority = Priority.NONE

    def set_value(self, text: str) -> None:
        self._value.setText(text)

    def value_text(self) -> str:
        return self._value.text()

    def set_limits(self, low=None, high=None) -> None:
        self._high.setText("" if high is None else f"▲ {high:g}")
        self._low.setText("" if low is None else f"▼ {low:g}")

    def set_alarm(self, priority: Priority) -> None:
        if priority == self.alarm_priority:
            return
        self.alarm_priority = priority
        if priority:
            color = ALARM_COLORS[priority]
            self._value.setStyleSheet(f"{_VALUE_STYLE} color: {color};")
            self.setStyleSheet(f"QFrame#card {{ border: 2px solid {color}; }}")
        else:
            self._value.setStyleSheet(_VALUE_STYLE)
            self.setStyleSheet("")
```

- [ ] **Step 6: Implement the basic dialogs**

`hmi/ui/dialogs/__init__.py`:
```python
"""Modal HMI dialogs: confirmation, value adjuster, on-screen keyboard, modes, alarms, demo panel."""
```

`hmi/ui/dialogs/base.py`:
```python
"""HmiDialog: base for every HMI dialog — frameless, modal, big title (easy to use through VNC)."""
from __future__ import annotations

from hmi.qt import QtCore, QtWidgets
from hmi.ui.theme import BORDER, SURFACE, make_label


class HmiDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None, title: str, min_width: int = 560):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.WindowType.Dialog | QtCore.Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        self.setMinimumWidth(min_width)
        self.setStyleSheet(f"HmiDialog {{ background: {SURFACE}; border: 2px solid {BORDER}; }}")
        self.body = QtWidgets.QVBoxLayout(self)
        self.body.setContentsMargins(28, 24, 28, 24)
        self.body.setSpacing(16)
        self.title_label = make_label(title, 24, bold=True)
        self.body.addWidget(self.title_label)
```

`hmi/ui/dialogs/confirm.py`:
```python
"""ConfirmDialog: every action that changes ventilation asks for an explicit confirmation."""
from __future__ import annotations

from hmi.qt import QtWidgets
from hmi.ui.dialogs.base import HmiDialog
from hmi.ui.theme import make_button, make_label


class ConfirmDialog(HmiDialog):
    def __init__(self, parent, title: str, text: str, confirm_text: str = "Confirm",
                 cancel_text: str | None = "Cancel", role: str = "primary"):
        super().__init__(parent, title)
        message = make_label(text, 19)
        message.setWordWrap(True)
        self.body.addWidget(message)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        self.cancel_button = None
        if cancel_text:
            self.cancel_button = make_button(cancel_text)
            self.cancel_button.setMinimumWidth(170)
            self.cancel_button.clicked.connect(self.reject)
            row.addWidget(self.cancel_button)
        self.confirm_button = make_button(confirm_text, role)
        self.confirm_button.setMinimumWidth(210)
        self.confirm_button.clicked.connect(self.accept)
        row.addWidget(self.confirm_button)
        self.body.addLayout(row)

    @staticmethod
    def ask(parent, title: str, text: str, confirm_text: str = "Confirm", role: str = "primary",
            cancel_text: str | None = "Cancel") -> bool:
        return bool(ConfirmDialog(parent, title, text, confirm_text, cancel_text, role).exec())

    @staticmethod
    def inform(parent, title: str, text: str) -> None:
        ConfirmDialog.ask(parent, title, text, confirm_text="OK", cancel_text=None)
```

`hmi/ui/dialogs/value_adjust.py`:
```python
"""ValueAdjustDialog: change one number with big - / + buttons, then Confirm or Cancel.

Nothing changes until Confirm. A validator can block Confirm and explain why (safety cross-checks).
Wide ranges also get coarse buttons (10 steps at a time).
"""
from __future__ import annotations

from typing import Callable

from hmi.model.spec import NumericSpec
from hmi.qt import QtWidgets
from hmi.ui.dialogs.base import HmiDialog
from hmi.ui.theme import ADVISORY, ALIGN_CENTER, make_button, make_label

Validator = Callable[[float], "str | None"]


class ValueAdjustDialog(HmiDialog):
    def __init__(self, parent, spec: NumericSpec, value: float, title: str | None = None,
                 validator: Validator | None = None, hint: str = ""):
        super().__init__(parent, title or f"Set {spec.label}", min_width=640)
        self._spec, self._validator = spec, validator
        coarse = (spec.maximum - spec.minimum) / spec.step > 40

        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)

        def add_button(text: str, steps: int) -> None:
            button = make_button(text)
            button.setFixedSize(100, 88)
            button.setStyleSheet("font-size: 26px;")
            button.setAutoRepeat(True)
            button.setAutoRepeatDelay(400)
            button.setAutoRepeatInterval(80)
            button.clicked.connect(lambda _checked=False, n=steps: self.step(n))
            row.addWidget(button)

        if coarse:
            add_button(f"−{spec.fmt(10 * spec.step)}", -10)
        add_button("−", -1)
        column = QtWidgets.QVBoxLayout()
        self._value_label = make_label("", 64, bold=True)
        self._value_label.setAlignment(ALIGN_CENTER)
        self._value_label.setMinimumWidth(200)
        unit = make_label(spec.unit, 18, muted=True)
        unit.setAlignment(ALIGN_CENTER)
        column.addWidget(self._value_label)
        column.addWidget(unit)
        row.addLayout(column)
        add_button("+", 1)
        if coarse:
            add_button(f"+{spec.fmt(10 * spec.step)}", 10)
        row.addStretch(1)
        self.body.addLayout(row)

        range_label = make_label(f"Range {spec.range_text()}", 15, muted=True)
        range_label.setAlignment(ALIGN_CENTER)
        self.body.addWidget(range_label)
        if hint:
            hint_label = make_label(hint, 15, muted=True)
            hint_label.setWordWrap(True)
            hint_label.setAlignment(ALIGN_CENTER)
            self.body.addWidget(hint_label)
        self._error = make_label("", 16, color=ADVISORY)
        self._error.setWordWrap(True)
        self.body.addWidget(self._error)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        cancel = make_button("Cancel")
        cancel.setMinimumWidth(170)
        cancel.clicked.connect(self.reject)
        self.confirm_button = make_button("Confirm", "primary")
        self.confirm_button.setMinimumWidth(210)
        self.confirm_button.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(self.confirm_button)
        self.body.addLayout(buttons)

        self._value = spec.clamp(value)
        self._set(self._value)

    def step(self, n: int) -> None:
        self._set(self._value + n * self._spec.step)

    def value(self) -> float:
        return self._value

    def error_text(self) -> str:
        return self._error.text()

    def _set(self, value: float) -> None:
        self._value = self._spec.clamp(value)
        self._value_label.setText(self._spec.fmt(self._value))
        error = self._validator(self._value) if self._validator else None
        self._error.setText(error or "")
        self._error.setVisible(bool(error))
        self.confirm_button.setEnabled(error is None)

    @staticmethod
    def ask(parent, spec: NumericSpec, value: float, title: str | None = None,
            validator: Validator | None = None, hint: str = "") -> float | None:
        dialog = ValueAdjustDialog(parent, spec, value, title, validator, hint)
        return dialog.value() if dialog.exec() else None
```

`hmi/ui/dialogs/keyboard.py`:
```python
"""KeyboardDialog: on-screen keyboard for the optional patient name and ID (no typing over VNC needed)."""
from __future__ import annotations

from hmi.qt import QtWidgets
from hmi.ui.dialogs.base import HmiDialog
from hmi.ui.theme import SURFACE_2, make_button, make_label

ROWS = ("1234567890", "QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM-.")
MAX_LENGTH = 24


class KeyboardDialog(HmiDialog):
    def __init__(self, parent, title: str, text: str = ""):
        super().__init__(parent, title, min_width=900)
        self._text = text
        self._display = make_label("", 28, bold=True)
        self._display.setStyleSheet(f"font-size: 28px; font-weight: 700; background: {SURFACE_2}; "
                                    "padding: 8px 14px; border-radius: 8px;")
        self._display.setMinimumHeight(56)
        self.body.addWidget(self._display)
        for keys in ROWS:
            row = QtWidgets.QHBoxLayout()
            row.addStretch(1)
            for ch in keys:
                key = make_button(ch)
                key.setFixedSize(72, 60)
                key.clicked.connect(lambda _checked=False, c=ch: self.type(c))
                row.addWidget(key)
            row.addStretch(1)
            self.body.addLayout(row)
        bottom = QtWidgets.QHBoxLayout()
        for text_, slot, width in (("Clear", self.clear, 120), ("Space", lambda: self.type(" "), 300),
                                   ("Back", self.backspace, 120)):
            button = make_button(text_)
            button.setFixedWidth(width)
            button.clicked.connect(slot)
            bottom.addWidget(button)
        bottom.addStretch(1)
        cancel = make_button("Cancel")
        cancel.clicked.connect(self.reject)
        ok = make_button("OK", "primary")
        ok.setMinimumWidth(160)
        ok.clicked.connect(self.accept)
        bottom.addWidget(cancel)
        bottom.addWidget(ok)
        self.body.addLayout(bottom)
        self._refresh()

    def type(self, ch: str) -> None:
        if len(self._text) < MAX_LENGTH:
            self._text += ch
            self._refresh()

    def backspace(self) -> None:
        self._text = self._text[:-1]
        self._refresh()

    def clear(self) -> None:
        self._text = ""
        self._refresh()

    def text(self) -> str:
        return self._text.strip()

    def _refresh(self) -> None:
        self._display.setText(self._text + "_")

    @staticmethod
    def ask(parent, title: str, text: str = "") -> str | None:
        dialog = KeyboardDialog(parent, title, text)
        return dialog.text() if dialog.exec() else None
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_ui_basics.py -v`
Expected: 8 passed

- [ ] **Step 8: Commit**

```bash
git add hmi/qt.py hmi/ui tests/test_ui_basics.py
git commit -m "Add theme, basic widgets and confirmation/adjuster/keyboard dialogs"
```

---

### Task 13: Waveform panel, alarm banner and top bar

**Files:**
- Create: `hmi/ui/widgets/waveform_panel.py`, `hmi/ui/widgets/alarm_banner.py`, `hmi/ui/top_bar.py`
- Test: `tests/test_ui_live.py`

**Interfaces:**
- Consumes: `Sample`, `Category`, `AlarmState`, `ALARMS`, `Priority`, theme
- Produces:
  - `WaveformPanel()` with `add_sample(sample)`, `redraw()`, `clear()`, `set_category(category)`, `trace(key)->np.ndarray`, `.index`
  - `AlarmBanner()` (a `QPushButton`) with `show_alarm(top: AlarmState|None, others: int)`, `is_flashing()`, `text()`-like `message_text()`, `badge_text()`
  - `TopBar()` signals `logo_long_pressed`, `banner_clicked`, `audio_pause_clicked`, `alarm_reset_clicked`; attribute `.banner`; methods `set_mode(text)`, `set_patient(text)`, `set_power(on_battery, pct)`, `set_audio_paused(remaining_s|None)`, `audio_pause_text()`

- [ ] **Step 1: Write the failing tests**

`tests/test_ui_live.py`:
```python
import math

from hmi.core.alarms.definitions import ALARMS
from hmi.core.alarms.engine import AlarmState
from hmi.device.messages import Sample
from hmi.ui.top_bar import TopBar
from hmi.ui.widgets.alarm_banner import AlarmBanner
from hmi.ui.widgets.waveform_panel import GAP_POINTS, POINTS, WaveformPanel


def test_waveform_sweeps_and_leaves_an_erase_gap(qapp):
    panel = WaveformPanel()
    for i in range(POINTS + 20):
        panel.add_sample(Sample(i * 20, 10.0, 5.0, 100.0, "I"))
    assert panel.index == 20
    pressure = panel.trace("pressure")
    assert all(math.isnan(v) for v in pressure[20:20 + GAP_POINTS])
    assert pressure[19] == 10.0
    panel.redraw()
    panel.clear()
    assert all(math.isnan(v) for v in panel.trace("volume"))


def test_banner_flashes_for_active_high_and_is_steady_when_resolved(qapp):
    banner = AlarmBanner()
    state = AlarmState(ALARMS["HIGH_PRESSURE"], onset=0.0, detail="45.0 > 40 cmH2O")
    banner.show_alarm(state, 2)
    assert banner.is_flashing() and banner.badge_text() == "+2"
    assert banner.message_text().startswith("!!! HIGH PRESSURE")
    state.active = False
    banner.show_alarm(state, 0)
    assert not banner.is_flashing() and banner.badge_text() == ""
    banner.show_alarm(None, 0)
    assert banner.message_text() == "No active alarms"


def test_low_priority_banner_is_steady(qapp):
    banner = AlarmBanner()
    banner.show_alarm(AlarmState(ALARMS["NO_PRECHECK"], onset=0.0), 0)
    assert not banner.is_flashing()


def test_top_bar_audio_pause_countdown(qapp):
    bar = TopBar()
    bar.set_audio_paused(103)
    assert "1:43" in bar.audio_pause_text()
    bar.set_audio_paused(None)
    assert "1:43" not in bar.audio_pause_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_ui_live.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the waveform panel**

`hmi/ui/widgets/waveform_panel.py`:
```python
"""WaveformPanel: live pressure, flow and volume curves (pyqtgraph), 10 s window, sweep mode.

Like a bedside monitor, the trace is written left to right and a short gap is erased ahead of the
write position. Samples arrive at 50 Hz; the screen redraws at 25 fps. Y ranges are fixed per patient
category so the curves do not jump around.
"""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg

from hmi.device.messages import Sample
from hmi.model.patient import Category
from hmi.qt import QtCore
from hmi.ui.theme import BG, BORDER, MUTED, WAVE_COLORS

WINDOW_S = 10.0
POINTS = 500          # 10 s x 50 Hz
GAP_POINTS = 15       # 0.3 s erase gap ahead of the sweep
REDRAW_MS = 40        # 25 fps
TRACES = (("pressure", "Paw", "cmH2O"), ("flow", "Flow", "L/min"), ("volume", "Volume", "mL"))
Y_RANGES = {
    Category.ADULT: {"pressure": (-2, 50), "flow": (-100, 100), "volume": (0, 800)},
    Category.PEDIATRIC: {"pressure": (-2, 40), "flow": (-50, 50), "volume": (0, 300)},
}


class WaveformPanel(pg.GraphicsLayoutWidget):
    def __init__(self):
        super().__init__()
        pg.setConfigOptions(antialias=False)
        self.setBackground(BG)
        self._x = np.linspace(0.0, WINDOW_S, POINTS, endpoint=False)
        self._data = {key: np.full(POINTS, np.nan) for key, _, _ in TRACES}
        self._plots: dict[str, pg.PlotItem] = {}
        self._curves: dict[str, pg.PlotDataItem] = {}
        self.index = 0
        self._dirty = False
        for row, (key, title, unit) in enumerate(TRACES):
            plot = self.addPlot(row=row, col=0)
            plot.setMenuEnabled(False)
            plot.setMouseEnabled(x=False, y=False)
            plot.hideButtons()
            plot.showGrid(x=False, y=True, alpha=0.15)
            plot.setXRange(0, WINDOW_S, padding=0)
            plot.setLabel("left", f"{title} ({unit})", color=WAVE_COLORS[key])
            plot.getAxis("left").setWidth(64)
            plot.getAxis("left").setTextPen(MUTED)
            plot.getAxis("bottom").setTextPen(MUTED)
            plot.getAxis("bottom").setStyle(showValues=(row == len(TRACES) - 1))
            plot.addLine(y=0, pen=pg.mkPen(BORDER))
            self._curves[key] = plot.plot(self._x, self._data[key], pen=pg.mkPen(WAVE_COLORS[key], width=2),
                                          connect="finite")
            self._plots[key] = plot
        self.set_category(Category.ADULT)
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.redraw)
        self._timer.start(REDRAW_MS)

    def set_category(self, category: Category) -> None:
        for key, (low, high) in Y_RANGES[category].items():
            self._plots[key].setYRange(low, high, padding=0)

    def add_sample(self, s: Sample) -> None:
        i = self.index
        self._data["pressure"][i] = s.pressure
        self._data["flow"][i] = s.flow
        self._data["volume"][i] = s.volume
        gap = (i + 1 + np.arange(GAP_POINTS)) % POINTS
        for values in self._data.values():
            values[gap] = np.nan
        self.index = (i + 1) % POINTS
        self._dirty = True

    def redraw(self) -> None:
        if not self._dirty:
            return
        for key, curve in self._curves.items():
            curve.setData(self._x, self._data[key], connect="finite")
        self._dirty = False

    def clear(self) -> None:
        for values in self._data.values():
            values[:] = np.nan
        self.index = 0
        self._dirty = True

    def trace(self, key: str) -> np.ndarray:
        return self._data[key]
```

- [ ] **Step 4: Implement the alarm banner**

`hmi/ui/widgets/alarm_banner.py`:
```python
"""AlarmBanner: shows the most important alarm, flashing per IEC 60601-1-8.

High priority: red, flashing 2 Hz. Medium: yellow, flashing 0.6 Hz. Low: cyan, steady.
Resolved (latched) alarms are shown steady with a colored border until Alarm Reset.
Tapping the banner opens the alarm list.
"""
from __future__ import annotations

from hmi.core.alarms.definitions import Priority
from hmi.core.alarms.engine import AlarmState
from hmi.qt import QtCore, QtWidgets
from hmi.ui.theme import ALARM_COLORS, ALARM_TEXT, BORDER, MUTED, SURFACE, SURFACE_2, make_label, transparent_for_mouse

FLASH_HALF_PERIOD_MS = {Priority.HIGH: 250, Priority.MEDIUM: 833}  # 2 Hz and 0.6 Hz at 50 % duty


class AlarmBanner(QtWidgets.QPushButton):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(56)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 12, 0)
        self._text = make_label("")
        self._badge = make_label("")
        layout.addWidget(self._text, 1)
        layout.addWidget(self._badge)
        transparent_for_mouse(self._text, self._badge)
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._toggle)
        self._key: tuple[Priority, bool] | None = None
        self._flash_on = True
        self.show_alarm(None, 0)

    def show_alarm(self, top: AlarmState | None, others: int) -> None:
        self._badge.setText(f"+{others}" if others > 0 else "")
        if top is None:
            self._timer.stop()
            self._key = None
            self._text.setText("No active alarms")
            self._render()
            return
        self._text.setText(top.message)
        key = (top.priority, top.active)
        if key != self._key:
            self._key = key
            self._timer.stop()
            self._flash_on = True
            interval = FLASH_HALF_PERIOD_MS.get(top.priority) if top.active else None
            if interval:
                self._timer.start(interval)
            self._render()

    def is_flashing(self) -> bool:
        return self._timer.isActive()

    def message_text(self) -> str:
        return self._text.text()

    def badge_text(self) -> str:
        return self._badge.text()

    def _toggle(self) -> None:
        self._flash_on = not self._flash_on
        self._render()

    def _render(self) -> None:
        if self._key is None:
            background, border, foreground = SURFACE, BORDER, MUTED
        else:
            priority, active = self._key
            border = ALARM_COLORS[priority]
            if active and self._flash_on:
                background, foreground = border, ALARM_TEXT[priority]
            else:
                background, foreground = SURFACE_2, border
        self.setStyleSheet(f"QPushButton {{ background: {background}; border: 2px solid {border}; border-radius: 10px; }}")
        label_style = f"font-size: 19px; font-weight: 700; color: {foreground};"
        self._text.setStyleSheet(label_style)
        self._badge.setStyleSheet(label_style)
```

- [ ] **Step 5: Implement the top bar**

`hmi/ui/top_bar.py`:
```python
"""TopBar: logo (long-press opens the Demo Panel), mode, patient, alarm banner, Audio Pause,
Alarm Reset, power and clock. Always visible on every screen."""
from __future__ import annotations

import math
from datetime import datetime

from hmi.qt import QtCore, QtWidgets, Signal
from hmi.ui.theme import ADVISORY, ALIGN_CENTER, BORDER, PRIMARY, SURFACE, make_button, make_label
from hmi.ui.widgets.alarm_banner import AlarmBanner

LONG_PRESS_MS = 2000
PAUSE_IDLE_TEXT = "Audio\npause"


class TopBar(QtWidgets.QFrame):
    logo_long_pressed = Signal()
    banner_clicked = Signal()
    audio_pause_clicked = Signal()
    alarm_reset_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("topbar")
        self.setFixedHeight(76)
        self.setStyleSheet(f"QFrame#topbar {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}")
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(8)

        self._logo = make_button("VENT")
        self._logo.setFixedSize(76, 56)
        self._logo.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {PRIMARY};")
        self._press_timer = QtCore.QTimer(self)
        self._press_timer.setSingleShot(True)
        self._press_timer.setInterval(LONG_PRESS_MS)
        self._press_timer.timeout.connect(self.logo_long_pressed.emit)
        self._logo.pressed.connect(self._press_timer.start)
        self._logo.released.connect(self._press_timer.stop)

        self._mode = make_label("STANDBY", 18, bold=True)
        self._mode.setFixedWidth(96)
        self._mode.setAlignment(ALIGN_CENTER)
        self._patient = make_label("", 14, muted=True)
        self._patient.setFixedWidth(170)
        self._patient.setWordWrap(True)

        self.banner = AlarmBanner()
        self.banner.clicked.connect(self.banner_clicked.emit)

        self._pause = make_button(PAUSE_IDLE_TEXT)
        self._pause.setFixedSize(112, 56)
        self._pause.setStyleSheet("font-size: 15px; min-height: 0px;")
        self._pause.clicked.connect(self.audio_pause_clicked.emit)
        self._reset = make_button("Alarm\nreset")
        self._reset.setFixedSize(112, 56)
        self._reset.setStyleSheet("font-size: 15px; min-height: 0px;")
        self._reset.clicked.connect(self.alarm_reset_clicked.emit)

        self._status = make_label("", 15, bold=True)
        self._status.setFixedWidth(96)
        self._status.setAlignment(ALIGN_CENTER)
        self._clock_text = ""
        self._power_text = "AC 100 %"
        self._power_color = None

        for widget in (self._logo, self._mode, self._patient):
            row.addWidget(widget)
        row.addWidget(self.banner, 1)
        for widget in (self._pause, self._reset, self._status):
            row.addWidget(widget)

        self._clock = QtCore.QTimer(self)
        self._clock.timeout.connect(self._tick_clock)
        self._clock.start(1000)
        self._tick_clock()

    def set_mode(self, text: str) -> None:
        self._mode.setText(text)

    def set_patient(self, text: str) -> None:
        self._patient.setText(text)

    def set_power(self, on_battery: bool, pct: float) -> None:
        self._power_text = f"{'BATT' if on_battery else 'AC'} {pct:.0f} %"
        self._power_color = ADVISORY if on_battery else None
        self._render_status()

    def set_audio_paused(self, remaining_s: float | None) -> None:
        if remaining_s is None:
            self._pause.setText(PAUSE_IDLE_TEXT)
            self._pause.setStyleSheet("font-size: 15px; min-height: 0px;")
            return
        minutes, seconds = divmod(int(math.ceil(remaining_s)), 60)
        self._pause.setText(f"Audio paused\n{minutes}:{seconds:02d}")
        self._pause.setStyleSheet(f"font-size: 14px; min-height: 0px; font-weight: 700; border: 2px solid {PRIMARY};")

    def audio_pause_text(self) -> str:
        return self._pause.text()

    def _tick_clock(self) -> None:
        self._clock_text = datetime.now().strftime("%H:%M")
        self._render_status()

    def _render_status(self) -> None:
        self._status.setText(f"{self._clock_text}\n{self._power_text}")
        color = f" color: {self._power_color};" if self._power_color else ""
        self._status.setStyleSheet(f"font-size: 15px; font-weight: 700;{color}")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_ui_live.py -v`
Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git add hmi/ui tests/test_ui_live.py
git commit -m "Add waveform panel, IEC-style alarm banner and top bar"
```

---

### Task 14: Patient Profile screen

**Files:**
- Create: `hmi/ui/screens/__init__.py`, `hmi/ui/screens/patient.py`
- Test: `tests/test_screens.py` (first tests; later tasks append to it)

**Interfaces:**
- Consumes: `PatientProfile`, `Category`, `Sex`, `DEFAULT_HEIGHT`, `AGE_SPEC`, `height_spec`, `ToggleGroup`, `InlineAdjuster`, `KeyboardDialog`, `ValueAdjustDialog`
- Produces: `PatientScreen()` signals `next_requested`, `quick_start_requested`; attributes `category` (ToggleGroup), `sex` (ToggleGroup), `height_adjuster` (InlineAdjuster); methods `profile()->PatientProfile`, `set_profile(p)`, `ibw_text()`

- [ ] **Step 1: Write the failing tests**

`tests/test_screens.py`:
```python
from hmi.model.patient import Category, PatientProfile
from hmi.ui.screens.patient import PatientScreen


def test_patient_screen_updates_ibw_live(qapp):
    screen = PatientScreen()
    assert screen.ibw_text() == "66.0 kg"
    screen.height_adjuster.step(+1)
    assert screen.profile().height_cm == 171
    screen.sex.button("female").click()
    assert screen.ibw_text() == "62.4 kg"  # 45.5 + 0.91 x (171 - 152.4)


def test_switching_to_pediatric_resets_height(qapp):
    screen = PatientScreen()
    screen.category.button("pediatric").click()
    p = screen.profile()
    assert p.category is Category.PEDIATRIC and p.height_cm == 110
    assert screen.height_adjuster.value() == 110


def test_set_profile_round_trip(qapp):
    screen = PatientScreen()
    p = PatientProfile(category=Category.PEDIATRIC, height_cm=120, name="TEST")
    screen.set_profile(p)
    assert screen.profile() == p
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_screens.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`hmi/ui/screens/__init__.py`:
```python
"""The four HMI screens: Patient Profile, Pre-Use Check, Settings, Monitoring."""
```

`hmi/ui/screens/patient.py`:
```python
"""Screen 1 — Patient Profile.

The operator picks Adult/Pediatric, sex and height; the screen shows the Ideal Body Weight (IBW),
its formula and the suggested tidal volume (6-8 mL/kg IBW). Name, ID and age are optional.
Quick Start skips the pre-use check (with confirmation, handled by the main window).
"""
from __future__ import annotations

from dataclasses import replace

from hmi.model.patient import AGE_SPEC, DEFAULT_HEIGHT, Category, PatientProfile, Sex, height_spec
from hmi.qt import QtWidgets, Signal
from hmi.ui.dialogs.keyboard import KeyboardDialog
from hmi.ui.dialogs.value_adjust import ValueAdjustDialog
from hmi.ui.theme import make_button, make_card, make_label
from hmi.ui.widgets.inline_adjuster import InlineAdjuster
from hmi.ui.widgets.toggle_group import ToggleGroup

FIELD_STYLE = "text-align: left; padding-left: 16px; font-size: 18px;"


class PatientScreen(QtWidgets.QWidget):
    next_requested = Signal()
    quick_start_requested = Signal()

    def __init__(self):
        super().__init__()
        self._profile = PatientProfile()
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(16)

        header = QtWidgets.QHBoxLayout()
        header.addWidget(make_label("Patient profile", 28, bold=True))
        header.addStretch(1)
        quick = make_button("Quick start", "danger")
        quick.setMinimumWidth(200)
        quick.clicked.connect(self.quick_start_requested.emit)
        header.addWidget(quick)
        root.addLayout(header)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(16)
        form_card = make_card()
        form = QtWidgets.QGridLayout(form_card)
        form.setContentsMargins(20, 20, 20, 20)
        form.setVerticalSpacing(14)
        form.setHorizontalSpacing(16)
        self.category = ToggleGroup([(c.value, c.title) for c in Category], Category.ADULT.value)
        self.sex = ToggleGroup([(Sex.MALE.value, "Male"), (Sex.FEMALE.value, "Female")], Sex.MALE.value)
        self.height_adjuster = InlineAdjuster(height_spec(Category.ADULT), DEFAULT_HEIGHT[Category.ADULT])
        self._name_button = make_button("")
        self._id_button = make_button("")
        self._age_button = make_button("")
        for button in (self._name_button, self._id_button, self._age_button):
            button.setStyleSheet(FIELD_STYLE)
            button.setMinimumWidth(320)
        rows = (("Category", self.category), ("Sex", self.sex), ("Height", self.height_adjuster),
                ("Name", self._name_button), ("Patient ID", self._id_button), ("Age", self._age_button))
        for r, (label, widget) in enumerate(rows):
            form.addWidget(make_label(label, 17, muted=True), r, 0)
            form.addWidget(widget, r, 1)
        body.addWidget(form_card, 3)

        info_card = make_card()
        info = QtWidgets.QVBoxLayout(info_card)
        info.setContentsMargins(24, 20, 24, 20)
        info.addWidget(make_label("Ideal body weight (IBW)", 18, muted=True))
        self._ibw = make_label("", 56, bold=True)
        self._formula = make_label("", 14, muted=True)
        info.addWidget(self._ibw)
        info.addWidget(self._formula)
        info.addSpacing(18)
        info.addWidget(make_label("Suggested tidal volume (6–8 mL/kg IBW)", 18, muted=True))
        self._vt = make_label("", 34, bold=True)
        self._vt_note = make_label("", 14, muted=True)
        info.addWidget(self._vt)
        info.addWidget(self._vt_note)
        info.addStretch(1)
        body.addWidget(info_card, 2)
        root.addLayout(body, 1)

        footer = QtWidgets.QHBoxLayout()
        footer.addStretch(1)
        next_button = make_button("Next  →", "primary")
        next_button.setMinimumWidth(220)
        next_button.clicked.connect(self.next_requested.emit)
        footer.addWidget(next_button)
        root.addLayout(footer)

        self.category.changed.connect(self._on_category)
        self.sex.changed.connect(lambda key: self._update(sex=Sex(key)))
        self.height_adjuster.changed.connect(lambda value: self._update(height_cm=int(value)))
        self._name_button.clicked.connect(self._edit_name)
        self._id_button.clicked.connect(self._edit_id)
        self._age_button.clicked.connect(self._edit_age)
        self._refresh()

    def profile(self) -> PatientProfile:
        return self._profile

    def set_profile(self, profile: PatientProfile) -> None:
        self._profile = profile
        self.category.set_value(profile.category.value)
        self.sex.set_value(profile.sex.value)
        self.height_adjuster.set_spec(height_spec(profile.category), profile.height_cm)
        self._refresh()

    def ibw_text(self) -> str:
        return self._ibw.text()

    def _update(self, **changes) -> None:
        self._profile = replace(self._profile, **changes)
        self._refresh()

    def _on_category(self, key: str) -> None:
        category = Category(key)
        height = DEFAULT_HEIGHT[category]
        self.height_adjuster.set_spec(height_spec(category), height)
        self._update(category=category, height_cm=height)

    def _edit_name(self) -> None:
        text = KeyboardDialog.ask(self, "Patient name", self._profile.name)
        if text is not None:
            self._update(name=text)

    def _edit_id(self) -> None:
        text = KeyboardDialog.ask(self, "Patient ID", self._profile.patient_id)
        if text is not None:
            self._update(patient_id=text)

    def _edit_age(self) -> None:
        start = self._profile.age_years
        if start is None:
            start = 40 if self._profile.category is Category.ADULT else 8
        value = ValueAdjustDialog.ask(self, AGE_SPEC, start, title="Age")
        if value is not None:
            self._update(age_years=int(value))

    def _refresh(self) -> None:
        p = self._profile
        self._ibw.setText(f"{p.ibw_kg:.1f} kg")
        self._formula.setText(p.ibw_formula_text())
        low, high = p.suggested_vt_range()
        self._vt.setText(f"{low}–{high} mL")
        self._vt_note.setText(f"Default VT = 7 mL/kg IBW = {p.default_vt():.0f} mL")
        self._name_button.setText(p.name or "Tap to enter (optional)")
        self._id_button.setText(p.patient_id or "Tap to enter (optional)")
        self._age_button.setText(f"{p.age_years} years" if p.age_years is not None else "Tap to set (optional)")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_screens.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add hmi/ui/screens tests/test_screens.py
git commit -m "Add Patient Profile screen with live IBW"
```

---

### Task 15: Pre-Use Check screen

**Files:**
- Create: `hmi/ui/screens/precheck.py`
- Test: append to `tests/test_screens.py`

**Interfaces:**
- Consumes: `DeviceLink` (`run_test`, `test_finished`), `TestResult`, `ConfirmDialog`, theme
- Produces: `CHECKS`, status constants `PENDING, RUNNING, PASSED, FAILED`; `CheckRow` (`status`, `retry_button`, `set_status(status, detail="")`, `detail_text()`);
  `PrecheckScreen(device)` signals `back_requested`, `continue_requested`, `skip_requested`, `check_finished(str, bool, str)`; attributes `rows: dict[str, CheckRow]`, `run_button`, `continue_button`; methods `reset()`, `run_all()`, `retry(key)`, `all_passed()`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_screens.py`:

```python
import pytest

from hmi.device.simulator import SimulatedDevice
from hmi.ui.dialogs.confirm import ConfirmDialog
from hmi.ui.screens.precheck import FAILED, PASSED, PENDING, PrecheckScreen


@pytest.fixture
def always_confirm(monkeypatch):
    monkeypatch.setattr(ConfirmDialog, "ask", staticmethod(lambda *a, **k: True))


def tick(device, seconds):
    for _ in range(int(seconds / 0.02)):
        device.tick()


def test_precheck_runs_all_four_tests(qapp, always_confirm):
    device = SimulatedDevice(seed=2, sound=False)
    screen = PrecheckScreen(device)
    assert not screen.continue_button.isEnabled()
    screen.run_all()
    tick(device, 16)
    assert screen.all_passed() and screen.continue_button.isEnabled()
    assert "alarm confirmed" in screen.rows["CAL"].detail_text()


def test_precheck_stops_at_first_failure_and_offers_retry(qapp, always_confirm):
    device = SimulatedDevice(seed=2, sound=False)
    screen = PrecheckScreen(device)
    device.force_fail = "LEAK"
    screen.run_all()
    tick(device, 16)
    assert screen.rows["SELF"].status == PASSED
    assert screen.rows["LEAK"].status == FAILED and not screen.rows["LEAK"].retry_button.isHidden()
    assert screen.rows["COMP"].status == PENDING
    device.force_fail = None
    screen.retry("LEAK")
    tick(device, 4)
    assert screen.rows["LEAK"].status == PASSED


def test_operator_not_hearing_alarm_fails_the_test(qapp, monkeypatch):
    answers = iter([True, True, False])  # block Y-piece, unblock Y-piece, alarm "Not heard"
    monkeypatch.setattr(ConfirmDialog, "ask", staticmethod(lambda *a, **k: next(answers, True)))
    device = SimulatedDevice(seed=2, sound=False)
    screen = PrecheckScreen(device)
    screen.run_all()
    tick(device, 16)
    assert screen.rows["CAL"].status == FAILED
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_screens.py -v`
Expected: the 3 new tests FAIL with `ModuleNotFoundError: No module named 'hmi.ui.screens.precheck'`

- [ ] **Step 3: Implement**

`hmi/ui/screens/precheck.py`:
```python
"""Screen 2 — Pre-Use Check (ISO 80601-2-12 asks for a documented pre-use check).

Four tests run in order: system self-test, circuit leak test, circuit compliance & resistance, and
sensor calibration + alarm test. The operator is prompted to block/unblock the patient Y-piece
when needed, and must confirm hearing and seeing the alarm. The sequence stops at the first
failure; each failed test can be retried. Continue is enabled only when all tests pass.
"""
from __future__ import annotations

from hmi.core.alarms.definitions import Priority
from hmi.device.base import DeviceLink
from hmi.device.messages import TestResult
from hmi.qt import QtCore, QtWidgets, Signal
from hmi.ui.dialogs.confirm import ConfirmDialog
from hmi.ui.theme import ADVISORY, ALARM_COLORS, ALARM_TEXT, MUTED, PRIMARY, make_button, make_label

CHECKS = (
    ("SELF", "System self-test", "MCU link · sensors · valves · battery at least 20 %"),
    ("LEAK", "Circuit leak test", "Leak < 200 mL/min with the Y-piece blocked"),
    ("COMP", "Circuit compliance & resistance", "C 0.5–5.0 mL/cmH2O · R < 6 cmH2O/(L/s)"),
    ("CAL", "Sensor calibration + alarm test", "O2 21 ± 2 % on air · flow zero < 0.5 L/min · alarm heard and seen"),
)
PENDING, RUNNING, PASSED, FAILED = "pending", "running", "passed", "failed"
STATUS_LOOK = {PENDING: ("Pending", MUTED), RUNNING: ("Running…", PRIMARY),
               PASSED: ("✔ Pass", "#3fcf7a"), FAILED: ("✖ Fail", ADVISORY)}
RESULT_TIMEOUT_MS = 10000
FLASH_MS = 250  # 2 Hz, like a high-priority alarm


class CheckRow(QtWidgets.QFrame):
    def __init__(self, number: int, title: str, criterion: str):
        super().__init__()
        self.setObjectName("card")
        grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(16, 10, 16, 10)
        grid.setHorizontalSpacing(16)
        grid.addWidget(make_label(str(number), 26, bold=True, muted=True), 0, 0, 2, 1)
        grid.addWidget(make_label(title, 20, bold=True), 0, 1)
        grid.addWidget(make_label(criterion, 14, muted=True), 1, 1)
        self._status = make_label("", 18, bold=True)
        self._status.setFixedWidth(130)
        self._detail = make_label("", 15)
        self._detail.setWordWrap(True)
        self._detail.setMinimumWidth(380)
        self.retry_button = make_button("Retry")
        self.retry_button.setFixedWidth(110)
        grid.addWidget(self._status, 0, 2, 2, 1)
        grid.addWidget(self._detail, 0, 3, 2, 1)
        grid.addWidget(self.retry_button, 0, 4, 2, 1)
        grid.setColumnStretch(3, 1)
        self.status = PENDING
        self.set_status(PENDING)

    def set_status(self, status: str, detail: str = "") -> None:
        self.status = status
        text, color = STATUS_LOOK[status]
        self._status.setText(text)
        self._status.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {color};")
        self._detail.setText(detail)
        self.retry_button.setVisible(status == FAILED)

    def detail_text(self) -> str:
        return self._detail.text()


class PrecheckScreen(QtWidgets.QWidget):
    back_requested = Signal()
    continue_requested = Signal()
    skip_requested = Signal()
    check_finished = Signal(str, bool, str)

    def __init__(self, device: DeviceLink):
        super().__init__()
        self._device = device
        device.test_finished.connect(self._on_result)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(12)
        root.addWidget(make_label("Pre-use check", 28, bold=True))
        root.addWidget(make_label("Run before connecting a patient (ISO 80601-2-12).", 15, muted=True))

        self._flash = make_label("ALARM TEST — listen for the buzzer and watch this bar", 20, bold=True)
        self._flash.setMinimumHeight(48)
        self._flash.hide()
        root.addWidget(self._flash)
        self._flash_on = False
        self._flash_timer = QtCore.QTimer(self)
        self._flash_timer.timeout.connect(self._toggle_flash)

        self.rows: dict[str, CheckRow] = {}
        for number, (key, title, criterion) in enumerate(CHECKS, start=1):
            row = CheckRow(number, title, criterion)
            row.retry_button.clicked.connect(lambda _checked=False, k=key: self.retry(k))
            self.rows[key] = row
            root.addWidget(row)
        root.addStretch(1)

        footer = QtWidgets.QHBoxLayout()
        back = make_button("←  Back")
        back.setMinimumWidth(160)
        back.clicked.connect(self.back_requested.emit)
        skip = make_button("Skip check", "danger")
        skip.setMinimumWidth(180)
        skip.clicked.connect(self.skip_requested.emit)
        self.run_button = make_button("Run all", "primary")
        self.run_button.setMinimumWidth(180)
        self.run_button.clicked.connect(self.run_all)
        self.continue_button = make_button("Continue  →", "go")
        self.continue_button.setMinimumWidth(220)
        self.continue_button.clicked.connect(self.continue_requested.emit)
        for widget in (back, skip):
            footer.addWidget(widget)
        footer.addStretch(1)
        footer.addWidget(self.run_button)
        footer.addWidget(self.continue_button)
        root.addLayout(footer)

        self._queue: list[str] = []
        self._running: str | None = None
        self._y_blocked = False
        self._cal_detail = ""
        self._timeout = QtCore.QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.timeout.connect(self._on_timeout)
        self._update_buttons()

    # ----- public --------------------------------------------------------------------------------
    def reset(self) -> None:
        for row in self.rows.values():
            row.set_status(PENDING)
        self._queue.clear()
        self._running = None
        self._y_blocked = False
        self._timeout.stop()
        self._stop_flash()
        self._update_buttons()

    def all_passed(self) -> bool:
        return all(row.status == PASSED for row in self.rows.values())

    def run_all(self) -> None:
        if self._running:
            return
        self._queue = [key for key, row in self.rows.items() if row.status != PASSED]
        self._next()

    def retry(self, key: str) -> None:
        if self._running:
            return
        self._queue = [key]
        self._next()

    # ----- sequence ------------------------------------------------------------------------------
    def _next(self) -> None:
        self._update_buttons()
        if self._running or not self._queue:
            return
        key = self._queue.pop(0)
        if not self._prepare(key):
            self._queue.clear()
            self._update_buttons()
            return
        self._start(key, key)

    def _prepare(self, key: str) -> bool:
        """Ask the operator to block or unblock the Y-piece when the next test needs it."""
        if key in ("LEAK", "COMP") and not self._y_blocked:
            if not ConfirmDialog.ask(self, "Block the Y-piece",
                                     "Block the patient Y-piece with the test plug, then tap Start.\n"
                                     "Keep it blocked for the leak and compliance tests.", confirm_text="Start"):
                return False
            self._y_blocked = True
        elif key in ("SELF", "CAL") and self._y_blocked:
            if not ConfirmDialog.ask(self, "Unblock the Y-piece",
                                     "Remove the test plug so the circuit is open to room air, then tap Start.",
                                     confirm_text="Start"):
                return False
            self._y_blocked = False
        return True

    def _start(self, key: str, test: str) -> None:
        self._running = test
        detail = f"{self._cal_detail} · alarm test…" if test == "ALARM" else ""
        self.rows[key].set_status(RUNNING, detail)
        if test == "ALARM":
            self._start_flash()
        self._timeout.start(RESULT_TIMEOUT_MS)
        self._update_buttons()
        self._device.run_test(test)

    def _on_result(self, result: TestResult) -> None:
        if result.test != self._running:
            return
        self._timeout.stop()
        self._running = None
        if result.test == "CAL":
            if result.passed:
                self._cal_detail = result.detail
                self._start("CAL", "ALARM")
            else:
                self._finish("CAL", False, result.detail)
            return
        if result.test == "ALARM":
            self._stop_flash()
            if not result.passed:
                self._finish("CAL", False, result.detail)
                return
            heard = ConfirmDialog.ask(self, "Alarm test",
                                      "Did you hear the alarm buzzer and see the red bar flashing?",
                                      confirm_text="I heard and saw it", role="go", cancel_text="Not heard")
            self._finish("CAL", heard, f"{self._cal_detail} · alarm {'confirmed' if heard else 'NOT confirmed'}")
            return
        self._finish(result.test, result.passed, result.detail)

    def _on_timeout(self) -> None:
        test = self._running
        self._running = None
        self._stop_flash()
        self._finish("CAL" if test in ("CAL", "ALARM") else test, False, "No response from the device")

    def _finish(self, key: str, passed: bool, detail: str) -> None:
        self.rows[key].set_status(PASSED if passed else FAILED, detail)
        self.check_finished.emit(key, passed, detail)
        if not passed:
            self._queue.clear()
        self._next()

    def _update_buttons(self) -> None:
        idle = self._running is None
        self.run_button.setEnabled(idle and not self.all_passed())
        self.continue_button.setEnabled(idle and self.all_passed())
        for row in self.rows.values():
            row.retry_button.setEnabled(idle)

    # ----- alarm-test flashing bar ---------------------------------------------------------------
    def _start_flash(self) -> None:
        self._flash.show()
        self._flash_on = False
        self._toggle_flash()
        self._flash_timer.start(FLASH_MS)

    def _stop_flash(self) -> None:
        self._flash_timer.stop()
        self._flash.hide()

    def _toggle_flash(self) -> None:
        self._flash_on = not self._flash_on
        red = ALARM_COLORS[Priority.HIGH]
        if self._flash_on:
            style = f"background: {red}; color: {ALARM_TEXT[Priority.HIGH]};"
        else:
            style = f"background: transparent; color: {red}; border: 2px solid {red};"
        self._flash.setStyleSheet(f"font-size: 20px; font-weight: 700; padding: 8px; border-radius: 8px; {style}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_screens.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add hmi/ui/screens/precheck.py tests/test_screens.py
git commit -m "Add Pre-Use Check screen with Y-piece prompts and alarm test"
```

---

### Task 16: Settings screen, alarm limits panel and setting editors

**Files:**
- Create: `hmi/ui/setting_edit.py`, `hmi/ui/widgets/alarm_limits_panel.py`, `hmi/ui/screens/settings.py`
- Test: append to `tests/test_screens.py`

**Interfaces:**
- Consumes: settings/limits models, `ValueAdjustDialog`, `ConfirmDialog`, `ParamTile`, `ToggleGroup`
- Produces:
  - `edit_setting(parent, patient, settings, limits, key)->VentSettings|None`, `edit_limit(parent, patient, settings, limits, key)->AlarmLimits|None`
  - `AlarmLimitsPanel()` signal `limit_changed(str, float, float)`; `tiles: dict[str, ParamTile]`; `load(patient, settings, limits)`, `set_settings(settings)`, `limits()`
  - `SettingsScreen()` signals `back_requested`, `start_requested`, `setting_changed(str, object, object)`, `limit_changed(str, float, float)`; attributes `mode` (ToggleGroup), `tiles`, `limits_panel`, `start_button`; methods `load(patient, settings, limits)`, `settings()`, `limits()`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_screens.py`:

```python
from hmi.model.alarm_limits import AlarmLimits
from hmi.model.settings import Mode, VentSettings
from hmi.ui.dialogs.value_adjust import ValueAdjustDialog
from hmi.ui.screens.settings import SettingsScreen

ADULT = PatientProfile(height_cm=170)


def load_settings_screen():
    screen = SettingsScreen()
    screen.load(ADULT, VentSettings.defaults_for(ADULT), AlarmLimits.defaults_for(ADULT))
    return screen


def test_mode_switch_swaps_vt_for_pinsp(qapp):
    screen = load_settings_screen()
    seen = []
    screen.setting_changed.connect(lambda *args: seen.append(args))
    assert not screen.tiles["vt"].isHidden() and screen.tiles["pinsp"].isHidden()
    screen.mode.button("PC").click()
    assert screen.tiles["vt"].isHidden() and not screen.tiles["pinsp"].isHidden()
    assert screen.settings().mode is Mode.PC and seen == [("mode", "VC", "PC")]


def test_editing_vt_shows_advisory(qapp, monkeypatch):
    monkeypatch.setattr(ValueAdjustDialog, "ask", staticmethod(lambda *a, **k: 700))
    screen = load_settings_screen()
    screen.tiles["vt"].click()
    assert screen.settings().vt == 700
    assert "mL/kg" in screen.tiles["vt"].note_text()


def test_editing_a_limit_updates_panel(qapp, monkeypatch):
    monkeypatch.setattr(ValueAdjustDialog, "ask", staticmethod(lambda *a, **k: 45))
    screen = load_settings_screen()
    seen = []
    screen.limit_changed.connect(lambda *args: seen.append(args))
    screen.limits_panel.tiles["ppeak_high"].click()
    assert screen.limits().ppeak_high == 45 and seen == [("ppeak_high", 40, 45)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_screens.py -v`
Expected: the 3 new tests FAIL with `ModuleNotFoundError: No module named 'hmi.ui.screens.settings'`

- [ ] **Step 3: Implement the setting editors**

`hmi/ui/setting_edit.py`:
```python
"""Open the adjuster for one setting or alarm limit, with the safety cross-checks as validator.

Used by the Settings screen, the Monitoring bottom bar and the Alarms dialog, so every change goes
through the same checks.
"""
from __future__ import annotations

from hmi.model.alarm_limits import AlarmLimits, limit_spec, validate_limits
from hmi.model.patient import PatientProfile
from hmi.model.settings import VentSettings, param_spec, validate_settings
from hmi.ui.dialogs.value_adjust import ValueAdjustDialog


def edit_setting(parent, patient: PatientProfile, settings: VentSettings, limits: AlarmLimits,
                 key: str) -> VentSettings | None:
    spec = param_spec(patient.category, key)

    def validator(value: float) -> str | None:
        errors = validate_settings(settings.with_value(key, value), patient.category, limits.ppeak_high)
        return errors[0] if errors else None

    hint = ""
    if key == "vt":
        low, high = patient.suggested_vt_range()
        hint = f"Lung-protective range for IBW {patient.ibw_kg:.1f} kg: {low}–{high} mL (6–8 mL/kg)"
    value = ValueAdjustDialog.ask(parent, spec, settings.get(key), validator=validator, hint=hint)
    if value is None or value == settings.get(key):
        return None
    return settings.with_value(key, value)


def edit_limit(parent, patient: PatientProfile, settings: VentSettings, limits: AlarmLimits,
               key: str) -> AlarmLimits | None:
    spec = limit_spec(patient.category, key)

    def validator(value: float) -> str | None:
        candidate = limits.with_value(key, value)
        errors = validate_limits(candidate) + validate_settings(settings, patient.category, candidate.ppeak_high)
        return errors[0] if errors else None

    value = ValueAdjustDialog.ask(parent, spec, limits.get(key), title=f"Alarm limit: {spec.label}",
                                  validator=validator)
    if value is None or value == limits.get(key):
        return None
    return limits.with_value(key, value)
```

- [ ] **Step 4: Implement the alarm limits panel**

`hmi/ui/widgets/alarm_limits_panel.py`:
```python
"""AlarmLimitsPanel: tiles for every adjustable alarm limit, plus the automatic FiO2/PEEP limits.

Used on the Settings screen (Alarm limits tab) and in the Alarms dialog (Limits tab).
"""
from __future__ import annotations

from hmi.model.alarm_limits import LIMIT_KEYS, AlarmLimits, fio2_limits, limit_spec, peep_limits
from hmi.model.patient import PatientProfile
from hmi.model.settings import VentSettings
from hmi.qt import QtWidgets, Signal
from hmi.ui.dialogs.confirm import ConfirmDialog
from hmi.ui.setting_edit import edit_limit
from hmi.ui.theme import make_button, make_label
from hmi.ui.widgets.param_tile import ParamTile

COLUMNS = (("ppeak_high", "ppeak_low"), ("vte_high", "vte_low"), ("mve_high", "mve_low"), ("rr_high", "apnea_time"))


class AlarmLimitsPanel(QtWidgets.QWidget):
    limit_changed = Signal(str, float, float)

    def __init__(self):
        super().__init__()
        self._patient = PatientProfile()
        self._settings = VentSettings.defaults_for(self._patient)
        self._limits = AlarmLimits.defaults_for(self._patient)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 12, 0, 0)
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(12)
        self.tiles: dict[str, ParamTile] = {}
        for col, keys in enumerate(COLUMNS):
            for row, key in enumerate(keys):
                tile = ParamTile("", "")
                tile.clicked.connect(lambda _checked=False, k=key: self._edit(k))
                self.tiles[key] = tile
                grid.addWidget(tile, row, col)
        root.addLayout(grid)
        self._auto = make_label("", 15, muted=True)
        self._auto.setWordWrap(True)
        root.addWidget(self._auto)
        footer = QtWidgets.QHBoxLayout()
        footer.addStretch(1)
        restore = make_button("Restore defaults")
        restore.clicked.connect(self._restore)
        footer.addWidget(restore)
        root.addLayout(footer)
        root.addStretch(1)
        self._refresh()

    def load(self, patient: PatientProfile, settings: VentSettings, limits: AlarmLimits) -> None:
        self._patient, self._settings, self._limits = patient, settings, limits
        self._refresh()

    def set_settings(self, settings: VentSettings) -> None:
        self._settings = settings
        self._refresh()

    def limits(self) -> AlarmLimits:
        return self._limits

    def _edit(self, key: str) -> None:
        new = edit_limit(self, self._patient, self._settings, self._limits, key)
        if new is None:
            return
        old = self._limits.get(key)
        self._limits = new
        self._refresh()
        self.limit_changed.emit(key, old, new.get(key))

    def _restore(self) -> None:
        defaults = AlarmLimits.defaults_for(self._patient)
        if defaults == self._limits:
            return
        if not ConfirmDialog.ask(self, "Restore defaults",
                                 "Reset every alarm limit to the default for this patient?", confirm_text="Restore"):
            return
        old = self._limits
        self._limits = defaults
        self._refresh()
        for key in LIMIT_KEYS:
            if old.get(key) != defaults.get(key):
                self.limit_changed.emit(key, old.get(key), defaults.get(key))

    def _refresh(self) -> None:
        for key, tile in self.tiles.items():
            spec = limit_spec(self._patient.category, key)
            tile.set_title(spec.label)
            tile.set_unit(spec.unit)
            tile.set_value(spec.fmt(self._limits.get(key)))
        f_low, f_high = fio2_limits(self._settings.fio2)
        p_low, p_high = peep_limits(self._settings.peep)
        self._auto.setText(f"Automatic limits (follow the settings):  FiO2 {f_low:.0f}–{f_high:.0f} %   ·   "
                           f"PEEP {p_low:.0f}–{p_high:.0f} cmH2O")
```

- [ ] **Step 5: Implement the Settings screen**

`hmi/ui/screens/settings.py`:
```python
"""Screen 3 — Settings (before ventilation, and after Standby).

Ventilation tab: mode (VC/PC) and parameter tiles; each tile opens the adjuster with safety
cross-checks. Tiles outside the lung-protective range get an orange advisory. Alarm limits tab:
the adjustable limits. Start Ventilation asks for confirmation (handled by the main window).
"""
from __future__ import annotations

from hmi.model.alarm_limits import AlarmLimits
from hmi.model.patient import Category, PatientProfile
from hmi.model.settings import MODE_PARAMS, PARAM_KEYS, Mode, VentSettings, advisories, param_spec
from hmi.qt import QtWidgets, Signal
from hmi.ui.setting_edit import edit_setting
from hmi.ui.theme import make_button, make_card, make_label
from hmi.ui.widgets.alarm_limits_panel import AlarmLimitsPanel
from hmi.ui.widgets.param_tile import ParamTile
from hmi.ui.widgets.toggle_group import ToggleGroup

TILE_POSITIONS = {"vt": (0, 0), "pinsp": (0, 0), "rr": (0, 1), "peep": (0, 2),
                  "fio2": (1, 0), "ti": (1, 1), "trigger": (1, 2)}


class SettingsScreen(QtWidgets.QWidget):
    back_requested = Signal()
    start_requested = Signal()
    setting_changed = Signal(str, object, object)
    limit_changed = Signal(str, float, float)

    def __init__(self):
        super().__init__()
        self._patient = PatientProfile()
        self._settings = VentSettings.defaults_for(self._patient)
        self._limits = AlarmLimits.defaults_for(self._patient)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(10)
        header = QtWidgets.QHBoxLayout()
        header.addWidget(make_label("Settings", 28, bold=True))
        header.addStretch(1)
        self._subtitle = make_label("", 16, muted=True)
        header.addWidget(self._subtitle)
        root.addLayout(header)

        self.tabs = QtWidgets.QTabWidget()
        vent = QtWidgets.QWidget()
        vent_layout = QtWidgets.QVBoxLayout(vent)
        vent_layout.setContentsMargins(0, 12, 0, 0)
        mode_row = QtWidgets.QHBoxLayout()
        mode_row.addWidget(make_label("Mode", 17, muted=True))
        self.mode = ToggleGroup([("VC", "VC · Volume Control"), ("PC", "PC · Pressure Control")], "VC", min_width=280)
        mode_row.addWidget(self.mode, 1)
        vent_layout.addLayout(mode_row)
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(12)
        self.tiles: dict[str, ParamTile] = {}
        adult_specs = {key: param_spec(Category.ADULT, key) for key in PARAM_KEYS}
        for key in PARAM_KEYS:
            tile = ParamTile(adult_specs[key].label, adult_specs[key].unit)
            tile.clicked.connect(lambda _checked=False, k=key: self._edit(k))
            self.tiles[key] = tile
            grid.addWidget(tile, *TILE_POSITIONS[key])
        vent_layout.addLayout(grid)
        info_card = make_card()
        info_layout = QtWidgets.QHBoxLayout(info_card)
        self._info = make_label("", 17)
        info_layout.addWidget(self._info)
        vent_layout.addWidget(info_card)
        vent_layout.addStretch(1)
        self.tabs.addTab(vent, "Ventilation")
        self.limits_panel = AlarmLimitsPanel()
        self.tabs.addTab(self.limits_panel, "Alarm limits")
        root.addWidget(self.tabs, 1)

        footer = QtWidgets.QHBoxLayout()
        back = make_button("←  Back")
        back.setMinimumWidth(160)
        back.clicked.connect(self.back_requested.emit)
        footer.addWidget(back)
        footer.addStretch(1)
        self.start_button = make_button("Start ventilation", "go")
        self.start_button.setMinimumWidth(320)
        self.start_button.clicked.connect(self.start_requested.emit)
        footer.addWidget(self.start_button)
        root.addLayout(footer)

        self.mode.changed.connect(self._on_mode)
        self.limits_panel.limit_changed.connect(self._on_limit_changed)
        self._refresh()

    def load(self, patient: PatientProfile, settings: VentSettings, limits: AlarmLimits) -> None:
        self._patient, self._settings, self._limits = patient, settings, limits
        self.mode.set_value(settings.mode.value)
        self.limits_panel.load(patient, settings, limits)
        self._refresh()

    def settings(self) -> VentSettings:
        return self._settings

    def limits(self) -> AlarmLimits:
        return self._limits

    def _on_mode(self, key: str) -> None:
        old = self._settings.mode
        self._settings = self._settings.with_mode(Mode(key))
        self.limits_panel.set_settings(self._settings)
        self._refresh()
        self.setting_changed.emit("mode", old.value, key)

    def _edit(self, key: str) -> None:
        new = edit_setting(self, self._patient, self._settings, self._limits, key)
        if new is None:
            return
        old = self._settings.get(key)
        self._settings = new
        self.limits_panel.set_settings(new)
        self._refresh()
        self.setting_changed.emit(key, old, new.get(key))

    def _on_limit_changed(self, key: str, old: float, new: float) -> None:
        self._limits = self.limits_panel.limits()
        self.limit_changed.emit(key, old, new)

    def _refresh(self) -> None:
        s, p = self._settings, self._patient
        notes = advisories(s, p)
        visible = MODE_PARAMS[s.mode]
        for key, tile in self.tiles.items():
            spec = param_spec(p.category, key)
            tile.setHidden(key not in visible)
            tile.set_value(spec.fmt(s.get(key)))
            tile.set_note(notes.get(key))
        parts = [f"I:E {s.ie_text}"]
        if s.mode is Mode.VC:
            parts += [f"Inspiratory flow {s.inspiratory_flow_lpm:.0f} L/min", f"VT {s.vt / p.ibw_kg:.1f} mL/kg IBW"]
        else:
            parts.append(f"Inspiratory pressure {s.peep + s.pinsp:.0f} cmH2O (PEEP + Pinsp)")
        self._info.setText("     ·     ".join(parts))
        self._subtitle.setText(p.summary())
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_screens.py -v`
Expected: 9 passed

- [ ] **Step 7: Commit**

```bash
git add hmi/ui/setting_edit.py hmi/ui/widgets/alarm_limits_panel.py hmi/ui/screens/settings.py tests/test_screens.py
git commit -m "Add Settings screen with alarm limits panel and validated editors"
```

---

### Task 17: Monitoring screen

**Files:**
- Create: `hmi/ui/screens/monitoring.py`
- Test: append to `tests/test_screens.py`

**Interfaces:**
- Consumes: `WaveformPanel`, `NumericReadout`, `ParamTile`, `BreathResult`, limits helpers, `Priority`
- Produces: `MonitoringScreen()` signals `edit_setting_requested(str)`, `modes_requested`, `alarms_requested`, `standby_requested`; attributes `waveforms`, `readouts: dict[str, NumericReadout]`, `tiles: dict[str, ParamTile]`; methods `load(patient, settings, limits)`, `add_sample(s)`, `show_breath(r)`, `show_fio2(v)`, `show_alarm_colors(priorities)`, `reset_values()`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_screens.py`:

```python
from hmi.core.alarms.definitions import Priority
from hmi.core.breath_analyzer import BreathResult
from hmi.ui.screens.monitoring import MonitoringScreen


def test_monitoring_shows_breath_values_and_alarm_colors(qapp):
    screen = MonitoringScreen()
    screen.load(ADULT, VentSettings.defaults_for(ADULT), AlarmLimits.defaults_for(ADULT))
    screen.show_breath(BreathResult(0, 20.4, 5.02, 9.6, 460, 455, 1.0, 3.3, 14.0, 6.37))
    assert screen.readouts["pip"].value_text() == "20"
    assert screen.readouts["vte"].value_text() == "455"
    assert screen.readouts["ie"].value_text() == "1:3.3"
    screen.show_alarm_colors({"pip": Priority.HIGH})
    assert screen.readouts["pip"].alarm_priority is Priority.HIGH
    assert screen.readouts["vte"].alarm_priority is Priority.NONE
    screen.reset_values()
    assert screen.readouts["pip"].value_text() == "--"


def test_monitoring_bottom_bar_follows_mode(qapp):
    screen = MonitoringScreen()
    screen.load(ADULT, VentSettings.defaults_for(ADULT).with_mode(Mode.PC), AlarmLimits.defaults_for(ADULT))
    assert screen.tiles["vt"].isHidden() and not screen.tiles["pinsp"].isHidden()
    seen = []
    screen.edit_setting_requested.connect(seen.append)
    screen.tiles["rr"].click()
    assert seen == ["rr"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_screens.py -v`
Expected: the 2 new tests FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

`hmi/ui/screens/monitoring.py`:
```python
"""Screen 4 — Monitoring (ventilating).

Left: live pressure/flow/volume waveforms. Right: measured values with their alarm limits; a value
takes the alarm color while its alarm is active. Bottom: the current settings (tap to change, with
confirmation) and the MODES, ALARMS and STANDBY buttons.
"""
from __future__ import annotations

from hmi.core.alarms.definitions import Priority
from hmi.core.breath_analyzer import BreathResult
from hmi.device.messages import Sample
from hmi.model.alarm_limits import AlarmLimits, fio2_limits, peep_limits
from hmi.model.patient import Category, PatientProfile
from hmi.model.settings import MODE_PARAMS, PARAM_KEYS, VentSettings, param_spec
from hmi.qt import QtWidgets, Signal
from hmi.ui.theme import TEXT, WAVE_COLORS, make_button
from hmi.ui.widgets.numeric_readout import NumericReadout
from hmi.ui.widgets.param_tile import ParamTile
from hmi.ui.widgets.waveform_panel import WaveformPanel

READOUTS = (
    ("pip", "PIP", "cmH2O", WAVE_COLORS["pressure"]), ("peep", "PEEP", "cmH2O", WAVE_COLORS["pressure"]),
    ("pmean", "Pmean", "cmH2O", WAVE_COLORS["pressure"]), ("vte", "Vte", "mL", WAVE_COLORS["volume"]),
    ("mve", "MVe", "L/min", WAVE_COLORS["volume"]), ("rr", "RR", "bpm", TEXT),
    ("fio2", "FiO2", "%", TEXT), ("ie", "I:E", "", TEXT),
)


class MonitoringScreen(QtWidgets.QWidget):
    edit_setting_requested = Signal(str)
    modes_requested = Signal()
    alarms_requested = Signal()
    standby_requested = Signal()

    def __init__(self):
        super().__init__()
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)

        body = QtWidgets.QHBoxLayout()
        self.waveforms = WaveformPanel()
        body.addWidget(self.waveforms, 1)
        readout_box = QtWidgets.QWidget()
        readout_box.setFixedWidth(400)
        grid = QtWidgets.QGridLayout(readout_box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        self.readouts: dict[str, NumericReadout] = {}
        for i, (key, title, unit, accent) in enumerate(READOUTS):
            readout = NumericReadout(title, unit, accent)
            self.readouts[key] = readout
            grid.addWidget(readout, i // 2, i % 2)
        body.addWidget(readout_box)
        root.addLayout(body, 1)

        bar = QtWidgets.QHBoxLayout()
        bar.setSpacing(8)
        self.tiles: dict[str, ParamTile] = {}
        for key in PARAM_KEYS:
            spec = param_spec(Category.ADULT, key)
            tile = ParamTile(spec.label, spec.unit, compact=True)
            tile.clicked.connect(lambda _checked=False, k=key: self.edit_setting_requested.emit(k))
            self.tiles[key] = tile
            bar.addWidget(tile)
        bar.addStretch(1)
        for text, role, signal in (("Modes", None, self.modes_requested), ("Alarms", None, self.alarms_requested),
                                   ("Standby", "danger", self.standby_requested)):
            button = make_button(text, role)
            button.setFixedSize(122, 84)
            button.clicked.connect(signal.emit)
            bar.addWidget(button)
        root.addLayout(bar)

    def load(self, patient: PatientProfile, settings: VentSettings, limits: AlarmLimits) -> None:
        self.waveforms.set_category(patient.category)
        visible = MODE_PARAMS[settings.mode]
        for key, tile in self.tiles.items():
            spec = param_spec(patient.category, key)
            tile.setHidden(key not in visible)
            tile.set_value(spec.fmt(settings.get(key)))
        r = self.readouts
        r["pip"].set_limits(limits.ppeak_low, limits.ppeak_high)
        r["peep"].set_limits(*peep_limits(settings.peep))
        r["vte"].set_limits(limits.vte_low, limits.vte_high)
        r["mve"].set_limits(limits.mve_low, limits.mve_high)
        r["rr"].set_limits(None, limits.rr_high)
        r["fio2"].set_limits(*fio2_limits(settings.fio2))

    def add_sample(self, s: Sample) -> None:
        self.waveforms.add_sample(s)

    def show_breath(self, b: BreathResult) -> None:
        values = {"pip": f"{b.pip:.0f}", "peep": f"{b.peep:.1f}", "pmean": f"{b.pmean:.0f}", "vte": f"{b.vte:.0f}",
                  "mve": f"{b.mve:.1f}", "rr": f"{b.rr:.0f}", "ie": b.ie_text}
        for key, text in values.items():
            self.readouts[key].set_value(text)

    def show_fio2(self, fio2: float) -> None:
        self.readouts["fio2"].set_value(f"{fio2:.0f}")

    def show_alarm_colors(self, priorities: dict[str, Priority]) -> None:
        for key, readout in self.readouts.items():
            readout.set_alarm(priorities.get(key, Priority.NONE))

    def reset_values(self) -> None:
        for readout in self.readouts.values():
            readout.set_value("--")
            readout.set_alarm(Priority.NONE)
        self.waveforms.clear()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_screens.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add hmi/ui/screens/monitoring.py tests/test_screens.py
git commit -m "Add Monitoring screen with waveforms, readouts and settings bar"
```

---

### Task 18: Modes, Alarms and Demo Panel dialogs

**Files:**
- Create: `hmi/ui/dialogs/modes.py`, `hmi/ui/dialogs/alarms.py`, `hmi/ui/dialogs/demo_panel.py`
- Test: `tests/test_dialogs.py`

**Interfaces:**
- Consumes: `Mode`, `AlarmEngine`, `EventLog`, `describe`, `AlarmLimitsPanel`, `SimulatedDevice`, theme
- Produces:
  - `ModesDialog(parent, current)` with `.buttons: dict[Mode, QPushButton]`, `.selected`; static `ask(parent, current)->Mode|None`
  - `AlarmsDialog(parent, engine, log, patient, settings, limits, clock)` signals `limit_changed(str, float, float)`, `reset_requested`; attributes `active_list`, `log_table`, `limits_panel`; methods `refresh_active()`, `refresh_log()`
  - `DemoPanel(parent, device)` with `.checks: dict[str, QCheckBox]`, `.force_fail_box`, `sync()`, `reset_all()`

- [ ] **Step 1: Write the failing tests**

`tests/test_dialogs.py`:
```python
from datetime import datetime

from hmi.core.alarms.engine import AlarmEngine
from hmi.core.alarms.event_log import EventLog
from hmi.device.messages import Sample
from hmi.device.simulator import SimulatedDevice
from hmi.model.alarm_limits import AlarmLimits
from hmi.model.patient import PatientProfile
from hmi.model.settings import Mode, VentSettings
from hmi.ui.dialogs.alarms import AlarmsDialog
from hmi.ui.dialogs.demo_panel import DemoPanel
from hmi.ui.dialogs.modes import ModesDialog

PATIENT = PatientProfile()


def test_modes_dialog_disables_current_mode(qapp):
    dialog = ModesDialog(None, Mode.VC)
    assert not dialog.buttons[Mode.VC].isEnabled()
    dialog.buttons[Mode.PC].click()
    assert dialog.selected is Mode.PC


def test_alarms_dialog_lists_active_alarms_and_log(qapp):
    settings, limits = VentSettings.defaults_for(PATIENT), AlarmLimits.defaults_for(PATIENT)
    engine = AlarmEngine(settings, limits)
    engine.set_ventilating(True, 0.0)
    engine.on_sample(Sample(0, 45.0, 0.0, 0.0, "I"), 1.0)
    log = EventLog(None, clock=lambda: datetime(2026, 9, 22, 12, 0, 0))
    log.add("SETTING", key="vt", old=460, new=500)
    log.add("ALARM_ON", alarm_id="HIGH_PRESSURE", priority="HIGH", detail="45.0 > 40 cmH2O")
    dialog = AlarmsDialog(None, engine, log, PATIENT, settings, limits, clock=lambda: 11.0)
    assert dialog.active_list.count() == 1
    assert "HIGH PRESSURE" in dialog.active_list.item(0).text()
    assert dialog.log_table.rowCount() == 2
    assert dialog.log_table.item(0, 1).text() == "ALARM_ON"
    seen = []
    dialog.reset_requested.connect(lambda: seen.append(True))
    dialog.reset_button.click()
    assert seen == [True]


def test_demo_panel_injects_and_resets_faults(qapp):
    device = SimulatedDevice(seed=1, sound=False)
    panel = DemoPanel(None, device)
    panel.checks["leak"].setChecked(True)
    panel.checks["link"].setChecked(True)
    panel.force_fail_box.setCurrentText("LEAK")
    assert device.lung.faults.leak_fraction == 0.5 and device.link_lost and device.force_fail == "LEAK"
    panel.reset_all()
    assert device.lung.faults.leak_fraction == 0.0 and not device.link_lost and device.force_fail is None
    assert not panel.checks["leak"].isChecked()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_dialogs.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the Modes dialog**

`hmi/ui/dialogs/modes.py`:
```python
"""ModesDialog: choose VC or PC. The main window then proposes starting values and asks to confirm."""
from __future__ import annotations

from hmi.model.settings import Mode
from hmi.qt import QtWidgets
from hmi.ui.dialogs.base import HmiDialog
from hmi.ui.theme import make_button, make_label, transparent_for_mouse

DESCRIPTIONS = {
    Mode.VC: "You set the tidal volume (VT). The machine delivers it with a constant flow; "
             "the pressure depends on the patient's lungs.",
    Mode.PC: "You set the inspiratory pressure (Pinsp). The machine holds it for Ti; "
             "the volume depends on the patient's lungs.",
}


class ModesDialog(HmiDialog):
    def __init__(self, parent, current: Mode):
        super().__init__(parent, "Ventilation mode", min_width=880)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(16)
        self.buttons: dict[Mode, QtWidgets.QPushButton] = {}
        self.selected: Mode | None = None
        for mode in Mode:
            button = QtWidgets.QPushButton()
            button.setMinimumSize(400, 180)
            inner = QtWidgets.QVBoxLayout(button)
            inner.setContentsMargins(18, 14, 18, 14)
            title = make_label(f"{mode.value} — {mode.long_name}", 22, bold=True)
            text = make_label(DESCRIPTIONS[mode], 15, muted=True)
            text.setWordWrap(True)
            inner.addWidget(title)
            inner.addWidget(text)
            if mode is current:
                current_label = make_label("Current mode", 14, bold=True)
                inner.addWidget(current_label)
                transparent_for_mouse(current_label)
                button.setEnabled(False)
            inner.addStretch(1)
            transparent_for_mouse(title, text)
            button.clicked.connect(lambda _checked=False, m=mode: self._choose(m))
            self.buttons[mode] = button
            row.addWidget(button)
        self.body.addLayout(row)
        footer = QtWidgets.QHBoxLayout()
        footer.addStretch(1)
        cancel = make_button("Cancel")
        cancel.setMinimumWidth(170)
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        self.body.addLayout(footer)

    def _choose(self, mode: Mode) -> None:
        self.selected = mode
        self.accept()

    @staticmethod
    def ask(parent, current: Mode) -> Mode | None:
        dialog = ModesDialog(parent, current)
        return dialog.selected if dialog.exec() else None
```

- [ ] **Step 4: Implement the Alarms dialog**

`hmi/ui/dialogs/alarms.py`:
```python
"""AlarmsDialog: three tabs — Active alarms, Limits, and the event Log.

Opened from the ALARMS button or by tapping the alarm banner. Alarm Reset here does the same as
the top-bar button (clears resolved high-priority alarms).
"""
from __future__ import annotations

from hmi.core.alarms.engine import AlarmEngine
from hmi.core.alarms.event_log import EventLog, describe
from hmi.model.alarm_limits import AlarmLimits
from hmi.model.patient import PatientProfile
from hmi.model.settings import VentSettings
from hmi.qt import QtCore, QtGui, QtWidgets, Signal
from hmi.ui.dialogs.base import HmiDialog
from hmi.ui.theme import ALARM_COLORS, MUTED, make_button
from hmi.ui.widgets.alarm_limits_panel import AlarmLimitsPanel

REFRESH_MS = 500


class AlarmsDialog(HmiDialog):
    limit_changed = Signal(str, float, float)
    reset_requested = Signal()

    def __init__(self, parent, engine: AlarmEngine, log: EventLog, patient: PatientProfile,
                 settings: VentSettings, limits: AlarmLimits, clock):
        super().__init__(parent, "Alarms", min_width=1120)
        self.setMinimumHeight(660)
        self._engine, self._log, self._clock = engine, log, clock
        self.tabs = QtWidgets.QTabWidget()

        self.active_list = QtWidgets.QListWidget()
        self.active_list.setStyleSheet("font-size: 19px;")
        self.tabs.addTab(self.active_list, "Active alarms")

        self.limits_panel = AlarmLimitsPanel()
        self.limits_panel.load(patient, settings, limits)
        self.limits_panel.limit_changed.connect(self.limit_changed.emit)
        self.tabs.addTab(self.limits_panel, "Limits")

        self.log_table = QtWidgets.QTableWidget(0, 3)
        self.log_table.setHorizontalHeaderLabels(["Time", "Event", "Details"])
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.log_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.log_table.setColumnWidth(0, 110)
        self.log_table.setColumnWidth(1, 200)
        self.tabs.addTab(self.log_table, "Log")
        self.body.addWidget(self.tabs, 1)

        footer = QtWidgets.QHBoxLayout()
        self.reset_button = make_button("Alarm reset")
        self.reset_button.setMinimumWidth(200)
        self.reset_button.clicked.connect(self._reset)
        footer.addWidget(self.reset_button)
        footer.addStretch(1)
        close = make_button("Close", "primary")
        close.setMinimumWidth(200)
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        self.body.addLayout(footer)

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.refresh_active)
        self._timer.start(REFRESH_MS)
        self.refresh_active()
        self.refresh_log()

    def refresh_active(self) -> None:
        now = self._clock()
        self.active_list.clear()
        states = self._engine.alarms()
        if not states:
            item = QtWidgets.QListWidgetItem("No active alarms")
            item.setForeground(QtGui.QColor(MUTED))
            self.active_list.addItem(item)
            return
        for state in states:
            item = QtWidgets.QListWidgetItem(f"{state.message}      ({now - state.onset:.0f} s ago)")
            item.setForeground(QtGui.QColor(ALARM_COLORS[state.priority]))
            self.active_list.addItem(item)

    def refresh_log(self) -> None:
        entries = self._log.recent()
        self.log_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            cells = (entry["time"][11:19], entry["kind"], describe(entry))
            for col, text in enumerate(cells):
                self.log_table.setItem(row, col, QtWidgets.QTableWidgetItem(text))

    def done(self, result: int) -> None:
        self._timer.stop()
        super().done(result)

    def _reset(self) -> None:
        self.reset_requested.emit()
        self.refresh_active()
        self.refresh_log()
```

- [ ] **Step 5: Implement the Demo Panel**

`hmi/ui/dialogs/demo_panel.py`:
```python
"""DemoPanel: fault injection for presentations (simulator only).

Opened by holding the VENT logo for 2 s or pressing F12. Each fault makes the simulated patient or
machine misbehave so the matching alarms can be demonstrated (see docs/07-demo-guide.md).
"""
from __future__ import annotations

from hmi.device.simulator import SimulatedDevice
from hmi.qt import QtCore, QtWidgets
from hmi.ui.dialogs.base import HmiDialog
from hmi.ui.theme import make_button, make_label

FAULTS = (
    ("disconnected", "Disconnection"), ("occluded", "Occlusion (expiratory)"),
    ("leak", "Large leak (50 %)"), ("stiff", "Stiff lungs (C ÷ 4)"),
    ("effort", "Patient breathing fast (40 bpm)"), ("o2", "O2 supply loss"),
    ("battery", "Battery mode (starts at 25 %)"), ("link", "MCU link loss"),
)
TESTS = ("None", "SELF", "LEAK", "COMP", "CAL", "ALARM")


class DemoPanel(HmiDialog):
    def __init__(self, parent, device: SimulatedDevice):
        super().__init__(parent, "Demo panel — fault injection", min_width=560)
        self.setModal(False)
        self.setWindowFlags(QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.FramelessWindowHint)
        self._device = device
        note = make_label("For demonstrations only. Each fault changes the simulated patient or machine "
                          "so the alarms can be shown.", 14, muted=True)
        note.setWordWrap(True)
        self.body.addWidget(note)

        grid = QtWidgets.QGridLayout()
        self.checks: dict[str, QtWidgets.QCheckBox] = {}
        for i, (key, text) in enumerate(FAULTS):
            box = QtWidgets.QCheckBox(text)
            box.toggled.connect(lambda on, k=key: self._apply(k, on))
            self.checks[key] = box
            grid.addWidget(box, i // 2, i % 2)
        self.body.addLayout(grid)

        row = QtWidgets.QHBoxLayout()
        row.addWidget(make_label("Force pre-use test failure", 16))
        self.force_fail_box = QtWidgets.QComboBox()
        self.force_fail_box.addItems(TESTS)
        self.force_fail_box.currentTextChanged.connect(self._set_force_fail)
        row.addWidget(self.force_fail_box)
        row.addStretch(1)
        self.body.addLayout(row)

        self._buzzer = make_label("", 15, muted=True)
        self.body.addWidget(self._buzzer)

        footer = QtWidgets.QHBoxLayout()
        reset = make_button("Reset all faults", "primary")
        reset.clicked.connect(self.reset_all)
        close = make_button("Close")
        close.clicked.connect(self.hide)
        footer.addWidget(reset)
        footer.addStretch(1)
        footer.addWidget(close)
        self.body.addLayout(footer)

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._update_buzzer)
        self._timer.start(500)
        self.sync()

    def sync(self) -> None:
        """Show the device's current fault state in the check boxes."""
        d, f = self._device, self._device.lung.faults
        states = {"disconnected": f.disconnected, "occluded": f.occluded, "leak": f.leak_fraction > 0,
                  "stiff": f.stiff, "effort": f.patient_rate > 0, "o2": not d.o2_supply_ok,
                  "battery": d.on_battery, "link": d.link_lost}
        for key, box in self.checks.items():
            box.blockSignals(True)
            box.setChecked(states[key])
            box.blockSignals(False)
        self.force_fail_box.blockSignals(True)
        self.force_fail_box.setCurrentText(d.force_fail or "None")
        self.force_fail_box.blockSignals(False)
        self._update_buzzer()

    def reset_all(self) -> None:
        self._device.reset_faults()
        self.sync()

    def _apply(self, key: str, on: bool) -> None:
        d, f = self._device, self._device.lung.faults
        if key == "disconnected":
            f.disconnected = on
        elif key == "occluded":
            f.occluded = on
        elif key == "leak":
            f.leak_fraction = 0.5 if on else 0.0
        elif key == "stiff":
            f.stiff = on
        elif key == "effort":
            f.patient_rate = 40.0 if on else 0.0
        elif key == "o2":
            d.set_o2_supply(not on)
        elif key == "battery":
            d.set_battery_mode(on)
        elif key == "link":
            d.set_link_lost(on)

    def _set_force_fail(self, text: str) -> None:
        self._device.force_fail = None if text == "None" else text

    def _update_buzzer(self) -> None:
        buzzer = self._device.buzzer
        text = f"Simulated MCU buzzer: {buzzer.state_text}"
        if not buzzer.available:
            text += "  (no speaker available)"
        self._buzzer.setText(text)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_dialogs.py -v`
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add hmi/ui/dialogs tests/test_dialogs.py
git commit -m "Add Modes, Alarms and Demo Panel dialogs"
```

---

### Task 19: Main window, entry point and end-to-end smoke tests

**Files:**
- Create: `hmi/ui/main_window.py`, `main.py`
- Test: `tests/test_app_smoke.py`

**Interfaces:**
- Consumes: everything above
- Produces: `MainWindow(device, log, clock=time.monotonic)` with `start()`, `update_alarms()`, `open_alarms()`, `open_demo_panel()`, attributes `flow, patient, settings, limits, engine, analyzer, last_breath, top_bar, steps, patient_screen, precheck_screen, settings_screen, monitoring_screen`;
  `main.parse_args(argv)`, `main.main(argv)`

- [ ] **Step 1: Write the failing tests**

`tests/test_app_smoke.py`:
```python
import pytest

from hmi.core.alarms.event_log import EventLog
from hmi.core.flow import Step
from hmi.device.simulator import SimulatedDevice
from hmi.ui.dialogs.confirm import ConfirmDialog
from hmi.ui.main_window import MainWindow
from main import parse_args


@pytest.fixture
def window(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ConfirmDialog, "ask", staticmethod(lambda *a, **k: True))
    device = SimulatedDevice(seed=3, sound=False)
    win = MainWindow(device, EventLog(tmp_path), clock=lambda: device.sim_time)
    yield win, device
    device.close()


def run(win, device, seconds):
    for i in range(int(seconds / 0.02)):
        device.tick()
        if i % 10 == 0:
            win.update_alarms()


def test_quick_start_to_ventilation_and_standby(window):
    win, device = window
    win.patient_screen.quick_start_requested.emit()
    assert win.flow.step is Step.SETTINGS
    win.settings_screen.start_requested.emit()
    assert win.flow.step is Step.VENTILATING
    run(win, device, 45)
    assert win.monitoring_screen.readouts["pip"].value_text() != "--"
    assert [s.id for s in win.engine.alarms()] == ["NO_PRECHECK"]
    win.monitoring_screen.standby_requested.emit()
    assert win.flow.step is Step.SETTINGS
    assert win.engine.alarms()[0].id == "NO_PRECHECK"


def test_full_pre_use_check_then_ventilate_without_alarms(window):
    win, device = window
    win.patient_screen.next_requested.emit()
    assert win.flow.step is Step.PRECHECK
    win.precheck_screen.run_all()
    run(win, device, 16)
    assert win.precheck_screen.all_passed()
    win.precheck_screen.continue_requested.emit()
    win.settings_screen.start_requested.emit()
    run(win, device, 45)
    assert win.engine.alarms() == []


def test_disconnection_reaches_the_banner(window):
    win, device = window
    win.patient_screen.quick_start_requested.emit()
    win.settings_screen.start_requested.emit()
    run(win, device, 35)
    device.lung.faults.disconnected = True
    run(win, device, 15)
    assert "LOW PRESSURE" in win.top_bar.banner.message_text()
    assert win.top_bar.banner.is_flashing()


def test_parse_args_defaults():
    args = parse_args([])
    assert not args.fullscreen and args.serial is None and not args.no_sound
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_app_smoke.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'hmi.ui.main_window'`

- [ ] **Step 3: Implement the main window**

`hmi/ui/main_window.py`:
```python
"""MainWindow: builds the screens and wires the device, breath analyzer, alarm engine and event log.

Data flow (see docs/03-architecture.md):
  device samples -> waveforms + breath analyzer -> alarm engine -> banner, readout colors, buzzer
  operator action -> confirmation -> new settings -> device + alarm engine + event log
"""
from __future__ import annotations

import time

from hmi.core.alarms.engine import AlarmEngine
from hmi.core.alarms.event_log import EventLog
from hmi.core.breath_analyzer import BreathAnalyzer, BreathResult
from hmi.core.flow import ScreenFlow, Step
from hmi.device.base import DeviceLink
from hmi.device.messages import MonitorStatus, Sample
from hmi.device.simulator import SimulatedDevice
from hmi.model.alarm_limits import AlarmLimits, validate_limits
from hmi.model.patient import PatientProfile
from hmi.model.settings import MODE_PARAMS, VentSettings, param_spec, switch_mode, validate_settings
from hmi.qt import QShortcut, QtCore, QtGui, QtWidgets
from hmi.ui.dialogs.alarms import AlarmsDialog
from hmi.ui.dialogs.confirm import ConfirmDialog
from hmi.ui.dialogs.demo_panel import DemoPanel
from hmi.ui.dialogs.modes import ModesDialog
from hmi.ui.screens.monitoring import MonitoringScreen
from hmi.ui.screens.patient import PatientScreen
from hmi.ui.screens.precheck import PrecheckScreen
from hmi.ui.screens.settings import SettingsScreen
from hmi.ui.setting_edit import edit_setting
from hmi.ui.top_bar import TopBar
from hmi.ui.widgets.step_indicator import StepIndicator

ALARM_TICK_MS = 200


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, device: DeviceLink, log: EventLog, clock=time.monotonic):
        super().__init__()
        self.setWindowTitle("Ventilator HMI")
        self.device, self.log, self.clock = device, log, clock
        self.flow = ScreenFlow()
        self.patient = PatientProfile()
        self.settings = VentSettings.defaults_for(self.patient)
        self.limits = AlarmLimits.defaults_for(self.patient)
        self.engine = AlarmEngine(self.settings, self.limits)
        self.analyzer = BreathAnalyzer()
        self.last_breath: BreathResult | None = None
        self._fault_codes: set[str] = set()
        self._buzzer_state: tuple[int, bool] | None = None
        self._demo_panel: DemoPanel | None = None

        self.top_bar = TopBar()
        self.steps = StepIndicator()
        self.patient_screen = PatientScreen()
        self.precheck_screen = PrecheckScreen(device)
        self.settings_screen = SettingsScreen()
        self.monitoring_screen = MonitoringScreen()
        self.stack = QtWidgets.QStackedWidget()
        for screen in (self.patient_screen, self.precheck_screen, self.settings_screen, self.monitoring_screen):
            self.stack.addWidget(screen)
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.top_bar)
        layout.addWidget(self.steps)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self._alarm_timer = QtCore.QTimer(self)
        self._alarm_timer.timeout.connect(self.update_alarms)
        shortcut = QShortcut(QtGui.QKeySequence("F12"), self)
        shortcut.activated.connect(self.open_demo_panel)
        self._connect()
        self.settings_screen.load(self.patient, self.settings, self.limits)
        self.monitoring_screen.load(self.patient, self.settings, self.limits)
        self._show_step()

    def start(self) -> None:
        self.device.open()
        self._alarm_timer.start(ALARM_TICK_MS)
        self.log.add("APP_START")

    # ----- wiring --------------------------------------------------------------------------------
    def _connect(self) -> None:
        d = self.device
        d.sample_received.connect(self._on_sample)
        d.status_received.connect(self._on_status)
        d.fault_changed.connect(self._on_fault)
        d.link_changed.connect(self._on_link)
        tb = self.top_bar
        tb.logo_long_pressed.connect(self.open_demo_panel)
        tb.banner_clicked.connect(self.open_alarms)
        tb.audio_pause_clicked.connect(self._audio_pause)
        tb.alarm_reset_clicked.connect(self._alarm_reset)
        self.patient_screen.next_requested.connect(self._patient_next)
        self.patient_screen.quick_start_requested.connect(self._quick_start)
        pc = self.precheck_screen
        pc.back_requested.connect(self._back)
        pc.skip_requested.connect(self._skip_precheck)
        pc.continue_requested.connect(self._precheck_done)
        pc.check_finished.connect(lambda k, ok, detail: self.log.add("PRECHECK_TEST", test=k, passed=ok, detail=detail))
        ss = self.settings_screen
        ss.back_requested.connect(self._back)
        ss.start_requested.connect(self._start_ventilation)
        ss.setting_changed.connect(lambda k, old, new: self.log.add("SETTING", key=k, old=old, new=new))
        ss.limit_changed.connect(lambda k, old, new: self.log.add("ALARM_LIMIT", key=k, old=old, new=new))
        ms = self.monitoring_screen
        ms.edit_setting_requested.connect(self._edit_setting)
        ms.modes_requested.connect(self._change_mode)
        ms.alarms_requested.connect(self.open_alarms)
        ms.standby_requested.connect(self._standby)

    # ----- device signals ------------------------------------------------------------------------
    def _ventilating(self) -> bool:
        return self.flow.step is Step.VENTILATING

    def _on_sample(self, s: Sample) -> None:
        now = self.clock()
        self.engine.on_sample(s, now)
        if self._ventilating():
            self.monitoring_screen.add_sample(s)
        result = self.analyzer.add(s)
        if result is not None:
            self.last_breath = result
            self.engine.on_breath(result, now)
            if self._ventilating():
                self.monitoring_screen.show_breath(result)

    def _on_status(self, m: MonitorStatus) -> None:
        self.engine.on_status(m, self.clock())
        self.top_bar.set_power(m.on_battery, m.battery_pct)
        self.monitoring_screen.show_fio2(m.fio2)

    def _on_fault(self, code: str, active: bool) -> None:
        if active:
            self._fault_codes.add(code)
        else:
            self._fault_codes.discard(code)
        self.engine.set_condition("DEVICE_FAULT", bool(self._fault_codes), self.clock(),
                                  " · ".join(sorted(self._fault_codes)))
        self.log.add("DEVICE_FAULT", code=code, active=active)

    def _on_link(self, ok: bool) -> None:
        self.engine.set_condition("LINK_LOST", not ok, self.clock())
        self.log.add("MCU_LINK", ok=ok)

    def update_alarms(self) -> None:
        """Every 200 ms: advance the alarm engine, log events, refresh the banner and the buzzer."""
        now = self.clock()
        self.engine.tick(now)
        for event in self.engine.drain_events():
            self.log.add(event.kind, alarm_id=event.alarm_id, priority=event.priority, detail=event.detail)
        states = self.engine.alarms()
        self.top_bar.banner.show_alarm(states[0] if states else None, max(0, len(states) - 1))
        paused = self.engine.audio_paused(now)
        self.top_bar.set_audio_paused(self.engine.audio_pause_remaining(now) if paused else None)
        self.monitoring_screen.show_alarm_colors(self.engine.readout_priorities())
        buzzer = (int(self.engine.audible_priority()), paused)
        if buzzer != self._buzzer_state:
            self._buzzer_state = buzzer
            self.device.set_buzzer(*buzzer)

    # ----- navigation ----------------------------------------------------------------------------
    def _show_step(self) -> None:
        step = self.flow.step
        self.stack.setCurrentIndex(int(step) - 1)
        self.steps.set_step(step)
        self.steps.setVisible(step is not Step.VENTILATING)
        self.top_bar.set_mode(self.settings.mode.value if step is Step.VENTILATING else "STANDBY")
        self.top_bar.set_patient(self.patient.summary())

    def _set_patient(self, patient: PatientProfile) -> None:
        self.patient = patient
        self.settings = VentSettings.defaults_for(patient)
        self.limits = AlarmLimits.defaults_for(patient)
        self.engine.update_context(self.settings, self.limits)
        self.device.set_patient(patient.category)
        self.settings_screen.load(patient, self.settings, self.limits)
        self.monitoring_screen.load(patient, self.settings, self.limits)
        self.log.add("PATIENT", category=patient.category.value, sex=patient.sex.value,
                     height_cm=patient.height_cm, ibw_kg=patient.ibw_kg, name=patient.name, patient_id=patient.patient_id)

    def _patient_next(self) -> None:
        self._set_patient(self.patient_screen.profile())
        self.flow.patient_done()
        self.precheck_screen.reset()
        self._show_step()

    def _quick_start(self) -> None:
        if not ConfirmDialog.ask(self, "Quick start",
                                 "Skip the pre-use check and use the default settings for this patient?\n"
                                 "A 'Pre-use check not performed' alarm will stay on.",
                                 confirm_text="Quick start", role="danger"):
            return
        self._set_patient(self.patient_screen.profile())
        self.flow.quick_start()
        self._mark_precheck_skipped()
        self._show_step()

    def _skip_precheck(self) -> None:
        if not ConfirmDialog.ask(self, "Skip pre-use check",
                                 "The ventilator has not been verified.\n"
                                 "A 'Pre-use check not performed' alarm will stay on.",
                                 confirm_text="Skip check", role="danger"):
            return
        self.flow.skip_precheck()
        self._mark_precheck_skipped()
        self._show_step()

    def _mark_precheck_skipped(self) -> None:
        self.engine.set_condition("NO_PRECHECK", True, self.clock())
        self.log.add("PRECHECK_SKIPPED")

    def _precheck_done(self) -> None:
        self.flow.complete_precheck()
        self.engine.set_condition("NO_PRECHECK", False, self.clock())
        self.log.add("PRECHECK_PASSED")
        self._show_step()

    def _back(self) -> None:
        self.flow.back()
        self._show_step()

    def _settings_summary(self, s: VentSettings) -> str:
        parts = []
        for key in MODE_PARAMS[s.mode]:
            spec = param_spec(self.patient.category, key)
            parts.append(f"{spec.label} {spec.fmt(s.get(key))} {spec.unit}")
        return " · ".join(parts)

    def _start_ventilation(self) -> None:
        settings, limits = self.settings_screen.settings(), self.settings_screen.limits()
        errors = validate_settings(settings, self.patient.category, limits.ppeak_high) + validate_limits(limits)
        if errors:
            ConfirmDialog.inform(self, "Cannot start", "\n".join(errors))
            return
        summary = self._settings_summary(settings)
        if not ConfirmDialog.ask(self, "Start ventilation", f"Start {settings.mode.long_name} ventilation?\n\n{summary}",
                                 confirm_text="Start", role="go"):
            return
        self._apply(settings, limits)
        self.analyzer.reset()
        self.last_breath = None
        self.monitoring_screen.reset_values()
        self.device.start_ventilation()
        self.engine.set_ventilating(True, self.clock())
        self.flow.start_ventilation()
        self.log.add("VENTILATION_START", mode=settings.mode.value, settings=summary)
        self._show_step()

    def _apply(self, settings: VentSettings, limits: AlarmLimits) -> None:
        self.settings, self.limits = settings, limits
        self.engine.update_context(settings, limits)
        self.device.apply_settings(settings, limits.ppeak_high)
        self.monitoring_screen.load(self.patient, settings, limits)
        self.settings_screen.load(self.patient, settings, limits)
        if self._ventilating():
            self.top_bar.set_mode(settings.mode.value)

    # ----- actions while ventilating -------------------------------------------------------------
    def _edit_setting(self, key: str) -> None:
        new = edit_setting(self, self.patient, self.settings, self.limits, key)
        if new is None:
            return
        self.log.add("SETTING", key=key, old=self.settings.get(key), new=new.get(key))
        self._apply(new, self.limits)

    def _change_mode(self) -> None:
        mode = ModesDialog.ask(self, self.settings.mode)
        if mode is None:
            return
        last = self.last_breath
        new = switch_mode(self.settings, mode, self.patient.category,
                          last_pip=last.pip if last else None, last_vte=last.vte if last else None)
        errors = validate_settings(new, self.patient.category, self.limits.ppeak_high)
        if errors:
            ConfirmDialog.inform(self, "Cannot switch mode", "\n".join(errors))
            return
        if not ConfirmDialog.ask(self, "Change mode", f"Switch to {mode.long_name}?\n\n{self._settings_summary(new)}",
                                 confirm_text=f"Switch to {mode.value}"):
            return
        self.log.add("MODE", key="mode", old=self.settings.mode.value, new=mode.value)
        self._apply(new, self.limits)

    def open_alarms(self) -> None:
        dialog = AlarmsDialog(self, self.engine, self.log, self.patient, self.settings, self.limits, self.clock)
        dialog.limit_changed.connect(self._on_dialog_limit_changed)
        dialog.reset_requested.connect(self._alarm_reset)
        dialog.exec()

    def _on_dialog_limit_changed(self, key: str, old: float, new: float) -> None:
        self.log.add("ALARM_LIMIT", key=key, old=old, new=new)
        self._apply(self.settings, self.limits.with_value(key, new))

    def _audio_pause(self) -> None:
        self.engine.audio_pause(self.clock())
        self.update_alarms()

    def _alarm_reset(self) -> None:
        self.engine.reset(self.clock())
        self.update_alarms()

    def _standby(self) -> None:
        if not ConfirmDialog.ask(self, "Standby", "Stop ventilation?\nThe patient will NOT be ventilated.",
                                 confirm_text="Stop ventilation", role="danger"):
            return
        self.device.standby()
        self.engine.set_ventilating(False, self.clock())
        self.flow.standby()
        self.log.add("STANDBY")
        self._show_step()

    def open_demo_panel(self) -> None:
        if not isinstance(self.device, SimulatedDevice):
            return
        if self._demo_panel is None:
            self._demo_panel = DemoPanel(self, self.device)
        self._demo_panel.sync()
        self._demo_panel.show()
        self._demo_panel.raise_()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._alarm_timer.stop()
        self.device.close()
        self.log.add("APP_STOP")
        super().closeEvent(event)
```

- [ ] **Step 4: Implement the entry point**

`main.py`:
```python
"""Ventilator HMI — entry point.

  python main.py                     1280x800 window with the simulator (laptop)
  python main.py --fullscreen        fullscreen (Raspberry Pi, seen on the tablet through VNC)
  python main.py --serial COM3       use the real ventilator MCU instead of the simulator
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hmi.core.alarms.event_log import DEFAULT_LOG_DIR, EventLog
from hmi.device.serial_device import SerialDevice
from hmi.device.simulator import SimulatedDevice
from hmi.qt import QtWidgets
from hmi.ui.main_window import MainWindow
from hmi.ui.theme import apply_theme


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ventilator HMI demo")
    parser.add_argument("--fullscreen", action="store_true", help="fill the screen (use on the Raspberry Pi)")
    parser.add_argument("--serial", metavar="PORT",
                        help="serial port of the ventilator MCU, e.g. /dev/ttyACM0 or COM3 (default: simulator)")
    parser.add_argument("--log-dir", metavar="DIR", help=f"where to save the event log (default: {DEFAULT_LOG_DIR})")
    parser.add_argument("--no-sound", action="store_true", help="simulator: do not play the buzzer on the speaker")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    app = QtWidgets.QApplication(sys.argv[:1])
    apply_theme(app)
    log = EventLog(Path(args.log_dir) if args.log_dir else DEFAULT_LOG_DIR)
    device = SerialDevice(args.serial) if args.serial else SimulatedDevice(sound=not args.no_sound)
    window = MainWindow(device, log)
    if args.fullscreen:
        window.showFullScreen()
    else:
        window.setFixedSize(1280, 800)
        window.show()
    window.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the smoke tests and the whole suite**

Run: `.venv/Scripts/python -m pytest -v`
Expected: all tests pass.

- [ ] **Step 6: Launch the app and check each screen by eye**

Run: `.venv/Scripts/python main.py`
Check: step indicator and screens fit 1280×800 with no clipped text; Patient → Next → Run all (answer prompts) → Continue → Start → waveforms sweep; F12 opens the Demo Panel; Disconnection shows a flashing red banner and the buzzer sounds; Audio pause shows the 2:00 countdown; Standby returns to Settings. Fix any layout clipping by adjusting widths/font sizes in the affected widget only.

- [ ] **Step 7: Commit**

```bash
git add hmi/ui/main_window.py main.py tests/test_app_smoke.py
git commit -m "Add main window wiring, entry point and end-to-end smoke tests"
```

---

### Task 20: Documentation

**Files:**
- Create: `README.md`, `docs/01-screen-flow.md`, `docs/02-alarms.md`, `docs/03-architecture.md`, `docs/04-simulator.md`, `docs/05-serial-protocol.md`, `docs/06-raspberry-pi-setup.md`, `docs/07-demo-guide.md`
- Create: `docs/images/` with screenshots taken from the running app (`patient.png`, `precheck.png`, `settings.png`, `monitoring.png`, `alarm.png`)

**Writing rules (from the user):** plain language, short sentences, tables and diagrams, always explain *why*. Every number must match the code and the spec. No AI/tool attribution anywhere.

- [ ] **Step 1: Take screenshots**

Write a throwaway script in the scratchpad (not committed) that builds `MainWindow` offscreen with `SimulatedDevice(seed=3, sound=False)`, drives it like `tests/test_app_smoke.py` (quick start → start → tick 40 s; then disconnection → tick 12 s for `alarm.png`), calls `window.setFixedSize(1280, 800)` and saves `window.grab().save("docs/images/<name>.png")` for each screen. Run it with `QT_QPA_PLATFORM=offscreen`. Open each PNG to check it looks right.

- [ ] **Step 2: Write `README.md`** with these sections:
  1. *What this is* — 3 sentences: ventilator HMI graduation project, runs on Raspberry Pi 4 shown on a tablet via VNC, currently a demo with a simulated patient.
  2. A screenshot (`docs/images/monitoring.png`).
  3. *Run it on your laptop* — `python -m venv .venv`, `.venv\Scripts\pip install -r requirements.txt`, `.venv\Scripts\python main.py`.
  4. *Run it on the Raspberry Pi* — one line + link to `docs/06-raspberry-pi-setup.md`.
  5. *Command-line options* table: `--fullscreen`, `--serial PORT`, `--log-dir DIR`, `--no-sound`.
  6. *Run the tests* — `.venv\Scripts\python -m pytest`.
  7. *Documentation* table linking all 7 docs with one-line descriptions, plus the design spec.
  8. *Project layout* — the folder tree from spec §5.2.
  9. *Safety note* — this is a demo, not a certified medical device.

- [ ] **Step 3: Write `docs/01-screen-flow.md`**: flow diagram (spec §3), then one section per screen with its screenshot, a table "Button → what happens", and the *why* (e.g. why IBW sets VT; why confirm dialogs; why the pre-use check is required by ISO 80601-2-12). Include the parameter range table (spec §3.3) and the cross-checks.

- [ ] **Step 4: Write `docs/02-alarms.md`**: sections — *What the standards ask for* (IEC 60601-1-8 in 5 bullet points; ISO 80601-2-12 in 5 bullet points); *Priorities* table (color, flash rate, buzzer pattern, repeat — spec §6.1); *Operator actions* (Audio Paused 120 s, Alarm Reset, latching) with a small state diagram `inactive → pending (delay) → active → resolved (latched, high only) → reset`; *Every alarm* table (spec §6.3, exact IDs, delays, latching); *Default limits* table (spec §6.4); *The event log* (file location, JSON line example); *Pi ↔ MCU responsibilities* table and the known gap (spec §6.6); *How to verify* (point to `tests/test_alarm_engine.py` and `tests/test_fault_scenarios.py`).

- [ ] **Step 5: Write `docs/03-architecture.md`**: the block diagram (spec §5.1); a table of every module (file, what it does, depends on); the "no Qt in logic layers" rule and why (testable, reusable by the MCU team); data-flow timing table (spec §5.4); "How to switch from the simulator to the real MCU" (one command: `python main.py --serial /dev/ttyACM0`, what the firmware must implement → link to doc 05).

- [ ] **Step 6: Write `docs/04-simulator.md`**: the balloon-and-tube picture in ASCII, the equation `P = PEEP + V/C + R·flow` explained term by term, VC vs PC vs expiration in one table, time constant τ = R·C with a worked example (adult: 10 × 50 / 1000 = 0.5 s → 99 % exhaled after 5τ = 2.5 s), default R and C table, and the fault table (spec §8.2, as corrected) with what each fault changes in the equations.

- [ ] **Step 7: Write `docs/05-serial-protocol.md`**: framing and checksum with a worked example (compute the XOR for `H,42` step by step and show the final line), MCU→Pi and Pi→MCU tables (spec §7, with `R` carrying a comma-free detail text), timing (50 Hz data, 1 Hz status, 5 Hz heartbeat, 1 s timeout), what the MCU must do when the Pi heartbeat stops (sound high-priority buzzer), bandwidth calculation, and "Testing without hardware" (the protocol functions in `hmi/device/protocol.py` and `tests/test_protocol.py`).

- [ ] **Step 8: Write `docs/06-raspberry-pi-setup.md`** (mark clearly at the top: *written from documentation — verify each step on your Pi*):
  1. Flash Raspberry Pi OS (64-bit, with desktop) with Raspberry Pi Imager; enable SSH and Wi-Fi in the imager settings.
  2. Copy the project (`git clone` or USB).
  3. Install Qt and libraries: try `python3 -m venv --system-site-packages .venv && .venv/bin/pip install -r requirements.txt`; if PySide6 fails to install, use `sudo apt install python3-pyqt5 python3-pyqtgraph python3-numpy python3-serial` and run with the system `python3` (the app works with PyQt5 through `hmi/qt.py`).
  4. Enable VNC: `sudo raspi-config` → Interface Options → VNC → Enable.
  5. Set the resolution to 1280×800: `raspi-config` → Display Options (or Screen Configuration tool on the desktop). For a Pi with no monitor attached, set a headless resolution in the same menu.
  6. On the Samsung tablet: install a VNC viewer app (e.g. RealVNC Viewer), connect to the Pi's IP address, choose "scale to fit".
  7. Sound: plug a small speaker into the Pi's 3.5 mm jack for the demo buzzer; test with `aplay /usr/share/sounds/alsa/Front_Center.wav`.
  8. Start the HMI: `python3 main.py --fullscreen`.
  9. Auto-start on boot: create `~/.config/autostart/ventilator-hmi.desktop` with `Exec=/home/<user>/ventilator-hmi/.venv/bin/python /home/<user>/ventilator-hmi/main.py --fullscreen` (show the full file).
  10. Troubleshooting table: black VNC screen, wrong resolution, no sound, `ModuleNotFoundError: PySide6`.

- [ ] **Step 9: Write `docs/07-demo-guide.md`**: a timed presentation script (~10 min):
  1. Patient screen — change height, show IBW formula and suggested VT (explain lung-protective ventilation).
  2. Pre-use check — Run all, block/unblock prompts, alarm test; then force a LEAK failure from the Demo Panel and Retry.
  3. Settings — show VC tile advisory by setting VT to 700; show a blocked cross-check (RR 40 with Ti 1.0); show alarm limits.
  4. Start ventilation — explain the waveforms (VC ramp vs PC square) and readouts.
  5. Alarms — table "Fault to inject → alarms you will see → what to say", covering all 8 Demo Panel faults (copy the corrected spec §8.2 table) including Audio Pause and Alarm Reset.
  6. Standby.
  Close with "Questions examiners may ask" (5 Q&A: why a separate MCU; why the buzzer is on the MCU; how latching works; what the grace period is for; how this would be certified).

- [ ] **Step 10: Check the docs against the code**

Run: `grep -rn "TODO\|TBD" README.md docs/0*.md` — expected: no output. Re-read the alarm tables against `hmi/core/alarms/definitions.py` and the limits tables against `hmi/model/alarm_limits.py`; fix any mismatch.

- [ ] **Step 11: Commit**

```bash
git add README.md docs
git commit -m "Add user documentation, setup guide and demo script"
```

---

## Final verification

- [ ] Run `.venv/Scripts/python -m pytest -v` — all tests pass.
- [ ] Run `.venv/Scripts/python main.py` and walk the full demo guide once.
- [ ] `git log --oneline` shows one commit per task, with no attribution lines.
