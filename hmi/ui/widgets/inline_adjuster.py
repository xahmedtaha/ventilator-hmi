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
