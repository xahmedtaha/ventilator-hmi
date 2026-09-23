"""Event log: alarms, setting changes and operator actions, saved as JSON Lines. No Qt imports.

One JSON object per line in <directory>/events-YYYY-MM-DD.jsonl, so the log survives restarts and
can be opened in any text editor. If the file cannot be written, the HMI keeps running and the log
stays in memory.
"""
from __future__ import annotations

import json
import sys
from collections import deque
from datetime import datetime
from pathlib import Path

DEFAULT_LOG_DIR = Path.home() / ".ventilator-hmi" / "logs"


class EventLog:
    def __init__(self, directory: Path | None = DEFAULT_LOG_DIR, max_recent: int = 500,
                 clock=datetime.now):
        self.directory = Path(directory) if directory is not None else None
        self._recent: deque[dict] = deque(maxlen=max_recent)
        self._clock = clock
        self._write_failed = False

    @property
    def path(self) -> Path | None:
        if self.directory is None:
            return None
        return self.directory / f"events-{self._clock():%Y-%m-%d}.jsonl"

    def add(self, kind: str, **fields) -> dict:
        entry = {"time": self._clock().isoformat(timespec="seconds"), "kind": kind, **fields}
        self._recent.append(entry)
        self._write(entry)
        return entry

    def recent(self) -> list[dict]:
        return list(reversed(self._recent))

    def _write(self, entry: dict) -> None:
        path = self.path
        if path is None or self._write_failed:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            self._write_failed = True
            print(f"[event log] cannot write {path}: {exc}; keeping the log in memory only", file=sys.stderr)


def describe(entry: dict) -> str:
    """One-line human description of a log entry (used by the Log tab)."""
    fields = {k: v for k, v in entry.items() if k not in ("time", "kind")}
    if entry.get("kind") in ("ALARM_ON", "ALARM_OFF"):
        text = f"{fields.get('alarm_id', '')} ({str(fields.get('priority', '')).lower()}) {fields.get('detail', '')}"
        return text.strip()
    if {"key", "old", "new"} <= fields.keys():
        return f"{fields['key']}: {fields['old']} → {fields['new']}"
    return " · ".join(f"{k}={v}" for k, v in fields.items() if v not in ("", None))
