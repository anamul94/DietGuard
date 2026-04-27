"""
Recipe Suggestion Routes

API endpoints for AI-powered recipe generation based on doctor-prescribed diet restrictions.
"""

from datetime import date
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Query, Form
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.recipe_schemas import (
    DietProfileCreateRequest,
    DietProfileUpdateRequest,
    DietProfileResponse,
    RecipeGenerateRequest,
    WeeklyScheduleGenerateRequest,
    RecipeResponse,
    WeeklyScheduleWithRecipesResponse,
    RecipeTrackRequest,
    RecipeTrackResponse,
)
from ..schemas.ai_schemas import ErrorResponse
from ...infrastructure.database.database import get_db
from ...infrastructure.database.auth_models import User
from ...infrastructure.auth.dependencies import get_current_active_user
from ...application.services.recipe_service import RecipeService
from ...application.services.subscription_service import SubscriptionService
from ...infrastructure.utils.logger import logger
from ...infrastructure.utils.image_utils import encode_image_to_base64
import base64


router = APIRouter(prefix="/recipes", tags=["Recipe Suggestion"])

DIET_CHART_UPLOAD_SCHEMA = {
    "content": {
        "multipart/form-data": {
            "schema": {
                "type": "object",
                "required": ["file"],
                "properties": {
                    "file": {
                        "type": "string",
                        "format": "binary",
                        "description": "Diet chart image or PDF",
                    },
                    "profile_name": {
                        "type": "string",
                        "description": "Optional name for the diet profile",
                    },
                },
            }
        }
    },
    "required": True,
}


@router.post(
    "/diet-profiles/upload",
    response_model=dict,
    summary="Upload Diet Chart for Extraction",
    description="""
    Upload a doctor's diet chart, prescription, or nutritionist recommendation for AI extraction.
    
    **Supported Formats:** JPG, JPEG, PNG, WebP, PDF
    
    **Process:**
    1. Document is analyzed by AI to extract diet restrictions
    2. Extracted restrictions include: foods to avoid, limit, and allowed
    3. Returns extracted data for user confirmation
    
    **Returns:**
    - profile: Created diet profile with extraction_status='pending'
    - extraction_confidence: high/medium/low
    - unreadable_sections: parts that couldn't be clearly read
    """,
    responses={
        200: {"description": "Diet chart processed successfully"},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        413: {"description": "File too large"},
        422: {"description": "Invalid file format"},
    },
    openapi_extra={"requestBody": DIET_CHART_UPLOAD_SCHEMA},
)
async def upload_diet_chart(
    file: UploadFile = File(..., description="Diet chart image or PDF"),
    profile_name: Optional[str] = Form(default=None, description="Optional name for the diet profile"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a diet chart document for AI extraction."""
    try:
        logger.info(
            "Diet chart upload request",
            user_id=str(current_user.id),
            filename=file.filename,
            content_type=file.content_type,
        )
        
        try:
            limit_check = await SubscriptionService.check_upload_limit(db, current_user)
            logger.info(
                "Upload limit check passed",
                user_id=str(current_user.id),
                remaining=limit_check.get("remaining_uploads"),
            )
        except ValueError as e:
            logger.warning("Upload limit exceeded", user_id=str(current_user.id), error=str(e))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e),
            )
        
        allowed_mime_types = ["image/jpeg", "image/jpg", "image/png", "image/webp", "application/pdf"]
        if file.content_type not in allowed_mime_types:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported file type: {file.content_type}. Please upload JPG, PNG, WebP, or PDF.",
            )
        
        if file.content_type == "application/pdf":
            pdf_bytes = await file.read()
            file_data = base64.b64encode(pdf_bytes).decode('utf-8')
            mime_type = "application/pdf"
            file_type = "file"
        else:
            img_result = encode_image_to_base64(file)
            file_data = img_result["base64_string"]
            mime_type = img_result["mime_type"]
            file_type = "image"
        
        result = await RecipeService.upload_diet_chart(
            db=db,
            user_id=current_user.id,
            file_data=file_data,
            file_type=file_type,
            mime_type=mime_type,
            profile_name=profile_name,
        )
        
        await SubscriptionService.increment_upload_count(db, current_user)
        
        return result
        
    except ValueError as e:
        logger.error("Diet chart upload failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "Diet chart upload error",
            error=str(e),
            user_id=str(current_user.id),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process diet chart. Please try again.",
        )


@router.post(
    "/diet-profiles/manual",
    response_model=DietProfileResponse,
    summary="Create Diet Profile Manually",
    description="Manually create a diet profile by entering restrictions and preferences directly.",
)
async def create_diet_profile_manually(
    request: DietProfileCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a diet profile with manually entered data."""
    try:
        result = await RecipeService.create_diet_profile_manually(
            db=db,
            user_id=current_user.id,
            profile_data=request.model_dump(),
        )
        return result
    except Exception as e:
        logger.error("Manual profile creation failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/diet-profiles",
    response_model=List[DietProfileResponse],
    summary="Get All Diet Profiles",
    description="Get all diet profiles for the current user.",
)
async def get_diet_profiles(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all diet profiles for the current user."""
    return await RecipeService.get_diet_profiles(db, current_user.id)


@router.get(
    "/diet-profiles/active",
    response_model=DietProfileResponse,
    summary="Get Active Diet Profile",
    description="Get the user's currently active diet profile.",
)
async def get_active_diet_profile(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the user's active diet profile."""
    result = await RecipeService.get_active_diet_profile(db, current_user.id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active diet profile found",
        )
    return result


@router.get(
    "/diet-profiles/{profile_id}",
    response_model=DietProfileResponse,
    summary="Get Diet Profile by ID",
    description="Get a specific diet profile by ID.",
)
async def get_diet_profile(
    profile_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific diet profile."""
    result = await RecipeService.get_diet_profile(db, profile_id, current_user.id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diet profile not found",
        )
    return result


@router.patch(
    "/diet-profiles/{profile_id}",
    response_model=DietProfileResponse,
    summary="Update Diet Profile",
    description="""
    Update a diet profile.
    
    Use this to:
    - Confirm extracted restrictions after review
    - Edit restrictions
    - Set cuisine and cooking preferences
    """,
)
async def update_diet_profile(
    profile_id: str,
    request: DietProfileUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a diet profile."""
    try:
        result = await RecipeService.update_diet_profile(
            db=db,
            profile_id=profile_id,
            user_id=current_user.id,
            update_data=request.model_dump(exclude_unset=True),
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/suggest",
    response_model=RecipeResponse,
    summary="Generate Single Recipe (On-Demand)",
    description="""
    Generate a single recipe based on diet restrictions.
    
    Provide the diet profile ID and meal type to get a personalized recipe.
    """,
)
async def suggest_recipe(
    request: RecipeGenerateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate an on-demand recipe suggestion."""
    try:
        result = await RecipeService.generate_recipe(
            db=db,
            user_id=current_user.id,
            diet_profile_id=request.diet_profile_id,
            meal_type=request.meal_type or "lunch",
            cuisine_override=request.cuisine_override,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Recipe generation failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate recipe. Please try again.",
        )


@router.post(
    "/generate-schedule",
    response_model=WeeklyScheduleWithRecipesResponse,
    summary="Generate Weekly Meal Schedule",
    description="""
    Generate a complete weekly meal schedule based on diet restrictions.
    
    Creates recipes for all meals across 7 days and returns the full schedule.
    """,
)
async def generate_weekly_schedule(
    request: WeeklyScheduleGenerateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a weekly meal schedule."""
    try:
        result = await RecipeService.generate_weekly_schedule(
            db=db,
            user_id=current_user.id,
            diet_profile_id=request.diet_profile_id,
            week_start_date=request.week_start_date,
            cuisine_override=request.cuisine_override,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Schedule generation failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate schedule. Please try again.",
        )


@router.get(
    "/schedules/current",
    response_model=WeeklyScheduleWithRecipesResponse,
    summary="Get Current Weekly Schedule",
    description="Get the user's current active weekly meal schedule with recipe details.",
)
async def get_current_schedule(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current weekly schedule."""
    result = await RecipeService.get_current_schedule(db, current_user.id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active weekly schedule found",
        )
    return result


@router.get(
    "",
    response_model=List[RecipeResponse],
    summary="Get Recipe History",
    description="Get user's saved recipes (history and favorites).",
)
async def get_recipes(
    meal_type: Optional[str] = Query(default=None, description="Filter by meal type"),
    favorites_only: bool = Query(default=False, description="Only return favorites"),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's recipe history."""
    return await RecipeService.get_recipes(
        db=db,
        user_id=current_user.id,
        meal_type=meal_type,
        favorites_only=favorites_only,
        limit=limit,
    )


@router.get(
    "/{recipe_id}",
    response_model=RecipeResponse,
    summary="Get Recipe by ID",
    description="Get a specific recipe with full details.",
)
async def get_recipe(
    recipe_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific recipe."""
    result = await RecipeService.get_recipe(db, recipe_id, current_user.id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found",
        )
    return result


@router.patch(
    "/{recipe_id}/favorite",
    response_model=RecipeResponse,
    summary="Toggle Recipe Favorite",
    description="Toggle a recipe's favorite status.",
)
async def toggle_recipe_favorite(
    recipe_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle recipe favorite status."""
    try:
        return await RecipeService.toggle_recipe_favorite(db, recipe_id, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/{recipe_id}/track",
    response_model=RecipeTrackResponse,
    summary="Track Recipe to Meal Tracker",
    description="""
    Track a recipe - add it to the existing meal tracker.
    
    Status options:
    - cooked: User prepared the recipe
    - ate: User ate the meal
    - skipped: User skipped this meal
    - replaced: User ate something else instead
    
    When status is 'cooked' or 'ate', the recipe's nutrition is added to the meal tracker.
    """,
)
async def track_recipe(
    recipe_id: str,
    request: RecipeTrackRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Track a recipe to the meal tracker."""
    try:
        result = await RecipeService.track_recipe(
            db=db,
            user_id=current_user.id,
            recipe_id=recipe_id,
            scheduled_date=request.scheduled_date,
            status=request.status,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
