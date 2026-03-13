from src.infrastructure.graphs.health_correlation import (
    build_correlation_narrative,
    compute_associations_payload,
)


def test_compute_associations_payload_detects_meal_vital_association():
    result = compute_associations_payload(
        meals=[
            {
                "id": "meal-1",
                "meal_type": "lunch",
                "meal_date": "2026-03-10",
                "meal_time": "2026-03-10T13:00:00+00:00",
                "total_calories": 720,
                "total_carbohydrates_g": 84.0,
                "total_fat_g": 22.0,
            }
        ],
        vitals=[
            {
                "id": "vital-before",
                "vital_type": "cgm",
                "value_primary": 108.0,
                "value_secondary": None,
                "unit": "mg/dL",
                "captured_at": "2026-03-10T12:30:00+00:00",
                "source": "device",
            },
            {
                "id": "vital-after",
                "vital_type": "cgm",
                "value_primary": 162.0,
                "value_secondary": None,
                "unit": "mg/dL",
                "captured_at": "2026-03-10T13:50:00+00:00",
                "source": "device",
            },
        ],
        mood_checkins=[
            {
                "id": "mood-1",
                "mood_label": "stressed",
                "stress_level": 4,
                "sleep_quality": 2,
                "captured_at": "2026-03-10T12:00:00+00:00",
            }
        ],
        health_profile={
            "snapshot": {"diabetes_status": "yes"},
            "medications": [{"medication_name": "Metformin"}],
        },
    )

    assert len(result["associations"]) == 1
    association = result["associations"][0]
    assert association["confidence_tier"] in {"low", "medium"}
    assert "may be associated" in association["explanation"]
    assert "meal carb load" in association["possible_factors"]
    assert "stress" in association["possible_factors"]
    assert "poor sleep" in association["possible_factors"]


def test_build_correlation_narrative_mentions_possible_factors():
    narrative = build_correlation_narrative(
        period_label="daily",
        associations=[
            {
                "vital_type": "cgm",
                "possible_factors": ["meal carb load", "stress"],
            }
        ],
    )

    assert "possible associations" in narrative
    assert "meal carb load, stress" in narrative
