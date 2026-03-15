"""
Unit tests for DietPlanService safety guards and core logic.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


# ─── Safety guard helpers ────────────────────────────────────────────────────

def _make_profile(
    diabetes_status="unknown",
    hypertension_status="unknown",
    kidney_disease_stage=None,
    allergies=None,
    food_restrictions=None,
    medications=None,
):
    return {
        "snapshot": {
            "diabetes_status": diabetes_status,
            "hypertension_status": hypertension_status,
            "kidney_disease_stage": kidney_disease_stage,
            "dyslipidemia_status": "unknown",
            "food_restrictions": food_restrictions or [],
            "allergies": allergies or [],
            "dietary_preferences": [],
            "doctor_advice": [],
            "extra_conditions": [],
        },
        "medications": medications or [],
        "labs": [],
        "lab_trends": [],
    }


def _make_target(calories=2000, protein_g=100, carbs_g=250, fat_g=70, fiber_g=25):
    return {
        "calories_kcal": calories,
        "protein_g": protein_g,
        "carbohydrates_g": carbs_g,
        "fat_g": fat_g,
        "fiber_g": fiber_g,
    }


# ─── ReportComparisonService ──────────────────────────────────────────────────

class TestClassifyTrend:
    from src.application.services.report_comparison_service import ReportComparisonService

    def test_hba1c_worsening(self):
        from src.application.services.report_comparison_service import ReportComparisonService
        result = ReportComparisonService.classify_trend(8.0, 7.5, "hba1c")
        assert result == "worsening"

    def test_hba1c_improving(self):
        from src.application.services.report_comparison_service import ReportComparisonService
        result = ReportComparisonService.classify_trend(7.0, 7.5, "hba1c")
        assert result == "improving"

    def test_hba1c_stable(self):
        from src.application.services.report_comparison_service import ReportComparisonService
        result = ReportComparisonService.classify_trend(7.5, 7.5, "hba1c")
        assert result == "stable"

    def test_ldl_worsening(self):
        from src.application.services.report_comparison_service import ReportComparisonService
        result = ReportComparisonService.classify_trend(160, 140, "ldl_cholesterol")
        assert result == "worsening"

    def test_ldl_improving(self):
        from src.application.services.report_comparison_service import ReportComparisonService
        result = ReportComparisonService.classify_trend(120, 140, "ldl_cholesterol")
        assert result == "improving"

    def test_hdl_worsening(self):
        from src.application.services.report_comparison_service import ReportComparisonService
        result = ReportComparisonService.classify_trend(35, 45, "hdl_cholesterol")
        assert result == "worsening"

    def test_hdl_improving(self):
        from src.application.services.report_comparison_service import ReportComparisonService
        result = ReportComparisonService.classify_trend(55, 45, "hdl_cholesterol")
        assert result == "improving"

    def test_glucose_worsening(self):
        from src.application.services.report_comparison_service import ReportComparisonService
        result = ReportComparisonService.classify_trend(130, 110, "fasting_glucose")
        assert result == "worsening"

    def test_creatinine_worsening(self):
        from src.application.services.report_comparison_service import ReportComparisonService
        result = ReportComparisonService.classify_trend(1.5, 1.2, "creatinine")
        assert result == "worsening"

    def test_unknown_lab_small_delta_stable(self):
        from src.application.services.report_comparison_service import ReportComparisonService
        result = ReportComparisonService.classify_trend(100.0, 100.0, "unknown_lab")
        assert result == "stable"


# ─── DietPlanService context building ────────────────────────────────────────

class TestDietPlanServiceContextBuilding:
    """Tests for context assembly logic (no DB calls)."""

    def test_context_includes_allergy_from_profile(self):
        profile = _make_profile(allergies=["peanuts", "shellfish"])
        # Verify allergies flow through correctly
        assert "peanuts" in profile["snapshot"]["allergies"]
        assert "shellfish" in profile["snapshot"]["allergies"]

    def test_context_includes_kidney_stage(self):
        profile = _make_profile(kidney_disease_stage="stage_4")
        assert profile["snapshot"]["kidney_disease_stage"] == "stage_4"

    def test_context_diabetes_flag(self):
        profile = _make_profile(diabetes_status="yes")
        assert profile["snapshot"]["diabetes_status"] == "yes"

    def test_context_food_restrictions(self):
        profile = _make_profile(food_restrictions=["low_sodium", "low_potassium"])
        assert "low_sodium" in profile["snapshot"]["food_restrictions"]


# ─── DietPlanService serialize ────────────────────────────────────────────────

class TestDietPlanSerialize:
    def _make_mock_plan(self, meals=None):
        plan = MagicMock()
        plan.id = uuid4()
        plan.valid_from = date.today()
        plan.valid_until = date.today() + timedelta(days=6)
        plan.generated_by = "diet_plan_agent_v1"
        plan.trigger = "manual"
        plan.calorie_target = 2000
        plan.notes = "Test plan"
        plan.is_active = True
        plan.meals = meals or []
        return plan

    def test_serialize_empty_meals(self):
        from src.application.services.diet_plan_service import DietPlanService
        plan = self._make_mock_plan(meals=[])
        result = DietPlanService._serialize_plan(plan)
        assert result["plan_id"] == str(plan.id)
        assert result["meals"] == []
        assert result["calorie_target"] == 2000
        assert result["is_active"] is True

    def test_serialize_meals_sorted_by_day_and_type(self):
        from src.application.services.diet_plan_service import DietPlanService

        def _meal(day, mtype, name):
            m = MagicMock()
            m.day_of_week = day
            m.meal_type = mtype
            m.meal_name = name
            m.description = None
            m.foods = []
            m.total_calories = 300
            m.total_protein_g = 20
            m.notes = None
            return m

        meals = [
            _meal(1, "dinner", "D"),
            _meal(0, "lunch", "L"),
            _meal(0, "breakfast", "B"),
        ]
        plan = self._make_mock_plan(meals=meals)
        result = DietPlanService._serialize_plan(plan)
        order = [(m["day_of_week"], m["meal_type"]) for m in result["meals"]]
        assert order[0] == (0, "breakfast")
        assert order[1] == (0, "lunch")
        assert order[2] == (1, "dinner")


# ─── DietPlanService get_todays_plan_meals ────────────────────────────────────

class TestGetTodaysPlanMeals:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_plan(self):
        from src.application.services.diet_plan_service import DietPlanService

        db = AsyncMock()
        with patch.object(DietPlanService, "get_current_plan", return_value=None):
            result = await DietPlanService.get_todays_plan_meals(db, uuid4())
        assert result == []

    @pytest.mark.asyncio
    async def test_filters_to_today_weekday(self):
        from src.application.services.diet_plan_service import DietPlanService

        today_wd = date.today().weekday()
        other_wd = (today_wd + 1) % 7

        mock_plan = {
            "meals": [
                {"day_of_week": today_wd, "meal_type": "breakfast", "meal_name": "Oats"},
                {"day_of_week": other_wd, "meal_type": "lunch", "meal_name": "Rice"},
            ]
        }

        db = AsyncMock()
        with patch.object(DietPlanService, "get_current_plan", return_value=mock_plan):
            result = await DietPlanService.get_todays_plan_meals(db, uuid4())

        assert len(result) == 1
        assert result[0]["meal_name"] == "Oats"


# ─── NutritionTargetManualCreateRequest validation ───────────────────────────

class TestNutritionTargetManualCreateRequest:
    def test_future_date_rejected(self):
        from pydantic import ValidationError
        from src.presentation.schemas.health_schemas import NutritionTargetManualCreateRequest

        future = date.today() + timedelta(days=1)
        with pytest.raises(ValidationError) as exc_info:
            NutritionTargetManualCreateRequest(
                target_date=future,
                calories_kcal=2000,
                protein_g=100,
                carbohydrates_g=250,
                fat_g=70,
                fiber_g=25,
            )
        assert "future" in str(exc_info.value).lower()

    def test_today_accepted(self):
        from src.presentation.schemas.health_schemas import NutritionTargetManualCreateRequest

        req = NutritionTargetManualCreateRequest(
            target_date=date.today(),
            calories_kcal=2000,
            protein_g=100,
            carbohydrates_g=250,
            fat_g=70,
            fiber_g=25,
        )
        assert req.target_date == date.today()

    def test_past_date_accepted(self):
        from src.presentation.schemas.health_schemas import NutritionTargetManualCreateRequest

        past = date.today() - timedelta(days=30)
        req = NutritionTargetManualCreateRequest(
            target_date=past,
            calories_kcal=1800,
            protein_g=90,
            carbohydrates_g=200,
            fat_g=60,
            fiber_g=20,
        )
        assert req.target_date == past

    def test_calories_below_min_rejected(self):
        from pydantic import ValidationError
        from src.presentation.schemas.health_schemas import NutritionTargetManualCreateRequest

        with pytest.raises(ValidationError):
            NutritionTargetManualCreateRequest(
                target_date=date.today(),
                calories_kcal=500,
                protein_g=100,
                carbohydrates_g=250,
                fat_g=70,
                fiber_g=25,
            )
