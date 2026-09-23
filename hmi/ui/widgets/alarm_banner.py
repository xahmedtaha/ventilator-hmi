"""AlarmBanner: shows the most important alarm, flashing per IEC 60601-1-8.

High priority: red, flashing 2 Hz. Medium: yellow, flashing 0.6 Hz. Low: cyan, steady.
Resolved (latched) alarms are shown steady with a colored border until Alarm Reset.
Tapping the banner opens the alarm list.
"""
from __future__ import annotations

from hmi.core.alarms.definitions import Priority
from hmi.core.alarms.engine import AlarmState
from hmi.qt import QtCore, QtWidgets
from hmi.ui.theme import ALARM_COLORS, ALARM_TEXT, BORDER, MUTED, SURFACE, SURFACE_2, make_label, transparent_for_mouse

FLASH_HALF_PERIOD_MS = {Priority.HIGH: 250, Priority.MEDIUM: 833}  # 2 Hz and 0.6 Hz at 50 % duty


class AlarmBanner(QtWidgets.QPushButton):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(56)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 12, 0)
        self._text = make_label("")
        self._badge = make_label("")
        layout.addWidget(self._text, 1)
        layout.addWidget(self._badge)
        transparent_for_mouse(self._text, self._badge)
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._toggle)
        self._key: tuple[Priority, bool] | None = None
        self._flash_on = True
        self.show_alarm(None, 0)

    def show_alarm(self, top: AlarmState | None, others: int) -> None:
        self._badge.setText(f"+{others}" if others > 0 else "")
        if top is None:
            self._timer.stop()
            self._key = None
            self._text.setText("No active alarms")
            self._render()
            return
        self._text.setText(top.message)
        key = (top.priority, top.active)
        if key != self._key:
            self._key = key
            self._timer.stop()
            self._flash_on = True
            interval = FLASH_HALF_PERIOD_MS.get(top.priority) if top.active else None
            if interval:
                self._timer.start(interval)
            self._render()

    def is_flashing(self) -> bool:
        return self._timer.isActive()

    def message_text(self) -> str:
        return self._text.text()

    def badge_text(self) -> str:
        return self._badge.text()

    def _toggle(self) -> None:
        self._flash_on = not self._flash_on
        self._render()

    def _render(self) -> None:
        if self._key is None:
            background, border, foreground = SURFACE, BORDER, MUTED
        else:
            priority, active = self._key
            border = ALARM_COLORS[priority]
            if active and self._flash_on:
                background, foreground = border, ALARM_TEXT[priority]
            else:
                background, foreground = SURFACE_2, border
        self.setStyleSheet(f"QPushButton {{ background: {background}; border: 2px solid {border}; border-radius: 10px; }}")
        label_style = f"font-size: 19px; font-weight: 700; color: {foreground};"
        self._text.setStyleSheet(label_style)
        self._badge.setStyleSheet(label_style)
