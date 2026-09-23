"""Screen-flow state machine: Patient -> Pre-use check -> Settings -> Ventilating. No Qt imports.

Back is allowed from Pre-use check and Settings. Standby returns from Ventilating to Settings.
Quick Start and Skip jump to Settings and mark the pre-use check as skipped.
"""
from __future__ import annotations

from enum import IntEnum


class Step(IntEnum):
    PATIENT = 1
    PRECHECK = 2
    SETTINGS = 3
    VENTILATING = 4


class InvalidTransition(RuntimeError):
    """Raised when a screen change is not allowed from the current step."""


class ScreenFlow:
    def __init__(self) -> None:
        self.step = Step.PATIENT
        self.precheck_passed = False
        self.precheck_skipped = False

    def _require(self, action: str, *allowed: Step) -> None:
        if self.step not in allowed:
            raise InvalidTransition(f"cannot {action} from {self.step.name}")

    def patient_done(self) -> None:
        self._require("continue", Step.PATIENT)
        self.step = Step.PRECHECK

    def quick_start(self) -> None:
        self._require("quick start", Step.PATIENT)
        self.precheck_skipped = True
        self.step = Step.SETTINGS

    def complete_precheck(self) -> None:
        self._require("complete the pre-use check", Step.PRECHECK)
        self.precheck_passed = True
        self.precheck_skipped = False
        self.step = Step.SETTINGS

    def skip_precheck(self) -> None:
        self._require("skip the pre-use check", Step.PRECHECK)
        self.precheck_skipped = True
        self.step = Step.SETTINGS

    def back(self) -> None:
        self._require("go back", Step.PRECHECK, Step.SETTINGS)
        self.step = Step(self.step - 1)

    def start_ventilation(self) -> None:
        self._require("start ventilation", Step.SETTINGS)
        self.step = Step.VENTILATING

    def standby(self) -> None:
        self._require("go to standby", Step.VENTILATING)
        self.step = Step.SETTINGS
