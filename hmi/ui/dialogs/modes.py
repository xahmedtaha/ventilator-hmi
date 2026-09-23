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
