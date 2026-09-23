from hmi.device.simulator import SimulatedDevice
from hmi.model.settings import VentSettings


def collect(device, signal_name):
    items = []
    getattr(device, signal_name).connect(items.append)
    return items


def test_emits_samples_at_50_hz_and_status_at_1_hz(qapp):
    dev = SimulatedDevice(seed=1, sound=False)
    samples, statuses = collect(dev, "sample_received"), collect(dev, "status_received")
    for _ in range(100):
        dev.tick()
    assert len(samples) == 100 and len(statuses) == 2


def test_fio2_moves_toward_setting_while_ventilating(qapp):
    dev = SimulatedDevice(seed=1, sound=False)
    dev.apply_settings(VentSettings(fio2=60), 40)
    dev.start_ventilation()
    for _ in range(50 * 30):
        dev.tick()
    assert 55 < dev.fio2_measured < 60


def test_pre_use_tests_finish_after_their_duration(qapp):
    dev = SimulatedDevice(seed=1, sound=False)
    results = collect(dev, "test_finished")
    dev.run_test("LEAK")
    for _ in range(50 * 2):
        dev.tick()
    assert results == []
    for _ in range(50 * 2):
        dev.tick()
    assert len(results) == 1 and results[0].test == "LEAK" and results[0].passed
    assert "," not in results[0].detail


def test_forced_failure(qapp):
    dev = SimulatedDevice(seed=1, sound=False)
    results = collect(dev, "test_finished")
    dev.force_fail = "COMP"
    dev.run_test("COMP")
    for _ in range(50 * 4):
        dev.tick()
    assert not results[0].passed


def test_link_loss_stops_data_and_reports_link(qapp):
    dev = SimulatedDevice(seed=1, sound=False)
    samples, links = collect(dev, "sample_received"), collect(dev, "link_changed")
    dev.set_link_lost(True)
    for _ in range(10):
        dev.tick()
    assert samples == [] and links == [False]
    dev.reset_faults()
    assert links == [False, True]
