"""ConfirmDialog: every action that changes ventilation asks for an explicit confirmation."""
from __future__ import annotations

from hmi.qt import QtWidgets
from hmi.ui.dialogs.base import HmiDialog
from hmi.ui.theme import make_button, make_label


class ConfirmDialog(HmiDialog):
    def __init__(self, parent, title: str, text: str, confirm_text: str = "Confirm",
                 cancel_text: str | None = "Cancel", role: str = "primary"):
        super().__init__(parent, title)
        message = make_label(text, 19)
        message.setWordWrap(True)
        self.body.addWidget(message)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        self.cancel_button = None
        if cancel_text:
            self.cancel_button = make_button(cancel_text)
            self.cancel_button.setMinimumWidth(170)
            self.cancel_button.clicked.connect(self.reject)
            row.addWidget(self.cancel_button)
        self.confirm_button = make_button(confirm_text, role)
        self.confirm_button.setMinimumWidth(210)
        self.confirm_button.clicked.connect(self.accept)
        row.addWidget(self.confirm_button)
        self.body.addLayout(row)

    @staticmethod
    def ask(parent, title: str, text: str, confirm_text: str = "Confirm", role: str = "primary",
            cancel_text: str | None = "Cancel") -> bool:
        return bool(ConfirmDialog(parent, title, text, confirm_text, cancel_text, role).exec())

    @staticmethod
    def inform(parent, title: str, text: str) -> None:
        ConfirmDialog.ask(parent, title, text, confirm_text="OK", cancel_text=None)
