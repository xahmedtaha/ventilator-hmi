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
