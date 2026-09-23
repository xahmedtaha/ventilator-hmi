"""KeyboardDialog: on-screen keyboard for the optional patient name and ID (no typing over VNC needed)."""
from __future__ import annotations

from hmi.qt import QtWidgets
from hmi.ui.dialogs.base import HmiDialog
from hmi.ui.theme import SURFACE_2, make_button, make_label

ROWS = ("1234567890", "QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM-.")
MAX_LENGTH = 24


class KeyboardDialog(HmiDialog):
    def __init__(self, parent, title: str, text: str = ""):
        super().__init__(parent, title, min_width=900)
        self._text = text
        self._display = make_label("", 28, bold=True)
        self._display.setStyleSheet(f"font-size: 28px; font-weight: 700; background: {SURFACE_2}; "
                                    "padding: 8px 14px; border-radius: 8px;")
        self._display.setMinimumHeight(56)
        self.body.addWidget(self._display)
        for keys in ROWS:
            row = QtWidgets.QHBoxLayout()
            row.addStretch(1)
            for ch in keys:
                key = make_button(ch)
                key.setFixedSize(72, 60)
                key.clicked.connect(lambda _checked=False, c=ch: self.type(c))
                row.addWidget(key)
            row.addStretch(1)
            self.body.addLayout(row)
        bottom = QtWidgets.QHBoxLayout()
        for text_, slot, width in (("Clear", self.clear, 120), ("Space", lambda: self.type(" "), 300),
                                   ("Back", self.backspace, 120)):
            button = make_button(text_)
            button.setFixedWidth(width)
            button.clicked.connect(slot)
            bottom.addWidget(button)
        bottom.addStretch(1)
        cancel = make_button("Cancel")
        cancel.clicked.connect(self.reject)
        ok = make_button("OK", "primary")
        ok.setMinimumWidth(160)
        ok.clicked.connect(self.accept)
        bottom.addWidget(cancel)
        bottom.addWidget(ok)
        self.body.addLayout(bottom)
        self._refresh()

    def type(self, ch: str) -> None:
        if len(self._text) < MAX_LENGTH:
            self._text += ch
            self._refresh()

    def backspace(self) -> None:
        self._text = self._text[:-1]
        self._refresh()

    def clear(self) -> None:
        self._text = ""
        self._refresh()

    def text(self) -> str:
        return self._text.strip()

    def _refresh(self) -> None:
        self._display.setText(self._text + "_")

    @staticmethod
    def ask(parent, title: str, text: str = "") -> str | None:
        dialog = KeyboardDialog(parent, title, text)
        return dialog.text() if dialog.exec() else None
