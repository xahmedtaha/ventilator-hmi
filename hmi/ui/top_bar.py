"""TopBar: logo (long-press opens the Demo Panel), mode, patient, alarm banner, Audio Pause,
Alarm Reset, power and clock. Always visible on every screen."""
from __future__ import annotations

import math
from datetime import datetime

from hmi.qt import QtCore, QtWidgets, Signal
from hmi.ui.theme import ADVISORY, ALIGN_CENTER, BORDER, PRIMARY, SURFACE, make_button, make_label
from hmi.ui.widgets.alarm_banner import AlarmBanner

LONG_PRESS_MS = 2000
PAUSE_IDLE_TEXT = "Audio\npause"


class TopBar(QtWidgets.QFrame):
    logo_long_pressed = Signal()
    banner_clicked = Signal()
    audio_pause_clicked = Signal()
    alarm_reset_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("topbar")
        self.setFixedHeight(76)
        self.setStyleSheet(f"QFrame#topbar {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}")
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(8)

        self._logo = make_button("VENT")
        self._logo.setFixedSize(76, 56)
        self._logo.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {PRIMARY};")
        self._press_timer = QtCore.QTimer(self)
        self._press_timer.setSingleShot(True)
        self._press_timer.setInterval(LONG_PRESS_MS)
        self._press_timer.timeout.connect(self.logo_long_pressed.emit)
        self._logo.pressed.connect(self._press_timer.start)
        self._logo.released.connect(self._press_timer.stop)

        self._mode = make_label("STANDBY", 18, bold=True)
        self._mode.setFixedWidth(96)
        self._mode.setAlignment(ALIGN_CENTER)
        self._patient = make_label("", 14, muted=True)
        self._patient.setFixedWidth(170)
        self._patient.setWordWrap(True)

        self.banner = AlarmBanner()
        self.banner.clicked.connect(self.banner_clicked.emit)

        self._pause = make_button(PAUSE_IDLE_TEXT)
        self._pause.setFixedSize(112, 56)
        self._pause.setStyleSheet("font-size: 15px; min-height: 0px;")
        self._pause.clicked.connect(self.audio_pause_clicked.emit)
        self._reset = make_button("Alarm\nreset")
        self._reset.setFixedSize(112, 56)
        self._reset.setStyleSheet("font-size: 15px; min-height: 0px;")
        self._reset.clicked.connect(self.alarm_reset_clicked.emit)

        self._status = make_label("", 15, bold=True)
        self._status.setFixedWidth(96)
        self._status.setAlignment(ALIGN_CENTER)
        self._clock_text = ""
        self._power_text = "AC 100 %"
        self._power_color = None

        for widget in (self._logo, self._mode, self._patient):
            row.addWidget(widget)
        row.addWidget(self.banner, 1)
        for widget in (self._pause, self._reset, self._status):
            row.addWidget(widget)

        self._clock = QtCore.QTimer(self)
        self._clock.timeout.connect(self._tick_clock)
        self._clock.start(1000)
        self._tick_clock()

    def set_mode(self, text: str) -> None:
        self._mode.setText(text)

    def set_patient(self, text: str) -> None:
        self._patient.setText(text)

    def set_power(self, on_battery: bool, pct: float) -> None:
        self._power_text = f"{'BATT' if on_battery else 'AC'} {pct:.0f} %"
        self._power_color = ADVISORY if on_battery else None
        self._render_status()

    def set_audio_paused(self, remaining_s: float | None) -> None:
        if remaining_s is None:
            self._pause.setText(PAUSE_IDLE_TEXT)
            self._pause.setStyleSheet("font-size: 15px; min-height: 0px;")
            return
        minutes, seconds = divmod(int(math.ceil(remaining_s)), 60)
        self._pause.setText(f"Audio paused\n{minutes}:{seconds:02d}")
        self._pause.setStyleSheet(f"font-size: 14px; min-height: 0px; font-weight: 700; border: 2px solid {PRIMARY};")

    def audio_pause_text(self) -> str:
        return self._pause.text()

    def _tick_clock(self) -> None:
        self._clock_text = datetime.now().strftime("%H:%M")
        self._render_status()

    def _render_status(self) -> None:
        self._status.setText(f"{self._clock_text}\n{self._power_text}")
        color = f" color: {self._power_color};" if self._power_color else ""
        self._status.setStyleSheet(f"font-size: 15px; font-weight: 700;{color}")
