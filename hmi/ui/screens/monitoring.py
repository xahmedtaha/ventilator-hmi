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
