"""Screen 2 — Pre-Use Check (ISO 80601-2-12 asks for a documented pre-use check).

Four tests run in order: system self-test, circuit leak test, circuit compliance & resistance, and
sensor calibration + alarm test. The operator is prompted to block/unblock the patient Y-piece
when needed, and must confirm hearing and seeing the alarm. The sequence stops at the first
failure; each failed test can be retried. Continue is enabled only when all tests pass.
"""
from __future__ import annotations

from hmi.core.alarms.definitions import Priority
from hmi.device.base import DeviceLink
from hmi.device.messages import TestResult
from hmi.qt import QtCore, QtWidgets, Signal
from hmi.ui.dialogs.confirm import ConfirmDialog
from hmi.ui.theme import ADVISORY, ALARM_COLORS, ALARM_TEXT, MUTED, PRIMARY, make_button, make_label

CHECKS = (
    ("SELF", "System self-test", "MCU link · sensors · valves · battery at least 20 %"),
    ("LEAK", "Circuit leak test", "Leak < 200 mL/min with the Y-piece blocked"),
    ("COMP", "Circuit compliance & resistance", "C 0.5–5.0 mL/cmH2O · R < 6 cmH2O/(L/s)"),
    ("CAL", "Sensor calibration + alarm test", "O2 21 ± 2 % on air · flow zero < 0.5 L/min · alarm heard and seen"),
)
PENDING, RUNNING, PASSED, FAILED = "pending", "running", "passed", "failed"
STATUS_LOOK = {PENDING: ("Pending", MUTED), RUNNING: ("Running…", PRIMARY),
               PASSED: ("✔ Pass", "#3fcf7a"), FAILED: ("✖ Fail", ADVISORY)}
RESULT_TIMEOUT_MS = 10000
FLASH_MS = 250  # 2 Hz, like a high-priority alarm


class CheckRow(QtWidgets.QFrame):
    def __init__(self, number: int, title: str, criterion: str):
        super().__init__()
        self.setObjectName("card")
        self._grid = grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(16, 10, 16, 10)
        grid.setHorizontalSpacing(16)
        grid.addWidget(make_label(str(number), 26, bold=True, muted=True), 0, 0, 2, 1)
        self._title_label = make_label(title, 20, bold=True)
        self._criterion_label = make_label(criterion, 14, muted=True)
        grid.addWidget(self._title_label, 0, 1)
        grid.addWidget(self._criterion_label, 1, 1)
        self._status = make_label("", 18, bold=True)
        self._status.setFixedWidth(130)
        self._detail = make_label("", 15)
        self._detail.setWordWrap(True)
        self._detail.setMinimumWidth(380)
        self.retry_button = make_button("Retry")
        self.retry_button.setFixedWidth(110)
        grid.addWidget(self._status, 0, 2, 2, 1)
        grid.addWidget(self._detail, 0, 3, 2, 1)
        grid.addWidget(self.retry_button, 0, 4, 2, 1)
        grid.setColumnStretch(3, 1)
        self.status = PENDING
        self.set_status(PENDING)

    def set_status(self, status: str, detail: str = "") -> None:
        self.status = status
        text, color = STATUS_LOOK[status]
        self._status.setText(text)
        self._status.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {color};")
        self._detail.setText(detail)
        self.retry_button.setVisible(status == FAILED)

    def detail_text(self) -> str:
        return self._detail.text()

    def label_column_natural_width(self) -> int:
        """Widest of the title/criterion text at their own font, before any shared column width is set."""
        return max(self._title_label.sizeHint().width(), self._criterion_label.sizeHint().width())

    def set_label_column_width(self, width: int) -> None:
        """Give every row the same minimum width for column 1, so the status/detail/Retry columns
        that follow line up across rows regardless of each row's own title/criterion length."""
        self._grid.setColumnMinimumWidth(1, width)


class PrecheckScreen(QtWidgets.QWidget):
    back_requested = Signal()
    continue_requested = Signal()
    skip_requested = Signal()
    check_finished = Signal(str, bool, str)

    def __init__(self, device: DeviceLink):
        super().__init__()
        self._device = device
        device.test_finished.connect(self._on_result)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(12)
        root.addWidget(make_label("Pre-use check", 28, bold=True))
        root.addWidget(make_label("Run before connecting a patient (ISO 80601-2-12).", 15, muted=True))

        self._flash = make_label("ALARM TEST — listen for the buzzer and watch this bar", 20, bold=True)
        self._flash.setMinimumHeight(48)
        self._flash.hide()
        root.addWidget(self._flash)
        self._flash_on = False
        self._flash_timer = QtCore.QTimer(self)
        self._flash_timer.timeout.connect(self._toggle_flash)

        self.rows: dict[str, CheckRow] = {}
        for number, (key, title, criterion) in enumerate(CHECKS, start=1):
            row = CheckRow(number, title, criterion)
            row.retry_button.clicked.connect(lambda _checked=False, k=key: self.retry(k))
            self.rows[key] = row
            root.addWidget(row)
        column_width = max(row.label_column_natural_width() for row in self.rows.values())
        for row in self.rows.values():
            row.set_label_column_width(column_width)
        root.addStretch(1)

        footer = QtWidgets.QHBoxLayout()
        back = make_button("←  Back")
        back.setMinimumWidth(160)
        back.clicked.connect(self.back_requested.emit)
        skip = make_button("Skip check", "danger")
        skip.setMinimumWidth(180)
        skip.clicked.connect(self.skip_requested.emit)
        self.run_button = make_button("Run all", "primary")
        self.run_button.setMinimumWidth(180)
        self.run_button.clicked.connect(self.run_all)
        self.continue_button = make_button("Continue  →", "go")
        self.continue_button.setMinimumWidth(220)
        self.continue_button.clicked.connect(self.continue_requested.emit)
        for widget in (back, skip):
            footer.addWidget(widget)
        footer.addStretch(1)
        footer.addWidget(self.run_button)
        footer.addWidget(self.continue_button)
        root.addLayout(footer)

        self._queue: list[str] = []
        self._running: str | None = None
        self._y_blocked = False
        self._cal_detail = ""
        self._timeout = QtCore.QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.timeout.connect(self._on_timeout)
        self._update_buttons()

    # ----- public --------------------------------------------------------------------------------
    def reset(self) -> None:
        for row in self.rows.values():
            row.set_status(PENDING)
        self._queue.clear()
        self._running = None
        self._y_blocked = False
        self._timeout.stop()
        self._stop_flash()
        self._update_buttons()

    def all_passed(self) -> bool:
        return all(row.status == PASSED for row in self.rows.values())

    def run_all(self) -> None:
        if self._running:
            return
        self._queue = [key for key, row in self.rows.items() if row.status != PASSED]
        self._next()

    def retry(self, key: str) -> None:
        if self._running:
            return
        self._queue = [key]
        self._next()

    # ----- sequence ------------------------------------------------------------------------------
    def _next(self) -> None:
        self._update_buttons()
        if self._running or not self._queue:
            return
        key = self._queue.pop(0)
        if not self._prepare(key):
            self._queue.clear()
            self._update_buttons()
            return
        self._start(key, key)

    def _prepare(self, key: str) -> bool:
        """Ask the operator to block or unblock the Y-piece when the next test needs it."""
        if key in ("LEAK", "COMP") and not self._y_blocked:
            if not ConfirmDialog.ask(self, "Block the Y-piece",
                                     "Block the patient Y-piece with the test plug, then tap Start.\n"
                                     "Keep it blocked for the leak and compliance tests.", confirm_text="Start"):
                return False
            self._y_blocked = True
        elif key in ("SELF", "CAL") and self._y_blocked:
            if not ConfirmDialog.ask(self, "Unblock the Y-piece",
                                     "Remove the test plug so the circuit is open to room air, then tap Start.",
                                     confirm_text="Start"):
                return False
            self._y_blocked = False
        return True

    def _start(self, key: str, test: str) -> None:
        self._running = test
        detail = f"{self._cal_detail} · alarm test…" if test == "ALARM" else ""
        self.rows[key].set_status(RUNNING, detail)
        if test == "ALARM":
            self._start_flash()
        self._timeout.start(RESULT_TIMEOUT_MS)
        self._update_buttons()
        self._device.run_test(test)

    def _on_result(self, result: TestResult) -> None:
        if result.test != self._running:
            return
        self._timeout.stop()
        self._running = None
        if result.test == "CAL":
            if result.passed:
                self._cal_detail = result.detail
                self._start("CAL", "ALARM")
            else:
                self._finish("CAL", False, result.detail)
            return
        if result.test == "ALARM":
            self._stop_flash()
            if not result.passed:
                self._finish("CAL", False, result.detail)
                return
            heard = ConfirmDialog.ask(self, "Alarm test",
                                      "Did you hear the alarm buzzer and see the red bar flashing?",
                                      confirm_text="I heard and saw it", role="go", cancel_text="Not heard")
            self._finish("CAL", heard, f"{self._cal_detail} · alarm {'confirmed' if heard else 'NOT confirmed'}")
            return
        self._finish(result.test, result.passed, result.detail)

    def _on_timeout(self) -> None:
        test = self._running
        self._running = None
        self._stop_flash()
        self._finish("CAL" if test in ("CAL", "ALARM") else test, False, "No response from the device")

    def _finish(self, key: str, passed: bool, detail: str) -> None:
        self.rows[key].set_status(PASSED if passed else FAILED, detail)
        self.check_finished.emit(key, passed, detail)
        if not passed:
            self._queue.clear()
        self._next()

    def _update_buttons(self) -> None:
        idle = self._running is None
        self.run_button.setEnabled(idle and not self.all_passed())
        self.continue_button.setEnabled(idle and self.all_passed())
        for row in self.rows.values():
            row.retry_button.setEnabled(idle)

    # ----- alarm-test flashing bar ---------------------------------------------------------------
    def _start_flash(self) -> None:
        self._flash.show()
        self._flash_on = False
        self._toggle_flash()
        self._flash_timer.start(FLASH_MS)

    def _stop_flash(self) -> None:
        self._flash_timer.stop()
        self._flash.hide()

    def _toggle_flash(self) -> None:
        self._flash_on = not self._flash_on
        red = ALARM_COLORS[Priority.HIGH]
        if self._flash_on:
            style = f"background: {red}; color: {ALARM_TEXT[Priority.HIGH]};"
        else:
            style = f"background: transparent; color: {red}; border: 2px solid {red};"
        self._flash.setStyleSheet(f"font-size: 20px; font-weight: 700; padding: 8px; border-radius: 8px; {style}")
