from hmi.core.alarms.definitions import Priority
from hmi.core.flow import Step
from hmi.model.patient import Category, height_spec
from hmi.model.settings import param_spec
from hmi.ui.dialogs.confirm import ConfirmDialog
from hmi.ui.dialogs.keyboard import KeyboardDialog
from hmi.ui.dialogs.value_adjust import ValueAdjustDialog
from hmi.ui.theme import apply_theme
from hmi.ui.widgets.inline_adjuster import InlineAdjuster
from hmi.ui.widgets.numeric_readout import NumericReadout
from hmi.ui.widgets.param_tile import ParamTile
from hmi.ui.widgets.step_indicator import StepIndicator
from hmi.ui.widgets.toggle_group import ToggleGroup


def test_toggle_group_emits_only_on_change(qapp):
    tg = ToggleGroup([("a", "A"), ("b", "B")], "a")
    seen = []
    tg.changed.connect(seen.append)
    tg.button("b").click()
    tg.button("b").click()
    assert seen == ["b"] and tg.value() == "b"


def test_inline_adjuster_clamps_to_range(qapp):
    adj = InlineAdjuster(height_spec(Category.ADULT), 209)
    seen = []
    adj.changed.connect(seen.append)
    adj.step(+1)
    adj.step(+1)
    assert adj.value() == 210 and seen == [210]


def test_param_tile_note(qapp):
    tile = ParamTile("VT", "mL")
    tile.set_value("460")
    tile.set_note("10.6 mL/kg IBW")
    assert tile.value_text() == "460" and tile.note_text() == "10.6 mL/kg IBW"
    tile.set_note(None)
    assert tile.note_text() == ""


def test_step_indicator_marks_done_steps(qapp):
    si = StepIndicator()
    si.set_step(Step.SETTINGS)
    assert si.text_of(Step.PATIENT).startswith("✔")
    assert si.text_of(Step.SETTINGS) == "3. Settings"


def test_step_indicator_marks_skipped_step(qapp):
    si = StepIndicator()
    si.set_step(Step.SETTINGS, skipped=frozenset({Step.PRECHECK}))
    assert si.text_of(Step.PRECHECK) == "✖ Pre-use check skipped"


def test_numeric_readout_alarm_state(qapp):
    r = NumericReadout("PIP", "cmH2O")
    r.set_value("45")
    r.set_limits(8, 40)
    r.set_alarm(Priority.HIGH)
    assert r.value_text() == "45" and r.alarm_priority is Priority.HIGH


def test_value_adjust_dialog_validates(qapp):
    spec = param_spec(Category.ADULT, "vt")
    dlg = ValueAdjustDialog(None, spec, 460, validator=lambda v: "too high" if v > 600 else None)
    dlg.step(10)
    assert dlg.value() == 560 and dlg.confirm_button.isEnabled()
    dlg.step(10)
    assert dlg.value() == 660 and not dlg.confirm_button.isEnabled() and dlg.error_text() == "too high"
    dlg.step(1000)
    assert dlg.value() == 1000


def test_keyboard_dialog_typing(qapp):
    kb = KeyboardDialog(None, "Name", "J")
    kb.type(".")
    kb.type("X")
    kb.backspace()
    assert kb.text() == "J."
    kb.clear()
    assert kb.text() == ""


def test_confirm_dialog_buttons(qapp):
    dlg = ConfirmDialog(None, "Title", "Text", confirm_text="Start", cancel_text=None)
    assert dlg.confirm_button.text() == "Start" and dlg.cancel_button is None


def test_primary_buttons_meet_minimum_tap_target(qapp):
    apply_theme(qapp)
    dlg = ConfirmDialog(None, "Title", "Text")
    dlg.confirm_button.ensurePolished()
    assert dlg.confirm_button.sizeHint().height() >= 56
