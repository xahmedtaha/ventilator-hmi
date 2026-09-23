import pytest

from hmi.device.messages import Fault, Heartbeat, MonitorStatus, Sample, TestResult
from hmi.device.protocol import (
    ProtocolError, checksum, decode, encode, encode_buzzer, encode_fault, encode_heartbeat,
    encode_sample, encode_settings, encode_status, encode_test_result, parse_mcu_message,
)
from hmi.model.settings import VentSettings


def test_checksum_is_xor_of_body():
    assert checksum("A") == "41"
    assert checksum("AB") == "03"


def test_encode_formats_numbers_compactly():
    assert encode("D", 12345, 18.2, 500.0, "I") == f"$D,12345,18.2,500,I*{checksum('D,12345,18.2,500,I')}\n"


@pytest.mark.parametrize("msg", [
    Sample(12345, 18.2, -32.5, 410.0, "E"),
    MonitorStatus(40.5, 87.0, False, True),
    MonitorStatus(21.0, 15.0, True, False),
    TestResult("LEAK", True, "Leak 45 mL/min (limit < 200)"),
    Fault("FLOW_SENSOR", True),
    Heartbeat(42),
])
def test_roundtrip_mcu_messages(msg):
    encoders = {
        Sample: encode_sample, MonitorStatus: encode_status, TestResult: encode_test_result,
        Fault: encode_fault, Heartbeat: lambda m: encode_heartbeat(m.seq),
    }
    assert parse_mcu_message(encoders[type(msg)](msg)) == msg


def test_bad_checksum_rejected():
    line = encode_heartbeat(1).replace("*", "*F")
    with pytest.raises(ProtocolError):
        decode(line)


@pytest.mark.parametrize("line", ["", "hello", "$H,1", "$Z,1*" + checksum("Z,1"), "$D,1,2*" + checksum("D,1,2")])
def test_garbage_rejected(line):
    with pytest.raises(ProtocolError):
        parse_mcu_message(line)


def test_fields_cannot_contain_separators():
    with pytest.raises(ProtocolError):
        encode("R", "LEAK", "PASS", "a,b")


@pytest.mark.parametrize("text", ["café", "leak · high", "10–20 mL"])  # accent, middle dot, en dash
def test_non_ascii_fields_rejected(text):
    with pytest.raises(ProtocolError):
        encode("R", "LEAK", "PASS", text)


def test_buzzer_command():
    assert encode_buzzer(3, False) == f"$B,3,0*{checksum('B,3,0')}\n"


def test_settings_are_sent_as_nine_lines_mode_first():
    lines = encode_settings(VentSettings(), pmax=40)
    assert len(lines) == 9
    assert lines[0].startswith("$S,MODE,VC*")
    assert lines[-1].startswith("$S,PMAX,40*")
