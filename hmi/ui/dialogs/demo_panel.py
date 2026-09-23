"""DemoPanel: fault injection for presentations (simulator only).

Opened by holding the VENT logo for 2 s or pressing F12. Each fault makes the simulated patient or
machine misbehave so the matching alarms can be demonstrated (see docs/07-demo-guide.md).
"""
from __future__ import annotations

from hmi.device.simulator import SimulatedDevice
from hmi.qt import QtCore, QtGui, QtWidgets
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
        self.sync()

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        self._timer.start(500)
        super().showEvent(event)

    def hideEvent(self, event: QtGui.QHideEvent) -> None:
        self._timer.stop()
        super().hideEvent(event)

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
