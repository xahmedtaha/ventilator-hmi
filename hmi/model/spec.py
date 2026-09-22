"""NumericSpec: the range, step and display format of one adjustable number.

Ventilation settings, alarm limits and patient height/age all use it, so every number the operator
can change is validated and displayed the same way. No Qt imports.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NumericSpec:
    key: str
    label: str
    unit: str
    minimum: float
    maximum: float
    step: float
    decimals: int = 0

    def clamp(self, value: float) -> float:
        """Snap `value` to the nearest step (counted from `minimum`) and keep it inside the range."""
        steps = round((value - self.minimum) / self.step)
        snapped = self.minimum + steps * self.step
        snapped = min(max(snapped, self.minimum), self.maximum)
        return round(snapped, 6)

    def fmt(self, value: float) -> str:
        return f"{value:.{self.decimals}f}"

    def range_text(self) -> str:
        return f"{self.fmt(self.minimum)}–{self.fmt(self.maximum)} {self.unit}"
