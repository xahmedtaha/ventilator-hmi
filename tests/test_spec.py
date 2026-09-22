from hmi.model.spec import NumericSpec

VT = NumericSpec("vt", "VT", "mL", 200, 1000, 10)
TI = NumericSpec("ti", "Ti", "s", 0.3, 1.5, 0.1, 1)


def test_clamp_snaps_to_step():
    assert VT.clamp(503) == 500
    assert VT.clamp(506) == 510


def test_clamp_keeps_value_in_range():
    assert VT.clamp(1200) == 1000
    assert VT.clamp(10) == 200
    assert TI.clamp(0.34) == 0.3


def test_format_uses_decimals():
    assert VT.fmt(500) == "500"
    assert TI.fmt(0.7) == "0.7"
    assert VT.range_text() == "200–1000 mL"
