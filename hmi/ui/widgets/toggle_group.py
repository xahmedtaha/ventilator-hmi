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
