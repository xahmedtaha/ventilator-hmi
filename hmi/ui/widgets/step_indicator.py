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
