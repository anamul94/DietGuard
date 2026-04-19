"""
Structured health timeline routes.
"""

from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi import Form
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from ...application.services.health_timeline_service import HealthTimelineService, group_food_items_for_review, parse_vitals_csv
from ...application.services.token_usage_service import TokenUsageService
from ...application.services.nutrition_target_service import NutritionTargetService
from ...application.services.diet_plan_service import DietPlanService
from ...application.services.patient_service import PatientService
from ...infrastructure.agents.food_agent import food_agent
from ...infrastructure.agents.mood_checkin_agent import mood_checkin_agent
from ...infrastructure.agents.nutrition_calculator_agent import nutrition_calculator_agent
from ...infrastructure.auth.dependencies import get_current_active_user
from ...infrastructure.database.auth_models import User
from ...infrastructure.database.database import get_db
from ...infrastructure.utils.image_utils import encode_image_to_base64
from ...infrastructure.utils.logger import logger
from ...infrastructure.utils.transcribe_utils import (
    get_max_mood_audio_bytes,
    infer_transcribe_media_format,
    transcribe_audio_bytes,
    TranscribeConfigError,
    TranscribeFailedError,
)
from ..schemas.health_schemas import (
    DeviceVitalSyncRequest,
    MealConfirmRequest,
    MealConfirmResponse,
    MealDraftResponse,
    NutritionTargetAdherenceResponse,
    NutritionTargetManualCreateRequest,
    NutritionTargetResponse,
    PaginatedMealHistoryResponse,
    PeriodInsightsResponse,
    StructuredHealthProfileResponse,
    TodayMealNutritionSummaryResponse,
    VitalBatchCreate,
    VitalBatchResponse,
    VitalHistoryItemResponse,
    PaginatedVitalHistoryResponse,
)
from ..schemas.diet_plan_schemas import DietPlanResponse, DietPlanMealSchema
from ..schemas.daily_summary_schemas import DailySummaryCreate, DailySummaryResponse
from ..schemas.mood_schemas import MoodCheckInResponse, MoodHistoryItem, PaginatedMoodHistoryResponse
from ...application.services.daily_summary_service import DailySummaryService


router = APIRouter(tags=["Health Timeline"])

MOOD_CHECKIN_UPLOAD_SCHEMA = {
    "content": {
        "multipart/form-data": {
            "schema": {
                "type": "object",
                "required": ["audio", "consent"],
                "properties": {
                    "audio": {"type": "string", "format": "binary", "description": "Audio file (.m4a/.mp4/.mp3/.wav)"},
                    "consent": {"type": "boolean", "description": "Must be true to store transcript and analysis"},
                    "captured_at": {"type": "string", "format": "date-time", "description": "Optional capture time (UTC or with offset)"},
                    "user_local_time": {"type": "string", "format": "date-time", "description": "Optional local device time with offset"},
                },
            }
        }
    },
    "required": True,
}


async def _read_upload_file_limited(file: UploadFile, *, max_bytes: int) -> bytes:
    data = bytearray()
    chunk_size = 1024 * 1024
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Audio file too large. Max allowed is {max_bytes // (1024 * 1024)} MB.",
            )
    return bytes(data)


def _stress_score_to_1_5(score_0_100: int | None) -> int | None:
    if score_0_100 is None:
        return None
    clamped = max(0, min(100, int(score_0_100)))
    return min(5, (clamped // 20) + 1)


def _time_of_day(local_dt: datetime) -> str:
    hour = local_dt.hour
    if 5 <= hour <= 11:
        return "morning"
    if 12 <= hour <= 16:
        return "afternoon"
    if 17 <= hour <= 20:
        return "evening"
    return "night"


async def _resolve_user_local_time(
    *,
    db: AsyncSession,
    user_id: str,
    captured_at_utc: datetime,
    provided_local_time: datetime | None,
) -> datetime:
    if provided_local_time is not None:
        if provided_local_time.tzinfo is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_local_time must include timezone offset")
        return provided_local_time

    try:
        profile = await PatientService.get_patient_profile(db, user_id)
        tz_str = (profile or {}).get("persona", {}).get("timezone") or "UTC"
        tz = ZoneInfo(tz_str)
        return captured_at_utc.astimezone(tz)
    except Exception:
        return captured_at_utc


@router.get("/profile/current", response_model=StructuredHealthProfileResponse)
async def get_current_health_profile(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await HealthTimelineService.get_current_health_profile(db, current_user.id)
    if not profile["report"]["version"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No structured medical report found")
    return profile


@router.get("/targets/current", response_model=NutritionTargetResponse)
async def get_current_nutrition_target(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    target = await NutritionTargetService.get_current_target(db, current_user.id)
    if target:
        return target

    try:
        return await NutritionTargetService.upsert_calculated_target(db, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/targets", response_model=NutritionTargetResponse)
async def set_manual_nutrition_target(
    request: NutritionTargetManualCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await NutritionTargetService.set_manual_target(
        db=db,
        user_id=current_user.id,
        target_date=request.target_date,
        calories_kcal=request.calories_kcal,
        protein_g=request.protein_g,
        carbohydrates_g=request.carbohydrates_g,
        fat_g=request.fat_g,
        fiber_g=request.fiber_g,
    )


@router.get("/targets/adherence", response_model=NutritionTargetAdherenceResponse)
async def get_nutrition_target_adherence(
    date_value: date | None = Query(default=None, alias="date"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    target_date = date_value or date.today()
    try:
        return await NutritionTargetService.get_adherence_for_date(
            db=db,
            user_id=current_user.id,
            target_date=target_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/meals/draft-from-image", response_model=MealDraftResponse)
async def draft_meal_from_image(
    files: List[UploadFile] = File(..., description="Meal images"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    allowed_extensions = {"jpg", "jpeg", "png"}
    encoded_images = []
    filenames = []
    mime_types = []

    for file in files:
        extension = file.filename.split(".")[-1].lower()
        if extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid file type: {file.filename}. Only JPG and PNG files are allowed.",
            )
        encoded = encode_image_to_base64(file)
        encoded_images.append(encoded["base64_string"])
        filenames.append(file.filename)
        mime_types.append(encoded["mime_type"])

    patient_profile = await PatientService.get_patient_profile(db, current_user.id)
    location = (patient_profile or {}).get("persona", {}).get("current_location")

    agent_response = await food_agent(encoded_images, ["image"] * len(encoded_images), mime_types, location=location)
    if not agent_response.success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=agent_response.error_message)

    draft = group_food_items_for_review(agent_response.data)
    return {
        **draft,
        "filenames": filenames,
        "raw_food_analysis": agent_response.data,
    }


@router.post("/meals/confirm", response_model=MealConfirmResponse)
async def confirm_meal(
    request: MealConfirmRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    logger.debug("Meal confirmation payload", user_id=str(current_user.id), payload=jsonable_encoder(request))
    analysis_payload = request.food_analysis.model_dump()
    item_payloads = [
        {
            "name": detail.name,
            "quantity": detail.quantity,
            "role": "main",
            "preparation": detail.preparation,
        }
        for detail in request.food_analysis.fooditem_details
    ]
    logger.info(
        "Meal confirmation requested",
        user_id=str(current_user.id),
        item_count=len(item_payloads),
    )
    hour, minute = map(int, request.meal_time.split(":"))
    meal_event = await HealthTimelineService.create_meal_event(
        db=db,
        user_id=current_user.id,
        meal_type=request.meal_type,
        meal_date=request.meal_date,
        meal_time_value=time(hour=hour, minute=minute),
        items=item_payloads,
        nutrition=analysis_payload.get("nutrition", {}),
        fooditem_details=analysis_payload.get("fooditem_details", item_payloads),
        source_filenames=[],
        source="confirmed_meal",
    )

    return {
        "meal_event_id": str(meal_event.id),
        "meal_type": meal_event.meal_type,
        "meal_date": meal_event.meal_date.isoformat(),
        "meal_time": request.meal_time,
        "food_analysis": analysis_payload,
        "source_filenames": [],
    }


@router.get("/meals/today-summary", response_model=TodayMealNutritionSummaryResponse)
async def get_todays_meal_summary(
    target_date: date | None = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    target_date = target_date or date.today()
    return await HealthTimelineService.get_todays_meal_nutrition_summary(
        db=db,
        user_id=current_user.id,
        target_date=target_date,
    )


@router.get("/meals/history", response_model=PaginatedMealHistoryResponse)
async def get_meal_history(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date cannot be after end_date",
        )
    return await HealthTimelineService.get_meal_history(
        db=db,
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )


@router.post("/vitals", response_model=VitalBatchResponse)
async def create_vitals(
    request: VitalBatchCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    created = await HealthTimelineService.create_vital_events(
        db=db,
        user_id=current_user.id,
        entries=[entry.model_dump() for entry in request.entries],
        source="manual",
    )
    return {
        "created_count": len(created),
        "source": "manual",
        "entries": [
            {
                "vital_type": entry.vital_type,
                "value_primary": float(entry.value_primary),
                "value_secondary": float(entry.value_secondary) if entry.value_secondary is not None else None,
                "unit": entry.unit,
                "captured_at": entry.captured_at,
                "source": entry.source,
                "source_device": entry.source_device,
            }
            for entry in created
        ],
    }


@router.post("/vitals/import-csv", response_model=VitalBatchResponse)
async def import_vitals_csv(
    file: UploadFile = File(..., description="CSV file with vital readings"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only CSV files are supported")

    content = (await file.read()).decode("utf-8")
    try:
        entries = parse_vitals_csv(content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    created = await HealthTimelineService.create_vital_events(
        db=db,
        user_id=current_user.id,
        entries=entries,
        source="csv",
    )
    return {
        "created_count": len(created),
        "source": "csv",
        "entries": [
            {
                "vital_type": entry.vital_type,
                "value_primary": float(entry.value_primary),
                "value_secondary": float(entry.value_secondary) if entry.value_secondary is not None else None,
                "unit": entry.unit,
                "captured_at": entry.captured_at,
                "source": entry.source,
                "source_device": entry.source_device,
            }
            for entry in created
        ],
    }


@router.post("/vitals/device-sync", response_model=VitalBatchResponse)
async def sync_device_vitals(
    request: DeviceVitalSyncRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    created = await HealthTimelineService.create_vital_events(
        db=db,
        user_id=current_user.id,
        entries=[entry.model_dump() for entry in request.entries],
        source="device",
        source_device=request.source_device,
    )
    return {
        "created_count": len(created),
        "source": "device",
        "entries": [
            {
                "vital_type": entry.vital_type,
                "value_primary": float(entry.value_primary),
                "value_secondary": float(entry.value_secondary) if entry.value_secondary is not None else None,
                "unit": entry.unit,
                "captured_at": entry.captured_at,
                "source": entry.source,
                "source_device": entry.source_device,
            }
            for entry in created
        ],
    }


@router.get("/vitals/daily", response_model=List[VitalHistoryItemResponse])
async def get_daily_vitals(
    target_date: date | None = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    target_date = target_date or date.today()
    return await HealthTimelineService.get_daily_vitals(
        db=db,
        user_id=current_user.id,
        target_date=target_date,
    )


@router.get("/vitals/history", response_model=PaginatedVitalHistoryResponse)
async def get_vital_history(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date cannot be after end_date")

    return await HealthTimelineService.get_vital_history(
        db=db,
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/mood/checkin",
    response_model=MoodCheckInResponse,
    summary="Create audio mood check-in",
    description="Uploads audio, transcribes via AWS Transcribe, analyzes transcript via LLM, stores result, and returns structured mood/stress fields. Requires consent=true.",
    openapi_extra={"requestBody": MOOD_CHECKIN_UPLOAD_SCHEMA},
)
async def create_mood_checkin(
    audio: UploadFile = File(..., description="Audio recording for mood check-in (.m4a/.mp4/.mp3/.wav)"),
    consent: bool = Form(..., description="Must be true to store transcript and derived mood/stress fields"),
    captured_at: datetime | None = Form(default=None, description="Optional ISO datetime when the check-in was recorded"),
    user_local_time: datetime | None = Form(default=None, description="Optional ISO datetime with offset from the device"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if consent is not True:
        logger.warning(
            "Mood check-in rejected: missing consent",
            user_id=str(current_user.id),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="consent=true is required")

    media_format = infer_transcribe_media_format(audio.filename or "")
    if not media_format:
        logger.warning(
            "Mood check-in rejected: unsupported audio extension",
            user_id=str(current_user.id),
            filename=audio.filename,
            content_type=audio.content_type,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid audio type. Allowed: .m4a, .mp4, .mp3, .wav",
        )

    max_bytes = get_max_mood_audio_bytes()
    audio_bytes = await _read_upload_file_limited(audio, max_bytes=max_bytes)
    logger.info(
        "Mood check-in audio received",
        user_id=str(current_user.id),
        filename=audio.filename,
        content_type=audio.content_type,
        media_format=media_format,
        size_bytes=len(audio_bytes),
    )

    try:
        transcribe_result = await transcribe_audio_bytes(
            filename=audio.filename or "audio",
            content_type=audio.content_type,
            audio_bytes=audio_bytes,
        )
    except TranscribeConfigError as exc:
        logger.error(
            "Transcribe configuration error",
            user_id=str(current_user.id),
            filename=audio.filename,
            media_format=media_format,
            error=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Transcription service is not configured") from exc
    except TranscribeFailedError as exc:
        logger.error(
            "Transcribe job failed",
            user_id=str(current_user.id),
            filename=audio.filename,
            media_format=media_format,
            error=str(exc),
        )
        message = str(exc)
        if "Empty transcript text" in message or "no speech detected" in message.lower():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No speech detected in audio") from exc
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Transcription failed") from exc
    except ValueError as exc:
        logger.warning(
            "Mood check-in rejected: invalid transcription input",
            user_id=str(current_user.id),
            filename=audio.filename,
            media_format=media_format,
            error=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(
            "AWS Transcribe failed",
            user_id=str(current_user.id),
            filename=audio.filename,
            media_format=media_format,
            error=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Transcription failed") from exc

    transcript_text = transcribe_result.transcript_text
    analyzed_at = datetime.now(timezone.utc)
    agent_response = await mood_checkin_agent(transcript_text)
    if not agent_response.success:
        logger.error(
            "Mood check-in agent failed",
            user_id=str(current_user.id),
            session_id=session_id,
            error=agent_response.error_message,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=agent_response.error_message)

    analysis = agent_response.data if isinstance(agent_response.data, dict) else {}
    primary_emotion = analysis.get("primary_emotion")
    urgency_level = analysis.get("urgency_level")
    summary = analysis.get("summary")
    if not isinstance(primary_emotion, str) or not primary_emotion.strip():
        logger.error(
            "Mood analysis invalid: primary_emotion",
            user_id=str(current_user.id),
            session_id=session_id,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Mood analysis returned invalid primary_emotion")
    if urgency_level not in {"low", "medium", "high"}:
        logger.error(
            "Mood analysis invalid: urgency_level",
            user_id=str(current_user.id),
            session_id=session_id,
            urgency_level=urgency_level,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Mood analysis returned invalid urgency_level")
    if not isinstance(summary, str) or not summary.strip():
        logger.error(
            "Mood analysis invalid: summary",
            user_id=str(current_user.id),
            session_id=session_id,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Mood analysis returned invalid summary")

    captured_at_utc = captured_at or datetime.now(timezone.utc)
    if captured_at_utc.tzinfo is None:
        captured_at_utc = captured_at_utc.replace(tzinfo=timezone.utc)
    local_dt = await _resolve_user_local_time(
        db=db,
        user_id=str(current_user.id),
        captured_at_utc=captured_at_utc,
        provided_local_time=user_local_time,
    )
    time_of_day = _time_of_day(local_dt)
    day_of_week = local_dt.strftime("%A")
    session_id = f"ses_{uuid.uuid4().hex}"

    try:
        stress_0_100 = int(analysis.get("stress_level", 0))
    except Exception:
        stress_0_100 = 0
    stress_0_100 = max(0, min(100, stress_0_100))
    stress_1_5 = _stress_score_to_1_5(stress_0_100)

    symptom_flags = {
        "session_id": session_id,
        "analyzed_at": analyzed_at.isoformat(),
        "user_local_time": local_dt.isoformat(),
        "time_of_day": time_of_day,
        "day_of_week": day_of_week,
        "stress_score_0_100": stress_0_100,
        "secondary_emotions": analysis.get("secondary_emotions") if isinstance(analysis.get("secondary_emotions"), list) else [],
        "key_stress_indicators": analysis.get("key_stress_indicators") if isinstance(analysis.get("key_stress_indicators"), list) else [],
        "urgency_level": urgency_level,
        "summary": summary,
        "analysis_version": "mood_checkin_v1",
        "transcribe_job_name": transcribe_result.job_name,
        "transcribe_media_format": transcribe_result.media_format,
    }

    meta = agent_response.metadata or {}
    if meta:
        try:
            await TokenUsageService.track_token_usage(
                db=db,
                user=current_user,
                model_name=meta.get("model_name", "unknown"),
                agent_type="mood_checkin_agent",
                input_tokens=meta.get("input_tokens", 0),
                output_tokens=meta.get("output_tokens", 0),
                total_tokens=meta.get("total_tokens", 0),
                endpoint="/api/v1/health/mood/checkin",
            )
        except Exception:
            pass

    saved = await HealthTimelineService.create_mood_checkin(
        db=db,
        user_id=current_user.id,
        audio_filename=audio.filename,
        transcript=transcript_text,
        mood_label=primary_emotion,
        stress_level_1_5=stress_1_5,
        symptom_flags=symptom_flags,
        captured_at=captured_at_utc,
        source="audio",
    )

    return MoodCheckInResponse(
        mood_checkin_id=str(saved.id),
        user_id=str(current_user.id),
        session_id=session_id,
        captured_at=saved.captured_at,
        analyzed_at=analyzed_at,
        user_local_time=local_dt,
        time_of_day=time_of_day,
        day_of_week=day_of_week,
        transcript=transcript_text,
        primary_emotion=primary_emotion,
        secondary_emotions=symptom_flags["secondary_emotions"],
        stress_level=stress_0_100,
        key_stress_indicators=symptom_flags["key_stress_indicators"],
        urgency_level=urgency_level,
        summary=summary,
    )


@router.get(
    "/mood/history",
    response_model=PaginatedMoodHistoryResponse,
    summary="Get mood check-in history",
)
async def get_mood_history(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date cannot be after end_date")

    payload = await HealthTimelineService.get_mood_history(
        db=db,
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )

    items: list[MoodHistoryItem] = []
    for row in payload["items"]:
        flags = row.symptom_flags or {}
        stress_0_100 = flags.get("stress_score_0_100")
        try:
            stress_0_100 = int(stress_0_100) if stress_0_100 is not None else None
        except Exception:
            stress_0_100 = None

        analyzed_at = None
        try:
            analyzed_raw = flags.get("analyzed_at")
            if isinstance(analyzed_raw, str) and analyzed_raw:
                analyzed_at = datetime.fromisoformat(analyzed_raw)
        except Exception:
            analyzed_at = None

        local_time = None
        try:
            local_raw = flags.get("user_local_time")
            if isinstance(local_raw, str) and local_raw:
                local_time = datetime.fromisoformat(local_raw)
        except Exception:
            local_time = None

        items.append(
            MoodHistoryItem(
                mood_checkin_id=str(row.id),
                user_id=str(current_user.id),
                session_id=flags.get("session_id"),
                captured_at=row.captured_at,
                analyzed_at=analyzed_at,
                user_local_time=local_time,
                time_of_day=flags.get("time_of_day"),
                day_of_week=flags.get("day_of_week"),
                transcript=row.transcript,
                primary_emotion=row.mood_label,
                secondary_emotions=flags.get("secondary_emotions") or [],
                stress_level=stress_0_100,
                key_stress_indicators=flags.get("key_stress_indicators") or [],
                urgency_level=flags.get("urgency_level"),
                summary=flags.get("summary"),
                raw=flags,
            )
        )

    return PaginatedMoodHistoryResponse(
        items=items,
        total_count=payload["total_count"],
        page=payload["page"],
        page_size=payload["page_size"],
        total_pages=payload["total_pages"],
    )


@router.get("/insights/daily", response_model=PeriodInsightsResponse)
async def get_daily_insights(
    target_date: date | None = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    target_date = target_date or date.today()
    start_datetime = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    end_datetime = datetime.combine(target_date, time.max, tzinfo=timezone.utc)
    return await HealthTimelineService.get_period_insights(
        db=db,
        user_id=current_user.id,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        label="daily",
    )


@router.get("/insights/weekly", response_model=PeriodInsightsResponse)
async def get_weekly_insights(
    end_date: date | None = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    end_date = end_date or date.today()
    end_datetime = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
    start_datetime = end_datetime - timedelta(days=6)
    return await HealthTimelineService.get_period_insights(
        db=db,
        user_id=current_user.id,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        label="weekly",
    )


@router.get("/insights/monthly", response_model=PeriodInsightsResponse)
async def get_monthly_insights(
    end_date: date | None = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    end_date = end_date or date.today()
    end_datetime = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
    start_datetime = end_datetime - timedelta(days=29)
    return await HealthTimelineService.get_period_insights(
        db=db,
        user_id=current_user.id,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        label="monthly",
    )


@router.post("/diet-plan/generate", response_model=DietPlanResponse)
async def generate_diet_plan(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        plan = await DietPlanService.generate_diet_plan(db, current_user.id, trigger="manual")
        return plan
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/diet-plan/current", response_model=DietPlanResponse)
async def get_current_diet_plan(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    plan = await DietPlanService.get_current_plan(db, current_user.id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active diet plan found")
    return plan


@router.get("/diet-plan/history", response_model=List[DietPlanResponse])
async def get_diet_plan_history(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    history = await DietPlanService.get_plan_history(db, current_user.id)
    return history


@router.get("/diet-plan/today", response_model=List[DietPlanMealSchema])
async def get_todays_diet_plan_meals(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    meals = await DietPlanService.get_todays_plan_meals(db, current_user.id)
    return meals


@router.post("/daily-summary/generate", response_model=DailySummaryResponse)
async def generate_daily_summary(
    request: DailySummaryCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        target_date = date.fromisoformat(request.summary_date)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="summary_date must be YYYY-MM-DD") from exc

    summary = await DailySummaryService.generate_summary(db, current_user.id, target_date)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not enough data to generate a summary for this date. Log meals or vitals first.",
        )
    return summary


@router.get("/daily-summary", response_model=DailySummaryResponse)
async def get_daily_summary(
    target_date: date | None = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    target_date = target_date or date.today()
    summary = await DailySummaryService.get_summary(db, current_user.id, target_date)
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No summary found for this date")
    return summary


@router.get("/daily-summary/recent", response_model=List[DailySummaryResponse])
async def get_recent_daily_summaries(
    limit: int = Query(default=7, ge=1, le=30),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return await DailySummaryService.get_recent_summaries(db, current_user.id, limit=limit)
