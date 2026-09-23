import pytest

from hmi.core.alarms.definitions import ALARMS, Priority
from hmi.core.alarms.engine import AlarmEngine, AlarmEvent
from hmi.core.breath_analyzer import BreathResult
from hmi.device.messages import MonitorStatus, Sample
from hmi.model.alarm_limits import AlarmLimits
from hmi.model.patient import PatientProfile
from hmi.model.settings import VentSettings

PATIENT = PatientProfile(height_cm=170)  # limits: Ppeak 8-40, Vte 260-660, MVe 3-15, RR 35, apnea 20


def make_engine(ventilating_at=0.0):
    e = AlarmEngine(VentSettings.defaults_for(PATIENT), AlarmLimits.defaults_for(PATIENT))
    if ventilating_at is not None:
        e.set_ventilating(True, ventilating_at)
    return e


def breath(**kw):
    values = dict(end_t_ms=0, pip=20.0, peep=5.0, pmean=9.0, vti=460.0, vte=460.0,
                  ti=1.0, te=3.3, rr=14.0, mve=6.4)
    values.update(kw)
    return BreathResult(**values)


def sample(p):
    return Sample(0, p, 0.0, 0.0, "I")


def status(fio2=40.0, battery=100.0, on_battery=False, o2_ok=True):
    return MonitorStatus(fio2, battery, on_battery, o2_ok)


def ids(e):
    return [s.id for s in e.alarms()]


def test_definitions_cover_the_spec_and_only_high_priority_latches():
    assert set(ALARMS) == {
        "HIGH_PRESSURE", "LOW_PRESSURE", "SUSTAINED_PRESSURE", "APNEA", "LOW_FIO2", "HIGH_FIO2",
        "LOW_VTE", "HIGH_VTE", "LOW_MVE", "HIGH_MVE", "HIGH_RR", "LOW_PEEP", "HIGH_PEEP",
        "O2_SUPPLY", "LINK_LOST", "DEVICE_FAULT", "ON_BATTERY", "BATTERY_LOW", "BATTERY_DEPLETED",
        "NO_PRECHECK",
    }
    assert all(d.latching == (d.priority is Priority.HIGH) for d in ALARMS.values())


def test_physiological_alarms_ignored_in_standby():
    e = make_engine(ventilating_at=None)
    e.on_breath(breath(pip=2), 1)
    e.on_breath(breath(pip=2), 2)
    assert ids(e) == []


def test_high_pressure_is_immediate_and_latches_until_reset():
    e = make_engine()
    e.on_sample(sample(45.0), 1.0)
    top = e.alarms()[0]
    assert top.id == "HIGH_PRESSURE" and top.active and top.priority is Priority.HIGH
    assert top.message.startswith("!!! HIGH PRESSURE")
    e.on_breath(breath(pip=20), 5.0)
    top = e.alarms()[0]
    assert not top.active and "(resolved)" in top.message
    assert e.audible_priority() is Priority.NONE
    e.reset(6.0)
    assert ids(e) == []


def test_low_pressure_needs_two_breaths():
    e = make_engine()
    e.on_breath(breath(pip=2), 1)
    assert ids(e) == []
    e.on_breath(breath(pip=2), 5)
    assert ids(e) == ["LOW_PRESSURE"]


def test_low_vte_needs_three_breaths_and_clears_by_itself():
    e = make_engine()
    e.on_breath(breath(vte=100), 31)
    e.on_breath(breath(vte=100), 35)
    assert ids(e) == []
    e.on_breath(breath(vte=100), 39)
    assert ids(e) == ["LOW_VTE"]
    e.on_breath(breath(), 43)
    assert ids(e) == []


def test_grace_period_suppresses_volume_alarms():
    e = make_engine()
    for t in (1, 5, 9, 13):
        e.on_breath(breath(vte=100), t)
    assert ids(e) == []


def test_minute_volume_needs_ten_seconds():
    e = make_engine()
    for t in (31, 35, 40):
        e.on_breath(breath(mve=1.0), t)
    assert ids(e) == []
    e.on_breath(breath(mve=1.0), 41.5)
    assert ids(e) == ["LOW_MVE"]


def test_alarms_sorted_by_priority():
    e = make_engine()
    e.set_condition("NO_PRECHECK", True, 1)
    e.on_sample(sample(45.0), 2)
    assert ids(e) == ["HIGH_PRESSURE", "NO_PRECHECK"]
    assert e.audible_priority() is Priority.HIGH


def test_audio_pause_lasts_120_seconds():
    e = make_engine()
    e.on_sample(sample(45.0), 1)
    e.audio_pause(10)
    assert e.audio_paused(100)
    assert e.audio_pause_remaining(100) == pytest.approx(30)
    e.tick(130.5)
    assert not e.audio_paused(130.5)


def test_new_alarm_ends_audio_pause():
    e = make_engine()
    e.on_sample(sample(45.0), 1)
    e.audio_pause(10)
    e.set_condition("NO_PRECHECK", True, 20)
    assert not e.audio_paused(21)


def test_standby_clears_physiological_but_keeps_technical():
    e = make_engine()
    e.on_sample(sample(45.0), 1)
    e.set_condition("LINK_LOST", True, 1)
    e.set_ventilating(False, 2)
    assert ids(e) == ["LINK_LOST"]


def test_standby_logs_alarm_off_for_active_physiological_alarms():
    e = make_engine()
    e.on_sample(sample(45.0), 1)  # HIGH_PRESSURE, still active (not resolved)
    e.drain_events()
    e.set_ventilating(False, 2)
    events = [ev for ev in e.drain_events() if ev.kind == "ALARM_OFF"]
    assert events == [AlarmEvent("ALARM_OFF", "HIGH_PRESSURE", "HIGH", "45.0 > 40 cmH2O")]


def test_apnea_after_apnea_time():
    e = make_engine(0)
    e.tick(19)
    assert ids(e) == []
    e.tick(21)
    assert ids(e) == ["APNEA"]
    e.on_breath(breath(), 22)
    e.tick(22.2)
    assert not e.alarms()[0].active


def test_battery_shows_only_the_most_severe():
    e = make_engine()
    e.on_status(status(battery=50, on_battery=True), 1)
    assert ids(e) == ["ON_BATTERY"]
    e.on_status(status(battery=15, on_battery=True), 2)
    assert ids(e) == ["BATTERY_LOW"]
    e.on_status(status(battery=3, on_battery=True), 3)
    assert ids(e) == ["BATTERY_DEPLETED"]


def test_low_fio2_needs_30_seconds_after_grace():
    e = make_engine()
    e.on_status(status(fio2=30), 31)
    e.on_status(status(fio2=30), 60)
    assert ids(e) == []
    e.on_status(status(fio2=30), 61.5)
    assert ids(e) == ["LOW_FIO2"]


def test_sustained_pressure_must_be_continuous():
    e = make_engine()
    t = 0.0
    while t <= 14.0:
        e.on_sample(sample(25.0), t)
        t += 0.5
    e.on_sample(sample(18.0), 14.5)
    t = 15.0
    while t <= 29.5:
        e.on_sample(sample(25.0), t)
        t += 0.5
    assert ids(e) == []
    e.on_sample(sample(25.0), 30.0)
    assert ids(e) == ["SUSTAINED_PRESSURE"]


def test_events_are_recorded_once():
    e = make_engine()
    e.on_sample(sample(45.0), 1)
    e.on_breath(breath(), 5)
    e.reset(6)
    assert [ev.kind for ev in e.drain_events()] == ["ALARM_ON", "ALARM_OFF", "ALARM_RESET"]
    assert e.drain_events() == []


def test_readout_priorities_color_the_measured_values():
    e = make_engine()
    e.on_sample(sample(45.0), 1)
    assert e.readout_priorities() == {"pip": Priority.HIGH}
