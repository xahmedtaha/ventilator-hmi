import glob
import io
import tempfile
import wave

import pytest

from hmi.core.alarms.definitions import Priority
from hmi.device.buzzer_sound import BURSTS, BuzzerSound, render_wav


def test_burst_pulse_counts_follow_iec_60601_1_8():
    assert len(BURSTS[Priority.HIGH]) == 10
    assert len(BURSTS[Priority.MEDIUM]) == 3
    assert len(BURSTS[Priority.LOW]) == 1


def test_rendered_wav_has_the_pattern_duration():
    pattern = BURSTS[Priority.MEDIUM]
    with wave.open(io.BytesIO(render_wav(pattern))) as w:
        seconds = w.getnframes() / w.getframerate()
        assert w.getnchannels() == 1
    assert seconds == pytest.approx(sum(on + off for on, off in pattern), abs=0.01)


def test_state_text_follows_priority_and_pause(qapp):
    b = BuzzerSound(enabled=False)
    b.update(Priority.HIGH, False)
    assert b.state_text == "HIGH burst every 5 s"
    b.update(Priority.HIGH, True)
    assert b.state_text == "silent (audio paused)"
    b.update(Priority.NONE, False)
    assert b.state_text == "silent"
    b.shutdown()


def test_disabled_buzzer_creates_no_temp_directory(qapp):
    pattern = tempfile.gettempdir() + "/vent-hmi-buzzer-*"
    before = len(glob.glob(pattern))
    b = BuzzerSound(enabled=False)
    after = len(glob.glob(pattern))
    assert after == before
    b.shutdown()
    assert len(glob.glob(pattern)) == before
