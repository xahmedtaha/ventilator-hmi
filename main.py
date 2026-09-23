"""Ventilator HMI — entry point.

  python main.py                     1280x800 window with the simulator (laptop)
  python main.py --fullscreen        fullscreen (Raspberry Pi, seen on the tablet through VNC)
  python main.py --serial COM3       use the real ventilator MCU instead of the simulator
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hmi.core.alarms.event_log import DEFAULT_LOG_DIR, EventLog
from hmi.device.serial_device import SerialDevice
from hmi.device.simulator import SimulatedDevice
from hmi.qt import QtWidgets
from hmi.ui.main_window import MainWindow
from hmi.ui.theme import apply_theme


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ventilator HMI demo")
    parser.add_argument("--fullscreen", action="store_true", help="fill the screen (use on the Raspberry Pi)")
    parser.add_argument("--serial", metavar="PORT",
                        help="serial port of the ventilator MCU, e.g. /dev/ttyACM0 or COM3 (default: simulator)")
    parser.add_argument("--log-dir", metavar="DIR", help=f"where to save the event log (default: {DEFAULT_LOG_DIR})")
    parser.add_argument("--no-sound", action="store_true", help="simulator: do not play the buzzer on the speaker")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    app = QtWidgets.QApplication(sys.argv[:1])
    apply_theme(app)
    log = EventLog(Path(args.log_dir) if args.log_dir else DEFAULT_LOG_DIR)
    device = SerialDevice(args.serial) if args.serial else SimulatedDevice(sound=not args.no_sound)
    window = MainWindow(device, log)
    if args.fullscreen:
        window.showFullScreen()
    else:
        window.setFixedSize(1280, 800)
        window.show()
    window.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
