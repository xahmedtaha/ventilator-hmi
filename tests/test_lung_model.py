import math

import pytest

from hmi.device.lung_model import LungSimulator
from hmi.model.settings import Mode, VentSettings

DT = 0.02


def run(sim, seconds):
    return [sim.step(DT) for _ in range(int(round(seconds / DT)))]


def make(settings, **faults):
    sim = LungSimulator(noise=0.0)
    for name, value in faults.items():
        setattr(sim.faults, name, value)
    sim.apply(settings, pmax=40)
    sim.start()
    return sim


def breath_starts(samples):
    return [i for i in range(1, len(samples)) if samples[i].phase == "I" and samples[i - 1].phase == "E"]


def test_vc_delivers_set_volume_with_expected_pip():
    samples = run(make(VentSettings(vt=500, rr=15, ti=1.0, peep=5)), 20)
    window = samples[600:800]  # one full 4 s breath
    assert max(s.volume for s in window) == pytest.approx(500, abs=2)
    assert max(s.pressure for s in window) == pytest.approx(20, abs=0.3)  # PEEP + V/C + R*flow


def test_pc_holds_pressure_and_volume_follows_lungs():
    samples = run(make(VentSettings(mode=Mode.PC, pinsp=15, peep=5, rr=15, ti=1.0)), 20)
    window = samples[600:800]
    assert all(s.pressure == pytest.approx(20) for s in window if s.phase == "I")
    assert max(s.volume for s in window) == pytest.approx(750 * (1 - math.exp(-2)), abs=5)


def test_expiration_follows_time_constant():
    sim = make(VentSettings(vt=500, rr=15, ti=1.0, peep=5))
    samples = run(sim, 20)
    first_e = next(i for i in range(600, 800) if samples[i].phase == "E")
    v0 = samples[first_e - 1].volume
    after_tau = samples[first_e - 1 + int(round(sim.tau / DT))].volume
    assert after_tau == pytest.approx(v0 * math.exp(-1), abs=3)


def test_disconnection_gives_no_pressure_and_no_expired_flow():
    samples = run(make(VentSettings(), disconnected=True), 8)
    assert max(s.pressure for s in samples) < 1
    assert min(s.flow for s in samples) >= 0


def test_expiratory_occlusion_keeps_pressure_high_in_vc():
    samples = run(make(VentSettings(vt=500, rr=15, ti=1.0), occluded=True), 20)
    assert min(s.pressure for s in samples[-250:]) > 20
    assert max(s.pressure for s in samples) > 40


def test_stiff_lungs_hit_the_pressure_limit_in_vc():
    samples = run(make(VentSettings(vt=500, rr=15, ti=1.0), stiff=True), 8)
    assert 40 < max(s.pressure for s in samples) < 42


def test_leak_halves_expired_volume_and_drops_peep():
    samples = run(make(VentSettings(vt=500, rr=15, ti=1.0, peep=5), leak_fraction=0.5), 20)
    last_e = samples[798]
    assert last_e.phase == "E"
    assert last_e.volume == pytest.approx(250, abs=10)
    assert last_e.pressure == pytest.approx(1.25, abs=0.01)


def test_patient_effort_triggers_extra_breaths():
    samples = run(make(VentSettings(rr=14, ti=1.0), patient_rate=40), 30)
    assert 17 <= len(breath_starts(samples)) <= 21


def test_standby_outputs_zero():
    sim = LungSimulator(noise=0.0)
    samples = run(sim, 2)
    assert all(s.pressure == 0 and s.flow == 0 and s.phase == "E" for s in samples)
