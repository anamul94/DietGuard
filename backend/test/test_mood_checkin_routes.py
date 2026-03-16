import io
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from src.presentation.api import health_routes
from src.infrastructure.agents.agent_response import AgentResponse


@pytest.mark.asyncio
async def test_create_mood_checkin_requires_consent():
    audio = UploadFile(filename="checkin.wav", file=io.BytesIO(b"1234"), content_type="audio/wav")
    with pytest.raises(HTTPException) as exc:
        await health_routes.create_mood_checkin(
            audio=audio,
            consent=False,
            captured_at=None,
            user_local_time=None,
            current_user=SimpleNamespace(id=uuid.uuid4(), email="user@example.com"),
            db=object(),
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_create_mood_checkin_rejects_invalid_extension():
    audio = UploadFile(filename="checkin.ogg", file=io.BytesIO(b"1234"), content_type="audio/ogg")
    with pytest.raises(HTTPException) as exc:
        await health_routes.create_mood_checkin(
            audio=audio,
            consent=True,
            captured_at=None,
            user_local_time=None,
            current_user=SimpleNamespace(id=uuid.uuid4(), email="user@example.com"),
            db=object(),
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_create_mood_checkin_persists_and_returns_structured_fields(monkeypatch):
    captured: dict = {}

    async def fake_transcribe_audio_bytes(**kwargs):
        return SimpleNamespace(
            transcript_text="I feel overwhelmed and can't focus today.",
            job_name="job-123",
            media_format="wav",
            s3_object_key="mood-checkins/x.wav",
        )

    async def fake_mood_checkin_agent(transcribed_text: str):
        assert "overwhelmed" in transcribed_text
        return AgentResponse.success_response(
            {
                "primary_emotion": "anxious",
                "secondary_emotions": ["overwhelmed", "tired"],
                "stress_level": 78,
                "key_stress_indicators": ["can't focus", "overwhelmed"],
                "urgency_level": "medium",
                "summary": "User feels overwhelmed and has trouble focusing today.",
            },
            metadata={"model_name": "test", "input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        )

    async def fake_track_token_usage(**kwargs):
        return None

    async def fake_create_mood_checkin(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=uuid.uuid4(), captured_at=kwargs["captured_at"])

    monkeypatch.setattr(health_routes, "transcribe_audio_bytes", fake_transcribe_audio_bytes)
    monkeypatch.setattr(health_routes, "mood_checkin_agent", fake_mood_checkin_agent)
    monkeypatch.setattr(health_routes.TokenUsageService, "track_token_usage", fake_track_token_usage)
    monkeypatch.setattr(health_routes.HealthTimelineService, "create_mood_checkin", fake_create_mood_checkin)

    now = datetime(2026, 3, 16, 10, 0, tzinfo=timezone.utc)
    audio = UploadFile(filename="checkin.wav", file=io.BytesIO(b"1234"), content_type="audio/wav")
    user = SimpleNamespace(id=uuid.uuid4(), email="user@example.com")

    resp = await health_routes.create_mood_checkin(
        audio=audio,
        consent=True,
        captured_at=now,
        user_local_time=None,
        current_user=user,
        db=object(),
    )

    assert resp.user_id == str(user.id)
    assert resp.session_id.startswith("ses_")
    assert resp.analyzed_at.tzinfo is not None
    assert resp.day_of_week in {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
    assert resp.time_of_day in {"morning", "afternoon", "evening", "night"}
    assert resp.primary_emotion == "anxious"
    assert resp.stress_level == 78
    assert resp.urgency_level == "medium"
    assert "overwhelmed" in resp.summary.lower()
    assert captured["mood_label"] == "anxious"
    assert captured["stress_level_1_5"] == 4
    assert captured["symptom_flags"]["stress_score_0_100"] == 78
    assert captured["symptom_flags"]["analysis_version"] == "mood_checkin_v1"


@pytest.mark.asyncio
async def test_get_mood_history_maps_symptom_flags(monkeypatch):
    fake_row = SimpleNamespace(
        id=uuid.uuid4(),
        captured_at=datetime(2026, 3, 16, 9, 0, tzinfo=timezone.utc),
        transcript="Feeling okay.",
        mood_label="calm",
        symptom_flags={
            "stress_score_0_100": 12,
            "secondary_emotions": ["content"],
            "key_stress_indicators": [],
            "urgency_level": "low",
            "summary": "User feels calm.",
        },
    )

    async def fake_get_mood_history(**kwargs):
        return {
            "items": [fake_row],
            "total_count": 1,
            "page": 1,
            "page_size": 10,
            "total_pages": 1,
        }

    monkeypatch.setattr(health_routes.HealthTimelineService, "get_mood_history", fake_get_mood_history)

    resp = await health_routes.get_mood_history(
        start_date=None,
        end_date=None,
        page=1,
        page_size=10,
        current_user=SimpleNamespace(id=uuid.uuid4()),
        db=object(),
    )

    assert resp.total_count == 1
    assert resp.items[0].primary_emotion == "calm"
    assert resp.items[0].stress_level == 12
    assert resp.items[0].urgency_level == "low"
