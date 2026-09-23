"""AlarmLimitsPanel: tiles for every adjustable alarm limit, plus the automatic FiO2/PEEP limits.

Used on the Settings screen (Alarm limits tab) and in the Alarms dialog (Limits tab).
"""
from __future__ import annotations

from hmi.model.alarm_limits import AlarmLimits, fio2_limits, limit_spec, peep_limits, validate_limits
from hmi.model.patient import PatientProfile
from hmi.model.settings import VentSettings, validate_settings
from hmi.qt import QtWidgets, Signal
from hmi.ui.dialogs.confirm import ConfirmDialog
from hmi.ui.setting_edit import edit_limit
from hmi.ui.theme import make_button, make_label
from hmi.ui.widgets.param_tile import ParamTile

COLUMNS = (("ppeak_high", "ppeak_low"), ("vte_high", "vte_low"), ("mve_high", "mve_low"), ("rr_high", "apnea_time"))


class AlarmLimitsPanel(QtWidgets.QWidget):
    limit_changed = Signal(str, float, float)
    limits_replaced = Signal(object, object)  # (old: AlarmLimits, new: AlarmLimits) -- one change, e.g. Restore defaults

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
        errors = validate_limits(defaults) + validate_settings(self._settings, self._patient.category, defaults.ppeak_high)
        if errors:
            ConfirmDialog.inform(self, "Cannot restore defaults", errors[0])
            return
        if not ConfirmDialog.ask(self, "Restore defaults",
                                 "Reset every alarm limit to the default for this patient?", confirm_text="Restore"):
            return
        old = self._limits
        self._limits = defaults
        self._refresh()
        self.limits_replaced.emit(old, defaults)

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
