"""AlarmsDialog: three tabs — Active alarms, Limits, and the event Log.

Opened from the ALARMS button or by tapping the alarm banner. Alarm Reset here does the same as
the top-bar button (clears resolved high-priority alarms).
"""
from __future__ import annotations

from hmi.core.alarms.engine import AlarmEngine
from hmi.core.alarms.event_log import EventLog, describe
from hmi.model.alarm_limits import AlarmLimits
from hmi.model.patient import PatientProfile
from hmi.model.settings import VentSettings
from hmi.qt import QtCore, QtGui, QtWidgets, Signal
from hmi.ui.dialogs.base import HmiDialog
from hmi.ui.theme import ALARM_COLORS, MUTED, make_button
from hmi.ui.widgets.alarm_limits_panel import AlarmLimitsPanel

REFRESH_MS = 500


class AlarmsDialog(HmiDialog):
    limit_changed = Signal(str, float, float)
    reset_requested = Signal()

    def __init__(self, parent, engine: AlarmEngine, log: EventLog, patient: PatientProfile,
                 settings: VentSettings, limits: AlarmLimits, clock):
        super().__init__(parent, "Alarms", min_width=1120)
        self.setMinimumHeight(660)
        self._engine, self._log, self._clock = engine, log, clock
        self.tabs = QtWidgets.QTabWidget()

        self.active_list = QtWidgets.QListWidget()
        self.active_list.setStyleSheet("font-size: 19px;")
        self.tabs.addTab(self.active_list, "Active alarms")

        self.limits_panel = AlarmLimitsPanel()
        self.limits_panel.load(patient, settings, limits)
        self.limits_panel.limit_changed.connect(self.limit_changed.emit)
        self.tabs.addTab(self.limits_panel, "Limits")

        self.log_table = QtWidgets.QTableWidget(0, 3)
        self.log_table.setHorizontalHeaderLabels(["Time", "Event", "Details"])
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.log_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.log_table.setColumnWidth(0, 110)
        self.log_table.setColumnWidth(1, 200)
        self.tabs.addTab(self.log_table, "Log")
        self.body.addWidget(self.tabs, 1)

        footer = QtWidgets.QHBoxLayout()
        self.reset_button = make_button("Alarm reset")
        self.reset_button.setMinimumWidth(200)
        self.reset_button.clicked.connect(self._reset)
        footer.addWidget(self.reset_button)
        footer.addStretch(1)
        close = make_button("Close", "primary")
        close.setMinimumWidth(200)
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        self.body.addLayout(footer)

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.refresh_active)
        self._timer.start(REFRESH_MS)
        self.refresh_active()
        self.refresh_log()

    def refresh_active(self) -> None:
        now = self._clock()
        self.active_list.clear()
        states = self._engine.alarms()
        if not states:
            item = QtWidgets.QListWidgetItem("No active alarms")
            item.setForeground(QtGui.QColor(MUTED))
            self.active_list.addItem(item)
            return
        for state in states:
            item = QtWidgets.QListWidgetItem(f"{state.message}      ({now - state.onset:.0f} s ago)")
            item.setForeground(QtGui.QColor(ALARM_COLORS[state.priority]))
            self.active_list.addItem(item)

    def refresh_log(self) -> None:
        entries = self._log.recent()
        self.log_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            cells = (entry["time"][11:19], entry["kind"], describe(entry))
            for col, text in enumerate(cells):
                self.log_table.setItem(row, col, QtWidgets.QTableWidgetItem(text))

    def done(self, result: int) -> None:
        self._timer.stop()
        super().done(result)

    def _reset(self) -> None:
        self.reset_requested.emit()
        self.refresh_active()
        self.refresh_log()
