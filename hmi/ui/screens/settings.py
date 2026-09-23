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
