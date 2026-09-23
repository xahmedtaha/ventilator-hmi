import pytest

from hmi.core.alarms.engine import AlarmEngine
from hmi.core.breath_analyzer import BreathAnalyzer
from hmi.device.simulator import SimulatedDevice
from hmi.model.alarm_limits import AlarmLimits
from hmi.model.patient import PatientProfile
from hmi.model.settings import Mode, VentSettings


def run_scenario(inject, seconds, mode=Mode.VC):
    patient = PatientProfile()
    settings = VentSettings.defaults_for(patient).with_mode(mode)
    limits = AlarmLimits.defaults_for(patient)
    dev = SimulatedDevice(seed=7, sound=False)
    dev.apply_settings(settings, limits.ppeak_high)
    engine, analyzer = AlarmEngine(settings, limits), BreathAnalyzer()

    def on_sample(s):
        engine.on_sample(s, dev.sim_time)
        result = analyzer.add(s)
        if result:
            engine.on_breath(result, dev.sim_time)

    dev.sample_received.connect(on_sample)
    dev.status_received.connect(lambda m: engine.on_status(m, dev.sim_time))
    dev.link_changed.connect(lambda ok: engine.set_condition("LINK_LOST", not ok, dev.sim_time))
    dev.start_ventilation()
    engine.set_ventilating(True, dev.sim_time)

    def advance(duration):
        for _ in range(int(duration / 0.02)):
            dev.tick()
            engine.tick(dev.sim_time)

    advance(40)
    baseline = {s.id for s in engine.alarms()}
    inject(dev)
    advance(seconds)
    return baseline, {s.id for s in engine.alarms()}


def set_fault(name, value):
    return lambda dev: setattr(dev.lung.faults, name, value)


@pytest.mark.parametrize("inject, seconds, mode, expected", [
    (set_fault("disconnected", True), 40, Mode.VC, {"LOW_PRESSURE", "LOW_VTE", "LOW_MVE"}),
    (set_fault("occluded", True), 30, Mode.VC, {"HIGH_PRESSURE", "SUSTAINED_PRESSURE", "LOW_VTE"}),
    (set_fault("occluded", True), 40, Mode.PC, {"LOW_VTE", "LOW_MVE"}),
    (set_fault("leak_fraction", 0.5), 30, Mode.VC, {"LOW_VTE", "LOW_PEEP"}),
    (set_fault("stiff", True), 20, Mode.VC, {"HIGH_PRESSURE"}),
    (set_fault("stiff", True), 30, Mode.PC, {"LOW_VTE"}),
    (set_fault("patient_rate", 40), 40, Mode.VC, {"HIGH_RR", "HIGH_MVE"}),
    (lambda dev: dev.set_o2_supply(False), 45, Mode.VC, {"O2_SUPPLY", "LOW_FIO2"}),
    (lambda dev: dev.set_battery_mode(True), 50, Mode.VC, {"BATTERY_DEPLETED"}),
    (lambda dev: dev.set_link_lost(True), 25, Mode.VC, {"LINK_LOST", "APNEA"}),
])
def test_demo_fault_raises_expected_alarms(qapp, inject, seconds, mode, expected):
    baseline, raised = run_scenario(inject, seconds, mode)
    assert baseline == set()
    assert expected <= raised
