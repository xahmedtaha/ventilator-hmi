import math

from hmi.core.alarms.definitions import ALARMS
from hmi.core.alarms.engine import AlarmState
from hmi.device.messages import Sample
from hmi.ui.top_bar import TopBar
from hmi.ui.widgets.alarm_banner import AlarmBanner
from hmi.ui.widgets.waveform_panel import GAP_POINTS, POINTS, WaveformPanel


def test_waveform_sweeps_and_leaves_an_erase_gap(qapp):
    panel = WaveformPanel()
    for i in range(POINTS + 20):
        panel.add_sample(Sample(i * 20, 10.0, 5.0, 100.0, "I"))
    assert panel.index == 20
    pressure = panel.trace("pressure")
    assert all(math.isnan(v) for v in pressure[20:20 + GAP_POINTS])
    assert pressure[19] == 10.0
    panel.redraw()
    panel.clear()
    assert all(math.isnan(v) for v in panel.trace("volume"))


def test_banner_flashes_for_active_high_and_is_steady_when_resolved(qapp):
    banner = AlarmBanner()
    state = AlarmState(ALARMS["HIGH_PRESSURE"], onset=0.0, detail="45.0 > 40 cmH2O")
    banner.show_alarm(state, 2)
    assert banner.is_flashing() and banner.badge_text() == "+2"
    assert banner.message_text().startswith("!!! HIGH PRESSURE")
    state.active = False
    banner.show_alarm(state, 0)
    assert not banner.is_flashing() and banner.badge_text() == ""
    banner.show_alarm(None, 0)
    assert banner.message_text() == "No active alarms"


def test_low_priority_banner_is_steady(qapp):
    banner = AlarmBanner()
    banner.show_alarm(AlarmState(ALARMS["NO_PRECHECK"], onset=0.0), 0)
    assert not banner.is_flashing()


def test_top_bar_audio_pause_countdown(qapp):
    bar = TopBar()
    bar.set_audio_paused(103)
    assert "1:43" in bar.audio_pause_text()
    bar.set_audio_paused(None)
    assert "1:43" not in bar.audio_pause_text()
