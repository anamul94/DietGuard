from src.application.services.health_utils import grams
from src.infrastructure.utils.nutrition_utils import format_metric, metric_value
from src.presentation.schemas.food_schemas import FoodAnalysis, NutritionInfo


def test_nutrition_info_accepts_legacy_values_and_emits_structured_units():
    nutrition = NutritionInfo.model_validate(
        {
            "calories": 320,
            "protein": "12g",
            "carbohydrates": {"value": "48", "unit": "g"},
            "fat": {"value": 8, "unit": "g"},
            "fiber": 4,
            "sugar": "6 g",
        }
    )

    dumped = nutrition.model_dump()

    assert dumped["calories"] == {"value": 320.0, "unit": "kcal"}
    assert dumped["protein"] == {"value": 12.0, "unit": "g"}
    assert dumped["fiber"] == {"value": 4.0, "unit": "g"}
    assert dumped["sugar"] == {"value": 6.0, "unit": "g"}


def test_metric_helpers_support_structured_nutrition_values():
    metric = {"value": 15, "unit": "g"}

    assert metric_value({"value": 320, "unit": "kcal"}) == 320.0
    assert grams(metric) is not None
    assert format_metric(metric, "g") == "15 g"


def test_food_analysis_uses_item_details_as_the_only_item_source():
    analysis = FoodAnalysis.model_validate(
        {
            "fooditem_details": [
                {
                    "name": "Pizza with cheese",
                    "quantity": "2 slices",
                    "nutrition": {
                        "calories": {"value": 320, "unit": "kcal"},
                        "protein": {"value": 12, "unit": "g"},
                        "carbohydrates": {"value": 38, "unit": "g"},
                        "fat": {"value": 14, "unit": "g"},
                        "fiber": {"value": 2, "unit": "g"},
                        "sugar": {"value": 4, "unit": "g"},
                    },
                },
                {
                    "name": "Grilled chicken",
                    "quantity": "150 g",
                    "nutrition": {
                        "calories": {"value": 280, "unit": "kcal"},
                        "protein": {"value": 30, "unit": "g"},
                        "carbohydrates": {"value": 0, "unit": "g"},
                        "fat": {"value": 12, "unit": "g"},
                        "fiber": {"value": 0, "unit": "g"},
                        "sugar": {"value": 0, "unit": "g"},
                    },
                },
            ],
            "nutrition": {
                "calories": {"value": 600, "unit": "kcal"},
                "protein": {"value": 42, "unit": "g"},
                "carbohydrates": {"value": 38, "unit": "g"},
                "fat": {"value": 26, "unit": "g"},
                "fiber": {"value": 2, "unit": "g"},
                "sugar": {"value": 4, "unit": "g"},
            },
        }
    )

    dumped = analysis.model_dump()

    assert "fooditems" not in dumped
    assert [item["name"] for item in dumped["fooditem_details"]] == ["Pizza with cheese", "Grilled chicken"]
    assert analysis.fooditem_details[0].nutrition.calories.model_dump() == {"value": 320.0, "unit": "kcal"}
