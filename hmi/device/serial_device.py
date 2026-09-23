"""SerialDevice: talks to the real ventilator MCU over USB/UART (implements DeviceLink).

Reads protocol lines (docs/05-serial-protocol.md) every 10 ms and turns them into signals, sends a
heartbeat every 200 ms, and reports the link as lost when no MCU heartbeat arrives for 1 s.
Not yet tested against real firmware; the unit tests use a fake serial port.
"""
from __future__ import annotations

import sys
import time

from hmi.device.base import DeviceLink
from hmi.device.messages import Ack, Fault, Heartbeat, MonitorStatus, Sample, TestResult
from hmi.device.protocol import (
    ProtocolError, encode_buzzer, encode_command, encode_heartbeat, encode_run_test,
    encode_settings, parse_mcu_message,
)
from hmi.model.settings import VentSettings
from hmi.qt import QtCore

POLL_MS = 10
HEARTBEAT_MS = 200
LINK_TIMEOUT_S = 1.0


class SerialDevice(DeviceLink):
    def __init__(self, port: str, baudrate: int = 115200, parent: QtCore.QObject | None = None,
                 serial_factory=None, clock=time.monotonic):
        super().__init__(parent)
        self._factory = serial_factory or (lambda: self._open_port(port, baudrate))
        self._clock = clock
        self._serial = None
        self._buffer = b""
        self._seq = 0
        self._opened_at = 0.0
        self._last_heartbeat: float | None = None
        self._link_state: bool | None = None  # None = not known yet
        self.bad_lines = 0
        self._cmd_faults: set[str] = set()
        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.timeout.connect(self.poll)
        self._beat_timer = QtCore.QTimer(self)
        self._beat_timer.timeout.connect(self.heartbeat)

    @staticmethod
    def _open_port(port: str, baudrate: int):
        import serial  # pyserial, imported here so the demo runs without it

        return serial.Serial(port, baudrate, timeout=0)

    # ----- DeviceLink ----------------------------------------------------------------------------
    def open(self) -> None:
        try:
            self._serial = self._factory()
        except ImportError as exc:
            print(f"pyserial is not installed: {exc}", file=sys.stderr)
            self._port_failed(exc)
        except OSError as exc:
            self._port_failed(exc)
        self._opened_at = self._clock()
        self._poll_timer.start(POLL_MS)
        self._beat_timer.start(HEARTBEAT_MS)

    def close(self) -> None:
        self._poll_timer.stop()
        self._beat_timer.stop()
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def apply_settings(self, settings: VentSettings, pmax: float) -> None:
        for line in encode_settings(settings, pmax):
            self._send(line)

    def start_ventilation(self) -> None:
        self._send(encode_command("START"))

    def standby(self) -> None:
        self._send(encode_command("STANDBY"))

    def run_test(self, test: str) -> None:
        self._send(encode_run_test(test))

    def set_buzzer(self, priority: int, paused: bool) -> None:
        self._send(encode_buzzer(priority, paused))

    # ----- I/O -----------------------------------------------------------------------------------
    def poll(self) -> None:
        if self._serial is None:
            return
        try:
            waiting = self._serial.in_waiting
            if waiting:
                self._buffer += self._serial.read(waiting)
        except OSError as exc:
            self._port_failed(exc)
            return
        *lines, self._buffer = self._buffer.split(b"\n")
        for raw in lines:
            self._handle_line(raw.decode("ascii", errors="replace"))
        if len(self._buffer) > 4096:
            # No newline in 4 KB: a stuck/garbage stream. Drop it rather than growing forever.
            self.bad_lines += 1
            self._buffer = b""

    def heartbeat(self) -> None:
        """Send our heartbeat; report the link lost once if the MCU has been silent for > 1 s."""
        self._seq += 1
        self._send(encode_heartbeat(self._seq))
        last = self._last_heartbeat if self._last_heartbeat is not None else self._opened_at
        if self._clock() - last > LINK_TIMEOUT_S and self._link_state is not False:
            self._set_link(False)

    def _send(self, line: str) -> None:
        if self._serial is not None:
            try:
                self._serial.write(line.encode("ascii"))
            except OSError as exc:
                self._port_failed(exc)

    def _port_failed(self, exc: Exception) -> None:
        """Close the port on serial I/O failure and report the link as lost."""
        if self._serial is not None:
            try:
                self._serial.close()
            except OSError:
                pass  # Ignore errors while closing
        self._serial = None
        if self._link_state is not False:
            self._set_link(False)

    def _set_link(self, ok: bool) -> None:
        self._link_state = ok
        self.link_changed.emit(ok)

    def _handle_line(self, line: str) -> None:
        if not line.strip():
            return
        try:
            msg = parse_mcu_message(line)
        except ProtocolError:
            self.bad_lines += 1
            return
        if isinstance(msg, Sample):
            self.sample_received.emit(msg)
        elif isinstance(msg, MonitorStatus):
            self.status_received.emit(msg)
        elif isinstance(msg, TestResult):
            self.test_finished.emit(msg)
        elif isinstance(msg, Fault):
            self.fault_changed.emit(msg.code, msg.active)
        elif isinstance(msg, Heartbeat):
            self._last_heartbeat = self._clock()
            if self._link_state is not True:
                self._set_link(True)
        elif isinstance(msg, Ack):
            code = f"CMD_{msg.command}_REJECTED"
            if msg.ok:
                if code in self._cmd_faults:
                    self._cmd_faults.discard(code)
                    self.fault_changed.emit(code, False)
            else:
                self._cmd_faults.add(code)
                self.fault_changed.emit(code, True)
