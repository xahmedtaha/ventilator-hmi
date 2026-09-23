import pytest

from hmi.core.breath_analyzer import MAX_BREATH_SAMPLES, BreathAnalyzer
from hmi.device.lung_model import LungSimulator
from hmi.device.messages import Sample
from hmi.model.settings import VentSettings


def run(seconds, start=True):
    sim = LungSimulator(noise=0.0)
    sim.apply(VentSettings(vt=500, rr=15, ti=1.0, peep=5))
    if start:
        sim.start()
    analyzer = BreathAnalyzer()
    results = []
    for _ in range(int(round(seconds / 0.02))):
        r = analyzer.add(sim.step(0.02))
        if r:
            results.append(r)
    return results


def test_one_result_per_completed_breath():
    assert len(run(39.0)) == 9  # breaths start at 0, 4, ..., 36 s


def test_measurements_match_the_lung_model():
    r = run(40.0)[-1]
    assert r.pip == pytest.approx(20, abs=0.3)
    assert r.peep == pytest.approx(5, abs=0.1)
    assert r.vti == pytest.approx(500, abs=5)
    assert r.vte == pytest.approx(500, abs=10)
    assert r.ti == pytest.approx(1.0) and r.te == pytest.approx(3.0)
    assert r.rr == pytest.approx(15, abs=0.1)
    assert r.mve == pytest.approx(7.5, abs=0.2)
    assert r.ie_text == "1:3.0"
    assert r.peep < r.pmean < r.pip


def test_standby_samples_give_no_breaths():
    assert run(10.0, start=False) == []


def test_runaway_breath_is_capped_and_discarded():
    """A breath that never returns to I (stuck phase / fault) must not grow forever."""
    analyzer = BreathAnalyzer()
    analyzer.add(Sample(0, 10.0, 30.0, 0.0, "I"))
    for i in range(1, MAX_BREATH_SAMPLES + 10):
        result = analyzer.add(Sample(i * 20, 5.0, -10.0, 0.0, "E"))
        assert result is None
    assert analyzer._samples == []
    assert analyzer._started is False
    # The next breath starts and finishes normally.
    analyzer.add(Sample(1_000_000, 10.0, 30.0, 0.0, "I"))
    for i in range(1, 51):
        analyzer.add(Sample(1_000_000 + i * 20, 5.0, -10.0, 0.0, "E"))
    result = analyzer.add(Sample(2_000_000, 10.0, 30.0, 0.0, "I"))
    assert result is not None
