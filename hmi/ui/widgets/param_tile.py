"""ParamTile: a big tappable tile showing one setting (title, value, unit, optional advisory).

The tile's minimum height comes from the theme stylesheet (`#paramTile` / `#paramTileCompact`,
see hmi/ui/theme.py) rather than only `setMinimumSize`, because the global `QPushButton` rule is
re-applied whenever the widget is (re)polished and would otherwise squash it back down. The
advisory border is likewise a stylesheet rule keyed off the `hasNote` dynamic property, so
`set_note` never calls `setStyleSheet()` on the instance and so never wipes out the height rule.
"""
from __future__ import annotations

from hmi.qt import QtWidgets
from hmi.ui.theme import ADVISORY, make_label, transparent_for_mouse


class ParamTile(QtWidgets.QPushButton):
    def __init__(self, title: str, unit: str = "", compact: bool = False):
        super().__init__()
        self.setObjectName("paramTileCompact" if compact else "paramTile")
        self.setProperty("hasNote", False)
        self.setMinimumSize(118 if compact else 170, 84 if compact else 112)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(0)
        self._title = make_label(title, 14 if compact else 16, muted=True)
        self._value = make_label("--", 26 if compact else 34, bold=True)
        self._unit = make_label(unit, 12 if compact else 14, muted=True)
        self._note = make_label("", 12, color=ADVISORY)
        self._note.setWordWrap(True)
        self._note.hide()
        for widget in (self._title, self._value, self._unit, self._note):
            layout.addWidget(widget)
        transparent_for_mouse(self._title, self._value, self._unit, self._note)

    def set_title(self, text: str) -> None:
        self._title.setText(text)

    def set_unit(self, text: str) -> None:
        self._unit.setText(text)

    def set_value(self, text: str) -> None:
        self._value.setText(text)

    def value_text(self) -> str:
        return self._value.text()

    def set_note(self, text: str | None) -> None:
        self._note.setText(text or "")
        self._note.setVisible(bool(text))
        self.setProperty("hasNote", bool(text))
        self.style().unpolish(self)
        self.style().polish(self)

    def note_text(self) -> str:
        return self._note.text()
