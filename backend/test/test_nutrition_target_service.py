from datetime import date
from types import SimpleNamespace

import pytest

from src.application.services.nutrition_target_service import NutritionTargetService


def test_calculate_target_values_applies_diabetes_carb_cap():
    persona = SimpleNamespace(
        date_of_birth=date(1990, 1, 1),
        height_cm=172,
        weight_kg=78,
        gender="male",
        activity_level="sedentary",
    )
    conditions = {
        "diabetes_status": "yes",
        "hypertension_status": "no",
        "kidney_disease_stage": None,
    }

    result = NutritionTargetService._calculate_target_values(persona, conditions)
    cap = (result["calories_kcal"] * 0.45) / 4

    assert result["carbohydrates_g"] <= cap + 0.01
    assert result["calculation_basis"]["diabetes_status"] == "yes"


def test_calculate_target_values_restricts_protein_for_kidney_stage_4():
    persona = SimpleNamespace(
        date_of_birth=date(1985, 6, 1),
        height_cm=168,
        weight_kg=70,
        gender="female",
        activity_level="light",
    )
    conditions = {
        "diabetes_status": "no",
        "hypertension_status": "yes",
        "kidney_disease_stage": "Stage 4",
    }

    result = NutritionTargetService._calculate_target_values(persona, conditions)

    assert result["protein_g"] == pytest.approx(42.0, abs=0.2)
    assert result["calculation_basis"]["protein_per_kg"] == 0.6
    assert result["calculation_basis"]["sodium_watch"] is True
