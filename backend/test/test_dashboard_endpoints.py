from datetime import date
from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException

from src.infrastructure.agents.agent_response import AgentResponse
from src.application.services.health_timeline_service import HealthTimelineService
from src.presentation.api import ai_agent_routes, health_routes
from src.presentation.schemas.health_schemas import NutritionTargetManualCreateRequest
from src.presentation.schemas.nutrition_schemas import NutritionAdviceRequest


@pytest.mark.asyncio
async def test_nutrition_advice_persists_structured_meal_event(monkeypatch):
    captured: dict = {}

    async def fake_check_nutrition_limit(db, user):
        return {"remaining_queries": 1}

    async def fake_increment_nutrition_count(db, user):
        return None

    async def fake_get_patient_profile(db, user_id):
        return {
            "persona": {
                "age": 34,
                "gender": "female",
                "weight_kg": 63,
                "height_cm": 165,
            }
        }

    async def fake_get_current_health_profile(db, user_id):
        return {"report": {"version": None}, "health_context_summary": ""}

    async def fake_create_meal_event(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=uuid.uuid4())

    async def fake_nutritionist_agent(**kwargs):
        return AgentResponse.success_response("Add more vegetables.")

    monkeypatch.setattr(ai_agent_routes.SubscriptionService, "check_nutrition_limit", fake_check_nutrition_limit)
    monkeypatch.setattr(ai_agent_routes.SubscriptionService, "increment_nutrition_count", fake_increment_nutrition_count)
    monkeypatch.setattr("src.application.services.patient_service.PatientService.get_patient_profile", fake_get_patient_profile)
    monkeypatch.setattr(ai_agent_routes.HealthTimelineService, "get_current_health_profile", fake_get_current_health_profile)
    monkeypatch.setattr(ai_agent_routes.HealthTimelineService, "create_meal_event", fake_create_meal_event)
    monkeypatch.setattr(ai_agent_routes, "nutritionist_agent", fake_nutritionist_agent)

    request = NutritionAdviceRequest.model_validate(
        {
            "food_analysis": {
                "fooditem_details": [
                    {
                        "name": "grilled chicken",
                        "quantity": "1 plate",
                        "preparation": "grilled",
                        "nutrition": {
                            "calories": {"value": 320, "unit": "kcal"},
                            "protein": {"value": 35, "unit": "g"},
                            "carbohydrates": {"value": 5, "unit": "g"},
                            "fat": {"value": 18, "unit": "g"},
                            "fiber": {"value": 0, "unit": "g"},
                            "sugar": {"value": 0, "unit": "g"},
                        },
                    },
                    {
                        "name": "cola",
                        "quantity": "1 can",
                        "preparation": "cold",
                        "nutrition": {
                            "calories": {"value": 150, "unit": "kcal"},
                            "protein": {"value": 0, "unit": "g"},
                            "carbohydrates": {"value": 39, "unit": "g"},
                            "fat": {"value": 0, "unit": "g"},
                            "fiber": {"value": 0, "unit": "g"},
                            "sugar": {"value": 39, "unit": "g"},
                        },
                    },
                ],
                "nutrition": {
                    "calories": {"value": 470, "unit": "kcal"},
                    "protein": {"value": 35, "unit": "g"},
                    "carbohydrates": {"value": 44, "unit": "g"},
                    "fat": {"value": 18, "unit": "g"},
                    "fiber": {"value": 0, "unit": "g"},
                    "sugar": {"value": 39, "unit": "g"},
                },
            },
            "meal_type": "lunch",
            "meal_time": "13:15",
            "meal_date": "2026-03-14",
        }
    )

    response = await ai_agent_routes.get_nutrition_advice(
        request=request,
        current_user=SimpleNamespace(id=uuid.uuid4(), email="user@example.com"),
        db=object(),
    )

    assert response.meal_type == "lunch"
    assert response.meal_info.meal_date == "2026-03-14"
    assert captured["meal_type"] == "lunch"
    assert captured["source"] == "nutrition_advice"
    assert captured["meal_date"] == date(2026, 3, 14)
    assert captured["meal_time_value"].isoformat(timespec="minutes") == "13:15"
    assert captured["nutrition"]["calories"]["value"] == 470.0
    assert captured["items"][0]["role"] == "main"
    assert captured["items"][1]["role"] == "beverage"


@pytest.mark.asyncio
async def test_monthly_insights_uses_30_day_window(monkeypatch):
    captured: dict = {}

    async def fake_get_period_insights(**kwargs):
        captured.update(kwargs)
        return {
            "period_start": kwargs["start_datetime"].isoformat(),
            "period_end": kwargs["end_datetime"].isoformat(),
            "meal_count": 0,
            "vital_count": 0,
            "mood_checkin_count": 0,
            "nutrition_totals": {},
            "vital_overview": [],
            "associations": [],
            "narrative": "",
            "possible_factors": [],
        }

    monkeypatch.setattr(health_routes.HealthTimelineService, "get_period_insights", fake_get_period_insights)

    end_date = date(2026, 3, 14)
    response = await health_routes.get_monthly_insights(
        end_date=end_date,
        current_user=SimpleNamespace(id=uuid.uuid4()),
        db=object(),
    )

    assert response["meal_count"] == 0
    assert captured["label"] == "monthly"
    assert captured["end_datetime"].date() == end_date
    assert captured["start_datetime"].date() == date(2026, 2, 13)


@pytest.mark.asyncio
async def test_get_todays_meal_summary_delegates_to_service(monkeypatch):
    captured: dict = {}

    async def fake_get_todays_meal_nutrition_summary(**kwargs):
        captured.update(kwargs)
        return {
            "date": "2026-03-14",
            "meal_count": 2,
            "nutrition_totals": {
                "calories": {"value": 980.0, "unit": "kcal"},
                "protein": {"value": 52.0, "unit": "g"},
                "carbohydrates": {"value": 110.0, "unit": "g"},
                "fat": {"value": 28.0, "unit": "g"},
                "fiber": {"value": 8.0, "unit": "g"},
                "sugar": {"value": 21.0, "unit": "g"},
            },
        }

    monkeypatch.setattr(health_routes.HealthTimelineService, "get_todays_meal_nutrition_summary", fake_get_todays_meal_nutrition_summary)

    response = await health_routes.get_todays_meal_summary(
        target_date=date(2026, 3, 14),
        current_user=SimpleNamespace(id=uuid.uuid4()),
        db=object(),
    )

    assert response["meal_count"] == 2
    assert captured["target_date"] == date(2026, 3, 14)


@pytest.mark.asyncio
async def test_get_meal_history_delegates_to_service(monkeypatch):
    captured: dict = {}

    async def fake_get_meal_history(**kwargs):
        captured.update(kwargs)
        return {
            "items": [],
            "total_count": 0,
            "page": kwargs["page"],
            "page_size": kwargs["page_size"],
            "total_pages": 0,
        }

    monkeypatch.setattr(health_routes.HealthTimelineService, "get_meal_history", fake_get_meal_history)

    response = await health_routes.get_meal_history(
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 14),
        page=2,
        page_size=5,
        current_user=SimpleNamespace(id=uuid.uuid4()),
        db=object(),
    )

    assert response["page"] == 2
    assert captured["start_date"] == date(2026, 3, 1)
    assert captured["end_date"] == date(2026, 3, 14)
    assert captured["page_size"] == 5


@pytest.mark.asyncio
async def test_get_meal_history_rejects_invalid_date_range():
    with pytest.raises(HTTPException) as exc:
        await health_routes.get_meal_history(
            start_date=date(2026, 3, 15),
            end_date=date(2026, 3, 14),
            page=1,
            page_size=10,
            current_user=SimpleNamespace(id=uuid.uuid4()),
            db=object(),
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "start_date cannot be after end_date"


def test_nutrition_totals_from_meals_returns_structured_metrics():
    meals = [
        SimpleNamespace(
            total_calories=450,
            total_protein_g=25,
            total_carbohydrates_g=60,
            total_fat_g=12,
            total_fiber_g=5,
            total_sugar_g=10,
        ),
        SimpleNamespace(
            total_calories=530,
            total_protein_g=27,
            total_carbohydrates_g=50,
            total_fat_g=16,
            total_fiber_g=3,
            total_sugar_g=11,
        ),
    ]

    totals = HealthTimelineService._nutrition_totals_from_meals(meals)

    assert totals["calories"] == {"value": 980.0, "unit": "kcal"}
    assert totals["protein"] == {"value": 52.0, "unit": "g"}
    assert totals["sugar"] == {"value": 21.0, "unit": "g"}


@pytest.mark.asyncio
async def test_get_current_nutrition_target_returns_active_target(monkeypatch):
    expected = {
        "target_id": str(uuid.uuid4()),
        "target_date": "2026-03-14",
        "calories_kcal": 1800,
        "protein_g": 95.0,
        "carbohydrates_g": 180.0,
        "fat_g": 60.0,
        "fiber_g": 30.0,
        "source": "manual",
        "calculation_basis": {"manual_override": True},
        "is_active": True,
        "created_at": "2026-03-14T10:00:00+00:00",
    }

    async def fake_get_current_target(db, user_id, target_date=None):
        return expected

    monkeypatch.setattr(health_routes.NutritionTargetService, "get_current_target", fake_get_current_target)

    response = await health_routes.get_current_nutrition_target(
        current_user=SimpleNamespace(id=uuid.uuid4()),
        db=object(),
    )
    assert response["calories_kcal"] == 1800
    assert response["source"] == "manual"


@pytest.mark.asyncio
async def test_set_manual_nutrition_target_delegates_to_service(monkeypatch):
    captured = {}

    async def fake_set_manual_target(**kwargs):
        captured.update(kwargs)
        return {
            "target_id": str(uuid.uuid4()),
            "target_date": kwargs["target_date"].isoformat(),
            "calories_kcal": kwargs["calories_kcal"],
            "protein_g": kwargs["protein_g"],
            "carbohydrates_g": kwargs["carbohydrates_g"],
            "fat_g": kwargs["fat_g"],
            "fiber_g": kwargs["fiber_g"],
            "source": "manual",
            "calculation_basis": {"manual_override": True},
            "is_active": True,
            "created_at": "2026-03-14T10:00:00+00:00",
        }

    monkeypatch.setattr(health_routes.NutritionTargetService, "set_manual_target", fake_set_manual_target)

    request = NutritionTargetManualCreateRequest(
        target_date=date(2026, 3, 14),
        calories_kcal=1900,
        protein_g=100,
        carbohydrates_g=200,
        fat_g=62,
        fiber_g=32,
    )

    response = await health_routes.set_manual_nutrition_target(
        request=request,
        current_user=SimpleNamespace(id=uuid.uuid4()),
        db=object(),
    )

    assert captured["calories_kcal"] == 1900
    assert response["source"] == "manual"


@pytest.mark.asyncio
async def test_get_nutrition_target_adherence_returns_404_when_missing(monkeypatch):
    async def fake_get_adherence_for_date(db, user_id, target_date):
        raise ValueError("No nutrition target found for requested date")

    monkeypatch.setattr(health_routes.NutritionTargetService, "get_adherence_for_date", fake_get_adherence_for_date)

    with pytest.raises(HTTPException) as exc:
        await health_routes.get_nutrition_target_adherence(
            date_value=date(2026, 3, 14),
            current_user=SimpleNamespace(id=uuid.uuid4()),
            db=object(),
        )

    assert exc.value.status_code == 404


def test_build_food_analysis_fallback_contains_items_and_totals():
    meal = SimpleNamespace(
        total_calories=700,
        total_protein_g=35,
        total_carbohydrates_g=75,
        total_fat_g=22,
        total_fiber_g=6,
        total_sugar_g=14,
    )
    items = [
        {
            "name": "rice",
            "quantity": "1 bowl",
            "role": "main",
            "preparation": "cooked",
            "source_label": "rice",
            "confidence": 0.9,
        },
        {
            "name": "chicken curry",
            "quantity": "1 serving",
            "role": "main",
            "preparation": "curried",
            "source_label": "chicken curry",
            "confidence": 0.95,
        },
    ]

    payload = HealthTimelineService._build_food_analysis_fallback(meal, items)

    assert payload["fooditem_details"][0]["name"] == "rice"
    assert payload["nutrition"]["calories"] == {"value": 700.0, "unit": "kcal"}
    assert payload["nutrition"]["fiber"] == {"value": 6.0, "unit": "g"}
