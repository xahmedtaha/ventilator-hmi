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
