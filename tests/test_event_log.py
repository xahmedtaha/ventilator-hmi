import json
from datetime import datetime

from hmi.core.alarms.event_log import EventLog, describe


def clock():
    return datetime(2026, 9, 22, 12, 0, 5)


def test_entries_are_written_as_json_lines(tmp_path):
    log = EventLog(tmp_path, clock=clock)
    log.add("ALARM_ON", alarm_id="LOW_VTE", priority="MEDIUM", detail="100 < 260 mL")
    log.add("SETTING", key="vt", old=460, new=500)
    lines = (tmp_path / "events-2026-09-22.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["kind"] for line in lines] == ["ALARM_ON", "SETTING"]
    assert json.loads(lines[0])["time"] == "2026-09-22T12:00:05"


def test_recent_is_newest_first_and_bounded():
    log = EventLog(None, max_recent=2, clock=clock)
    for n in range(3):
        log.add("TEST", n=n)
    assert [e["n"] for e in log.recent()] == [2, 1]


def test_unwritable_directory_keeps_log_in_memory(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    log = EventLog(blocker / "sub", clock=clock)  # parent is a file: directory cannot be created
    log.add("TEST")
    assert len(log.recent()) == 1


def test_describe_is_human_readable():
    assert describe({"time": "t", "kind": "SETTING", "key": "vt", "old": 460, "new": 500}) == "vt: 460 → 500"
    assert describe({"time": "t", "kind": "ALARM_ON", "alarm_id": "LOW_VTE", "priority": "MEDIUM",
                     "detail": "100 < 260 mL"}) == "LOW_VTE (medium) 100 < 260 mL"
