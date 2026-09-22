"""Patient profile and Ideal Body Weight (IBW).

IBW formulas:
- Adults (ARDSNet): male 50 + 0.91 x (height_cm - 152.4); female 45.5 + 0.91 x (height_cm - 152.4)
- Pediatric (Traub & Kichen, valid 74-152 cm): 2.396 x e^(0.01863 x height_cm)
Suggested tidal volume is 6-8 mL/kg IBW (lung-protective ventilation); the default is 7 mL/kg.
No Qt imports.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from hmi.model.spec import NumericSpec


class Category(str, Enum):
    ADULT = "adult"
    PEDIATRIC = "pediatric"

    @property
    def title(self) -> str:
        return "Adult" if self is Category.ADULT else "Pediatric"


class Sex(str, Enum):
    MALE = "male"
    FEMALE = "female"


HEIGHT_RANGE = {Category.ADULT: (140, 210), Category.PEDIATRIC: (75, 150)}
DEFAULT_HEIGHT = {Category.ADULT: 170, Category.PEDIATRIC: 110}
VT_STEP = {Category.ADULT: 10, Category.PEDIATRIC: 5}
AGE_SPEC = NumericSpec("age", "Age", "years", 0, 120, 1)


def height_spec(category: Category) -> NumericSpec:
    low, high = HEIGHT_RANGE[category]
    return NumericSpec("height", "Height", "cm", low, high, 1)


def ideal_body_weight(category: Category, sex: Sex, height_cm: float) -> float:
    """IBW in kg, rounded to 0.1 kg."""
    if category is Category.PEDIATRIC:
        ibw = 2.396 * math.exp(0.01863 * height_cm)
    else:
        base = 50.0 if sex is Sex.MALE else 45.5
        ibw = base + 0.91 * (height_cm - 152.4)
    return round(ibw, 1)


@dataclass(frozen=True)
class PatientProfile:
    category: Category = Category.ADULT
    sex: Sex = Sex.MALE
    height_cm: int = 170
    name: str = ""
    patient_id: str = ""
    age_years: int | None = None

    @classmethod
    def quick_start(cls, category: Category) -> "PatientProfile":
        return cls(category=category, height_cm=DEFAULT_HEIGHT[category])

    @property
    def ibw_kg(self) -> float:
        return ideal_body_weight(self.category, self.sex, self.height_cm)

    def ibw_formula_text(self) -> str:
        h = self.height_cm
        if self.category is Category.PEDIATRIC:
            return f"Traub: 2.396 × e^(0.01863 × {h})"
        base = "50" if self.sex is Sex.MALE else "45.5"
        return f"ARDSNet: {base} + 0.91 × ({h} − 152.4)"

    def suggested_vt_range(self) -> tuple[int, int]:
        return round(6 * self.ibw_kg), round(8 * self.ibw_kg)

    def default_vt(self) -> float:
        step = VT_STEP[self.category]
        return round(7 * self.ibw_kg / step) * step

    def summary(self) -> str:
        text = f"{self.category.title} · IBW {self.ibw_kg:.1f} kg"
        if self.name:
            text += f" · {self.name}"
        return text
