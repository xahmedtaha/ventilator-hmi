"""Serial text protocol between the Raspberry Pi and the MCU (see docs/05-serial-protocol.md).

Each message is one line:  $<TYPE>,<field>,<field>...*<CS>\\n
CS = XOR of every character between '$' and '*', as two uppercase hex digits (like GPS/NMEA).
No Qt imports, so the MCU team can read this file as the reference.
"""
from __future__ import annotations

from hmi.device.messages import Ack, Fault, Heartbeat, MonitorStatus, Sample, TestResult
from hmi.model.settings import PARAM_KEYS, VentSettings

SETTING_NAMES = {"vt": "VT", "pinsp": "PINSP", "rr": "RR", "peep": "PEEP", "fio2": "FIO2", "ti": "TI", "trigger": "TRIG"}
COMMANDS = ("START", "STANDBY")
_FORBIDDEN = set(",*$\r\n")


class ProtocolError(ValueError):
    """A line that is not a valid protocol message."""


def checksum(body: str) -> str:
    value = 0
    for ch in body:
        value ^= ord(ch)
    return f"{value:02X}"


def _fmt(value) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        text = f"{value:.3f}".rstrip("0").rstrip(".")
        return text if text not in ("", "-0") else "0"
    text = str(value)
    if _FORBIDDEN & set(text):
        raise ProtocolError(f"field contains a reserved character: {text!r}")
    if not text.isascii():
        raise ProtocolError(f"field is not ASCII: {text!r}")
    return text


def encode(msg_type: str, *fields) -> str:
    body = ",".join([msg_type, *(_fmt(f) for f in fields)])
    return f"${body}*{checksum(body)}\n"


def decode(line: str) -> tuple[str, list[str]]:
    line = line.strip()
    if not line.startswith("$") or "*" not in line:
        raise ProtocolError(f"not a message: {line!r}")
    body, cs = line[1:].rsplit("*", 1)
    if cs.upper() != checksum(body):
        raise ProtocolError(f"bad checksum: {line!r}")
    parts = body.split(",")
    return parts[0], parts[1:]


# ----- MCU -> Pi ---------------------------------------------------------------------------------

def encode_sample(s: Sample) -> str:
    return encode("D", s.t_ms, float(s.pressure), float(s.flow), float(s.volume), s.phase)


def encode_status(m: MonitorStatus) -> str:
    return encode("M", float(m.fio2), float(m.battery_pct), "BAT" if m.on_battery else "AC",
                  "OK" if m.o2_supply_ok else "FAIL")


def encode_test_result(r: TestResult) -> str:
    return encode("R", r.test, "PASS" if r.passed else "FAIL", r.detail)


def encode_fault(f: Fault) -> str:
    return encode("F", f.code, f.active)


def encode_ack(a: Ack) -> str:
    return encode("K", a.command, "OK" if a.ok else "ERR", a.reason)


def encode_heartbeat(seq: int) -> str:
    return encode("H", seq)


def parse_mcu_message(line: str):
    """Turn one line from the MCU into Sample / MonitorStatus / TestResult / Fault / Ack / Heartbeat."""
    kind, f = decode(line)
    try:
        if kind == "D":
            if f[4] not in ("I", "E"):
                raise ValueError("phase must be I or E")
            return Sample(int(f[0]), float(f[1]), float(f[2]), float(f[3]), f[4])
        if kind == "M":
            return MonitorStatus(float(f[0]), float(f[1]), f[2] == "BAT", f[3] == "OK")
        if kind == "R":
            return TestResult(f[0], f[1] == "PASS", f[2] if len(f) > 2 else "")
        if kind == "F":
            return Fault(f[0], f[1] == "1")
        if kind == "K":
            return Ack(f[0], f[1] == "OK", f[2] if len(f) > 2 else "")
        if kind == "H":
            return Heartbeat(int(f[0]))
    except (IndexError, ValueError) as exc:
        raise ProtocolError(f"bad {kind} message: {line!r}") from exc
    raise ProtocolError(f"unknown message type {kind!r}")


# ----- Pi -> MCU ---------------------------------------------------------------------------------

def encode_setting(name: str, value) -> str:
    return encode("S", name, value)


def encode_settings(settings: VentSettings, pmax: float) -> list[str]:
    lines = [encode_setting("MODE", settings.mode.value)]
    lines += [encode_setting(SETTING_NAMES[k], float(settings.get(k))) for k in PARAM_KEYS]
    lines.append(encode_setting("PMAX", float(pmax)))
    return lines


def encode_command(cmd: str) -> str:
    if cmd not in COMMANDS:
        raise ProtocolError(f"unknown command {cmd!r}")
    return encode("C", cmd)


def encode_run_test(test: str) -> str:
    return encode("X", test)


def encode_buzzer(priority: int, paused: bool) -> str:
    return encode("B", int(priority), bool(paused))
