"""HmiDialog: base for every HMI dialog — frameless, modal, big title (easy to use through VNC)."""
from __future__ import annotations

from hmi.qt import QtCore, QtWidgets
from hmi.ui.theme import BORDER, SURFACE, make_label


class HmiDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None, title: str, min_width: int = 560):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.WindowType.Dialog | QtCore.Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        self.setMinimumWidth(min_width)
        self.setStyleSheet(f"HmiDialog {{ background: {SURFACE}; border: 2px solid {BORDER}; }}")
        self.body = QtWidgets.QVBoxLayout(self)
        self.body.setContentsMargins(28, 24, 28, 24)
        self.body.setSpacing(16)
        self.title_label = make_label(title, 24, bold=True)
        self.body.addWidget(self.title_label)
