"""
Structured health timeline routes.
"""

from datetime import date, datetime, time, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...application.services.health_timeline_service import HealthTimelineService, group_food_items_for_review, parse_vitals_csv
from ...application.services.nutrition_target_service import NutritionTargetService
from ...application.services.patient_service import PatientService
from ...infrastructure.agents.food_agent import food_agent
from ...infrastructure.agents.nutrition_calculator_agent import nutrition_calculator_agent
from ...infrastructure.auth.dependencies import get_current_active_user
from ...infrastructure.database.auth_models import User
from ...infrastructure.database.database import get_db
from ...infrastructure.utils.image_utils import encode_image_to_base64
from ...infrastructure.utils.logger import logger
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
)


router = APIRouter(tags=["Health Timeline"])


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
    logger.info("Meal confirmation requested", user_id=str(current_user.id), item_count=len(request.items))
    calculator_input = []
    for item in request.items:
        description = item.name
        if item.quantity:
            description = f"{item.quantity} {description}"
        if item.preparation:
            description = f"{description} ({item.preparation})"
        calculator_input.append(description)

    agent_response = await nutrition_calculator_agent(calculator_input)
    if not agent_response.success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=agent_response.error_message)

    hour, minute = map(int, request.meal_time.split(":"))
    meal_event = await HealthTimelineService.create_meal_event(
        db=db,
        user_id=current_user.id,
        meal_type=request.meal_type,
        meal_date=request.meal_date,
        meal_time_value=time(hour=hour, minute=minute),
        items=[item.model_dump() for item in request.items],
        nutrition=agent_response.data["nutrition"],
        fooditem_details=agent_response.data.get("fooditem_details", []),
        source_filenames=request.source_filenames,
        notes=request.notes,
        source="confirmed_meal",
    )

    return {
        "meal_event_id": str(meal_event.id),
        "meal_type": meal_event.meal_type,
        "meal_date": meal_event.meal_date.isoformat(),
        "meal_time": request.meal_time,
        "food_analysis": agent_response.data,
        "source_filenames": request.source_filenames,
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
