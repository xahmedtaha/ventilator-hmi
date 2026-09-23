"""Plays IEC 60601-1-8 style alarm bursts on the computer speaker. Demo only.

On the real ventilator the MCU drives a buzzer; this class imitates it so the demo can be heard.
Timings approximate IEC 60601-1-8:
  HIGH   10 pulses  x-x-x--x-x  pause  x-x-x--x-x   repeated every 5 s
  MEDIUM  3 pulses  x-x-x                           repeated every 10 s
  LOW     1 pulse                                   once
Tone: 523 Hz fundamental plus harmonics (the standard asks for at least 4 harmonics).
Windows plays through `winsound`; Linux/Raspberry Pi through `aplay`. Without either, it is silent.
"""
from __future__ import annotations

import io
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from functools import lru_cache
from pathlib import Path

from hmi.core.alarms.definitions import Priority
from hmi.qt import QtCore

TONE_HZ = 523.0
SAMPLE_RATE = 22050
FADE_SAMPLES = 220  # 10 ms fade in/out avoids clicks


def _high_group(gap_after: float) -> list[tuple[float, float]]:
    return [(0.15, 0.10), (0.15, 0.10), (0.15, 0.35), (0.15, 0.10), (0.15, gap_after)]


BURSTS: dict[Priority, list[tuple[float, float]]] = {
    Priority.HIGH: _high_group(0.8) + _high_group(0.0),
    Priority.MEDIUM: [(0.2, 0.2), (0.2, 0.2), (0.2, 0.0)],
    Priority.LOW: [(0.25, 0.0)],
}
REPEAT_S: dict[Priority, float | None] = {Priority.HIGH: 5.0, Priority.MEDIUM: 10.0, Priority.LOW: None}


def render_wav(pattern: list[tuple[float, float]]) -> bytes:
    """Render (pulse_seconds, silence_after_seconds) pairs to a 16-bit mono WAV file in memory."""
    frames = bytearray()
    for on, off in pattern:
        n_on = int(on * SAMPLE_RATE)
        for i in range(n_on):
            t = i / SAMPLE_RATE
            envelope = min(1.0, i / FADE_SAMPLES, (n_on - i) / FADE_SAMPLES)
            value = sum(math.sin(2 * math.pi * TONE_HZ * k * t) / k for k in range(1, 6))
            frames += struct.pack("<h", int(value * envelope * 9000))
        frames += b"\x00\x00" * int(off * SAMPLE_RATE)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(frames))
    return buffer.getvalue()


@lru_cache(maxsize=None)
def _rendered(priority: Priority) -> bytes:
    return render_wav(BURSTS[priority])


class _Player:
    """Plays one WAV file asynchronously; stop() cuts it off."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._winsound = None
        if sys.platform.startswith("win"):
            import winsound

            self._winsound = winsound
            self.available = True
        else:
            self.available = shutil.which("aplay") is not None

    def play(self, path: Path) -> None:
        if not self.available:
            return
        self.stop()
        try:
            if self._winsound:
                self._winsound.PlaySound(str(path), self._winsound.SND_FILENAME | self._winsound.SND_ASYNC)
            else:
                self._proc = subprocess.Popen(["aplay", "-q", str(path)],
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, RuntimeError):
            self.available = False

    def stop(self) -> None:
        if self._winsound:
            self._winsound.PlaySound(None, 0)
        elif self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None


class BuzzerSound(QtCore.QObject):
    def __init__(self, parent: QtCore.QObject | None = None, enabled: bool = True):
        super().__init__(parent)
        self._dir: Path | None = None
        self._files: dict[Priority, Path] = {}
        if enabled:
            self._dir = Path(tempfile.mkdtemp(prefix="vent-hmi-buzzer-"))
            for priority in BURSTS:
                path = self._dir / f"{priority.name.lower()}.wav"
                path.write_bytes(_rendered(priority))
                self._files[priority] = path
        self._player = _Player() if enabled else None
        self._priority = Priority.NONE
        self._paused = False
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._play_current)
        self.state_text = "silent"

    @property
    def available(self) -> bool:
        return self._player is not None and self._player.available

    def update(self, priority: int, paused: bool) -> None:
        priority = Priority(priority)
        if (priority, paused) == (self._priority, self._paused):
            return
        rising = priority > self._priority
        self._priority, self._paused = priority, paused
        self._timer.stop()
        if paused or priority is Priority.NONE:
            self._stop()
            self.state_text = "silent (audio paused)" if paused and priority else "silent"
            return
        repeat = REPEAT_S[priority]
        if repeat:
            self._play_current()
            self._timer.start(int(repeat * 1000))
            self.state_text = f"{priority.name} burst every {repeat:.0f} s"
        else:
            if rising:
                self._play_current()
            self.state_text = f"{priority.name} burst (once)"

    def play_test(self) -> None:
        """Alarm test during the pre-use check: one high-priority burst."""
        if self._player:
            self._player.play(self._files[Priority.HIGH])

    def shutdown(self) -> None:
        self._timer.stop()
        self._stop()
        if self._dir is not None:
            shutil.rmtree(self._dir, ignore_errors=True)

    def _play_current(self) -> None:
        if self._player and self._priority in self._files:
            self._player.play(self._files[self._priority])

    def _stop(self) -> None:
        if self._player:
            self._player.stop()
