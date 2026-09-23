"""Screen 1 — Patient Profile.

The operator picks Adult/Pediatric, sex and height; the screen shows the Ideal Body Weight (IBW),
its formula and the suggested tidal volume (6-8 mL/kg IBW). Name, ID and age are optional.
Quick Start skips the pre-use check (with confirmation, handled by the main window).
"""
from __future__ import annotations

from dataclasses import replace

from hmi.model.patient import AGE_SPEC, DEFAULT_HEIGHT, Category, PatientProfile, Sex, height_spec
from hmi.qt import QtWidgets, Signal
from hmi.ui.dialogs.keyboard import KeyboardDialog
from hmi.ui.dialogs.value_adjust import ValueAdjustDialog
from hmi.ui.theme import make_button, make_card, make_label
from hmi.ui.widgets.inline_adjuster import InlineAdjuster
from hmi.ui.widgets.toggle_group import ToggleGroup

FIELD_STYLE = "text-align: left; padding-left: 16px; font-size: 18px;"


class PatientScreen(QtWidgets.QWidget):
    next_requested = Signal()
    quick_start_requested = Signal()

    def __init__(self):
        super().__init__()
        self._profile = PatientProfile()
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(16)

        header = QtWidgets.QHBoxLayout()
        header.addWidget(make_label("Patient profile", 28, bold=True))
        header.addStretch(1)
        quick = make_button("Quick start", "danger")
        quick.setMinimumWidth(200)
        quick.clicked.connect(self.quick_start_requested.emit)
        header.addWidget(quick)
        root.addLayout(header)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(16)
        form_card = make_card()
        form = QtWidgets.QGridLayout(form_card)
        form.setContentsMargins(20, 20, 20, 20)
        form.setVerticalSpacing(14)
        form.setHorizontalSpacing(16)
        self.category = ToggleGroup([(c.value, c.title) for c in Category], Category.ADULT.value)
        self.sex = ToggleGroup([(Sex.MALE.value, "Male"), (Sex.FEMALE.value, "Female")], Sex.MALE.value)
        self.height_adjuster = InlineAdjuster(height_spec(Category.ADULT), DEFAULT_HEIGHT[Category.ADULT])
        self._name_button = make_button("")
        self._id_button = make_button("")
        self._age_button = make_button("")
        for button in (self._name_button, self._id_button, self._age_button):
            button.setStyleSheet(FIELD_STYLE)
            button.setMinimumWidth(320)
        rows = (("Category", self.category), ("Sex", self.sex), ("Height", self.height_adjuster),
                ("Name", self._name_button), ("Patient ID", self._id_button), ("Age", self._age_button))
        for r, (label, widget) in enumerate(rows):
            form.addWidget(make_label(label, 17, muted=True), r, 0)
            form.addWidget(widget, r, 1)
        body.addWidget(form_card, 3)

        info_card = make_card()
        info = QtWidgets.QVBoxLayout(info_card)
        info.setContentsMargins(24, 20, 24, 20)
        info.addWidget(make_label("Ideal body weight (IBW)", 18, muted=True))
        self._ibw = make_label("", 56, bold=True)
        self._formula = make_label("", 14, muted=True)
        info.addWidget(self._ibw)
        info.addWidget(self._formula)
        info.addSpacing(18)
        info.addWidget(make_label("Suggested tidal volume (6–8 mL/kg IBW)", 18, muted=True))
        self._vt = make_label("", 34, bold=True)
        self._vt_note = make_label("", 14, muted=True)
        info.addWidget(self._vt)
        info.addWidget(self._vt_note)
        info.addStretch(1)
        body.addWidget(info_card, 2)
        root.addLayout(body, 1)

        footer = QtWidgets.QHBoxLayout()
        footer.addStretch(1)
        next_button = make_button("Next  →", "primary")
        next_button.setMinimumWidth(220)
        next_button.clicked.connect(self.next_requested.emit)
        footer.addWidget(next_button)
        root.addLayout(footer)

        self.category.changed.connect(self._on_category)
        self.sex.changed.connect(lambda key: self._update(sex=Sex(key)))
        self.height_adjuster.changed.connect(lambda value: self._update(height_cm=int(value)))
        self._name_button.clicked.connect(self._edit_name)
        self._id_button.clicked.connect(self._edit_id)
        self._age_button.clicked.connect(self._edit_age)
        self._refresh()

    def profile(self) -> PatientProfile:
        return self._profile

    def set_profile(self, profile: PatientProfile) -> None:
        self._profile = profile
        self.category.set_value(profile.category.value)
        self.sex.set_value(profile.sex.value)
        self.height_adjuster.set_spec(height_spec(profile.category), profile.height_cm)
        self._refresh()

    def ibw_text(self) -> str:
        return self._ibw.text()

    def _update(self, **changes) -> None:
        self._profile = replace(self._profile, **changes)
        self._refresh()

    def _on_category(self, key: str) -> None:
        category = Category(key)
        height = DEFAULT_HEIGHT[category]
        self.height_adjuster.set_spec(height_spec(category), height)
        self._update(category=category, height_cm=height)

    def _edit_name(self) -> None:
        text = KeyboardDialog.ask(self, "Patient name", self._profile.name)
        if text is not None:
            self._update(name=text)

    def _edit_id(self) -> None:
        text = KeyboardDialog.ask(self, "Patient ID", self._profile.patient_id)
        if text is not None:
            self._update(patient_id=text)

    def _edit_age(self) -> None:
        start = self._profile.age_years
        if start is None:
            start = 40 if self._profile.category is Category.ADULT else 8
        value = ValueAdjustDialog.ask(self, AGE_SPEC, start, title="Age")
        if value is not None:
            self._update(age_years=int(value))

    def _refresh(self) -> None:
        p = self._profile
        self._ibw.setText(f"{p.ibw_kg:.1f} kg")
        self._formula.setText(p.ibw_formula_text())
        low, high = p.suggested_vt_range()
        self._vt.setText(f"{low}–{high} mL")
        self._vt_note.setText(f"Default VT = 7 mL/kg IBW = {p.default_vt():.0f} mL")
        self._name_button.setText(p.name or "Tap to enter (optional)")
        self._id_button.setText(p.patient_id or "Tap to enter (optional)")
        self._age_button.setText(f"{p.age_years} years" if p.age_years is not None else "Tap to set (optional)")
