"""
AI Agent Routes

This module contains API endpoints for AI-powered food and medical report analysis.
All endpoints require authentication and enforce subscription limits.
"""

from typing import Annotated, List

from datetime import date as date_type, datetime, timezone

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.food_schemas import FoodUploadResponse
from ..schemas.nutrition_schemas import NutritionAdviceRequest, NutritionAdviceResponse
from ..schemas.ai_schemas import ErrorResponse, SubscriptionLimitError
from ..schemas.nutrition_calculator_schemas import NutritionCalculationRequest, NutritionCalculationResponse
from ..schemas.ingredient_schemas import IngredientScanResponse
from ..schemas.health_schemas import PaginatedMealHistoryResponse, StructuredHealthProfileResponse
from ...infrastructure.database.database import get_db
from ...infrastructure.database.auth_models import User
from ...infrastructure.auth.dependencies import get_current_active_user
from ...application.services.subscription_service import SubscriptionService
from ...application.services.health_utils import (
    group_food_items_for_review,
    group_report_analyses_by_category,
    merge_dynamic_reports,
    parse_llm_json_payload,
)
from ...application.services.token_usage_service import TokenUsageService
from ...application.services.health_timeline_service import HealthTimelineService
from ...infrastructure.utils.logger import logger
from ...infrastructure.utils.nutrition_utils import extract_food_item_names, format_food_analysis_summary
from ...infrastructure.utils.image_utils import encode_image_to_base64, encode_pdf_to_base64
from ...infrastructure.agents.report_agent import report_agent
from ...infrastructure.agents.food_agent import food_agent
from ...infrastructure.agents.nutritionist_agent import nutritionist_agent
from ...infrastructure.agents.nutrition_calculator_agent import nutrition_calculator_agent
from ...infrastructure.agents.nutrition_recalculator_agent import nutrition_recalculator_agent
from ...infrastructure.agents.ingredient_scanner_agent import ingredient_scanner_agent


router = APIRouter(tags=["AI Agents"])

MULTI_FILE_UPLOAD_SCHEMA = {
    "content": {
        "multipart/form-data": {
            "schema": {
                "type": "object",
                "required": ["files"],
                "properties": {
                    "files": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "format": "binary",
                        },
                        "description": "One or more uploaded files",
                    }
                },
            }
        }
    },
    "required": True,
}


def _build_meal_items_from_food_analysis(food_analysis: dict) -> list[dict]:
    reviewed = group_food_items_for_review(food_analysis)
    return [
        {
            "name": item["name"],
            "quantity": item.get("quantity"),
            "role": item.get("role") or "main",
            "preparation": item.get("preparation"),
            "source_label": item.get("source_label"),
            "confidence": item.get("confidence"),
        }
        for item in reviewed["items"]
    ]


@router.post(
    "/upload-food",
    response_model=FoodUploadResponse,
    summary="Upload Food Images for AI Analysis",
    description="""
    Upload food images to get AI-powered nutritional analysis.
    
    **Authentication Required:** Yes (JWT Bearer token)
    
    **Subscription Limits:**
    - Free: 2 uploads/day
    - Trial: 20 uploads/day
    - Paid: 20 uploads/day
    
    **Supported Formats:** JPG, JPEG, PNG
    
    **Process:**
    1. Images are analyzed by AI food recognition agent
    2. Food items are identified with quantities
    3. Per-item and total nutritional information is calculated
    4. Structured response includes item names, item-level nutrition, and meal totals

    **Returns:**
    - user_email
    - files_processed count
    - filenames list
    - food_analysis object with `fooditem_details` and total `nutrition`
    """,
    responses={
        200: {
            "description": "Successful food analysis",
            "model": FoodUploadResponse
        },
        401: {
            "description": "Unauthorized - Invalid or missing JWT token",
            "model": ErrorResponse
        },
        403: {
            "description": "Forbidden - Daily upload limit reached",
            "model": SubscriptionLimitError
        },
        422: {
            "description": "Validation Error - Invalid file format"
        }
    },
    openapi_extra={"requestBody": MULTI_FILE_UPLOAD_SCHEMA},
)
async def upload_food(
    files: Annotated[List[UploadFile], File(description="Food images (JPG, PNG)")],
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload food images for AI-powered nutritional analysis.
    
    Requires authentication and enforces daily upload limits based on subscription.
    """
    try:
        logger.info(f"Food upload request from user {current_user.id}", file_count=len(files))
        
        # Check subscription limits
        try:
            limit_check = await SubscriptionService.check_upload_limit(db, current_user)
            logger.info("Upload limit check passed", user_id=str(current_user.id), 
                       remaining=limit_check.get("remaining_uploads"))
        except ValueError as e:
            logger.warning("Upload limit exceeded", user_id=str(current_user.id), error=str(e))
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
        
        allowed_extensions = {".jpg", ".jpeg", ".png"}
        
        # Validate and encode all files
        encoded_images = []
        filenames = []
        
        for file in files:
            file_extension = file.filename.split(".")[-1].lower()
            if f".{file_extension}" not in allowed_extensions:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid file type: {file.filename}. Only image files allowed",
                )
            
            encoded_data = encode_image_to_base64(file)
            encoded_images.append(encoded_data)
            filenames.append(file.filename)

        # Process all images together in one agent call
        data_list = [img["base64_string"] for img in encoded_images]
        type_list = ["image"] * len(encoded_images)
        mime_list = [img["mime_type"] for img in encoded_images]
        
        # Fetch user's location from patient profile for regional food context
        from ...application.services.patient_service import PatientService
        user_location = None
        try:
            patient_profile = await PatientService.get_patient_profile(db, current_user.id)
            persona_data = patient_profile.get("persona", {})
            user_location = persona_data.get("current_location")
            if user_location:
                logger.info("Using user location for food analysis", 
                           user_id=str(current_user.id), 
                           location=user_location)
        except Exception as e:
            # If location fetch fails, continue without it
            logger.warning("Failed to fetch user location, continuing without location context", 
                          user_id=str(current_user.id), 
                          error=str(e))
        
        food_analysis_response = await food_agent(data_list, type_list, mime_list, location=user_location)

        
        # Check if food analysis failed
        if not food_analysis_response.success:
            raise HTTPException(status_code=500, detail=food_analysis_response.error_message)
        
        # Extract food analysis data and metadata
        food_analysis = food_analysis_response.data
        metadata = food_analysis_response.metadata if hasattr(food_analysis_response, 'metadata') else {}
        
        # Track token usage
        if metadata:
            await TokenUsageService.track_token_usage(
                db=db,
                user=current_user,
                model_name=metadata.get("model_name", "unknown"),
                agent_type="food_agent",
                input_tokens=metadata.get("input_tokens", 0),
                output_tokens=metadata.get("output_tokens", 0),
                total_tokens=metadata.get("total_tokens", 0),
                endpoint="/api/v1/ai/upload-food",
                cache_creation_tokens=metadata.get("cache_creation_tokens", 0),
                cache_read_tokens=metadata.get("cache_read_tokens", 0)
            )
        
        # Increment upload count
        await SubscriptionService.increment_upload_count(db, current_user)

        result_data = {
            "user_email": current_user.email,
            "files_processed": len(files),
            "filenames": filenames,
            "food_analysis": food_analysis,
        }
        
        logger.info(f"Food analysis completed for user {current_user.id}", 
                   files_processed=len(filenames))
        
        return result_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Food upload error for user {current_user.id}", 
                    error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process food images. Please try again later."
        )


@router.post(
    "/scan-ingredients",
    response_model=IngredientScanResponse,
    summary="Scan Food Packaging Ingredients",
    description="""
    Upload food packaging images to scan and analyze ingredient lists.
    
    **Authentication Required:** Yes (JWT Bearer token)
    
    **Subscription Limits:**
    - Free: 2 scans/day
    - Trial: 20 scans/day
    - Paid: 20 scans/day
    
    **Supported Formats:** JPG, JPEG, PNG
    
    **Process:**
    1. AI reads ingredient list from packaging image
    2. Identifies each ingredient (including chemical names)
    3. Provides health ratings (🟢 Green, 🟡 Yellow, 🔴 Red)
    4. Explains ingredients in simple language
    5. Flags allergens, age restrictions, and dietary concerns
    
    **Returns:**
    - user_email
    - filename
    - ingredient_analysis with:
      - List of ingredients with health ratings
      - Short and detailed explanations
      - Allergen information
      - Age restrictions
      - Dietary compatibility (vegan, halal, kosher, etc.)
      - Overall product rating
      - Critical warnings
    """,
    responses={
        200: {
            "description": "Successful ingredient analysis",
            "model": IngredientScanResponse
        },
        401: {
            "description": "Unauthorized - Invalid or missing JWT token",
            "model": ErrorResponse
        },
        403: {
            "description": "Forbidden - Daily scan limit reached",
            "model": SubscriptionLimitError
        },
        422: {
            "description": "Validation Error - Invalid file format"
        }
    }
)
async def scan_ingredients(
    file: UploadFile = File(..., description="Food packaging image (JPG, PNG)"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Scan food packaging to extract and analyze ingredient lists.
    
    Requires authentication and enforces daily scan limits based on subscription.
    """
    try:
        logger.info(f"Ingredient scan request from user {current_user.id}", filename=file.filename)
        
        # Check subscription limits (using upload limit for now)
        try:
            limit_check = await SubscriptionService.check_upload_limit(db, current_user)
            logger.info("Ingredient scan limit check passed", user_id=str(current_user.id), 
                       remaining=limit_check.get("remaining_uploads"))
        except ValueError as e:
            logger.warning("Ingredient scan limit exceeded", user_id=str(current_user.id), error=str(e))
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
        
        # Validate file type
        allowed_extensions = {".jpg", ".jpeg", ".png"}
        file_extension = file.filename.split(".")[-1].lower()
        if f".{file_extension}" not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid file type: {file.filename}. Only image files (JPG, PNG) allowed",
            )
        
        # Encode image
        encoded_data = encode_image_to_base64(file)
        
        # Call ingredient scanner agent
        ingredient_response = await ingredient_scanner_agent(
            encoded_data["base64_string"],
            "image",
            encoded_data["mime_type"]
        )
        
        # Check if analysis failed
        if not ingredient_response.success:
            raise HTTPException(status_code=500, detail=ingredient_response.error_message)
        
        # Extract analysis data and metadata
        ingredient_analysis = ingredient_response.data
        metadata = ingredient_response.metadata if hasattr(ingredient_response, 'metadata') else {}
        
        # Track token usage
        if metadata:
            await TokenUsageService.track_token_usage(
                db=db,
                user=current_user,
                model_name=metadata.get("model_name", "unknown"),
                agent_type="ingredient_scanner_agent",
                input_tokens=metadata.get("input_tokens", 0),
                output_tokens=metadata.get("output_tokens", 0),
                total_tokens=metadata.get("total_tokens", 0),
                endpoint="/api/v1/ai/scan-ingredients",
                cache_creation_tokens=metadata.get("cache_creation_tokens", 0),
                cache_read_tokens=metadata.get("cache_read_tokens", 0)
            )
        
        # Increment upload count (using same counter as food uploads)
        await SubscriptionService.increment_upload_count(db, current_user)
        
        result_data = {
            "user_email": current_user.email,
            "filename": file.filename,
            "ingredient_analysis": ingredient_analysis,
        }
        
        logger.info(f"Ingredient scan completed for user {current_user.id}", 
                   filename=file.filename,
                   ingredients_count=len(ingredient_analysis.get('ingredients', [])),
                   overall_rating=ingredient_analysis.get('overall_rating'))
        
        return result_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingredient scan error for user {current_user.id}", 
                    error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to scan ingredients. Please try again later."
        )


@router.post(
    "/upload-report",
    response_model=None,  # Allow flexible response format
    status_code=status.HTTP_200_OK,
    summary="Upload Medical Reports",
    description="Upload medical reports (PDF or images) for AI-powered analysis with intelligent merging",
    openapi_extra={"requestBody": MULTI_FILE_UPLOAD_SCHEMA},
)
async def upload_report(
    files: Annotated[List[UploadFile], File(description="Medical reports (PDF or images)")],
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload medical reports for AI-powered analysis.
    
    Requires authentication and enforces daily upload limits based on subscription.
    """
    try:
        logger.info(f"Report upload request from user {current_user.id}", 
                   file_count=len(files))
        
        # Check subscription limits
        try:
            limit_check = await SubscriptionService.check_upload_limit(db, current_user)
            logger.info("Upload limit check passed", user_id=str(current_user.id))
        except ValueError as e:
            logger.warning("Upload limit exceeded", user_id=str(current_user.id), error=str(e))
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
        
        # Process files
        file_data_list = []
        filenames = []
        individual_analyses = []
        
        # Token tracking accumulators
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0
        model_name = None
        
        for file in files:
            # Validate file type
            file_extension = file.filename.split(".")[-1].lower()
            allowed_extensions = {"jpg", "jpeg", "png", "pdf"}
            
            if file_extension not in allowed_extensions:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid file type: {file.filename}. Only PDF and image files allowed"
                )
            
            # Handle PDF or image
            if file_extension == 'pdf':
                encoded_data = encode_pdf_to_base64(file)
                agent_response = await report_agent(
                    encoded_data["base64_string"], 
                    "image" , # Use 'image' type for PDFs - Bedrock treats them as images,
                    encoded_data["mime_type"]
                )
            else:  # image files
                encoded_data = encode_image_to_base64(file)
                agent_response = await report_agent(
                    encoded_data["base64_string"], 
                    "image", 
                    encoded_data["mime_type"]
                )
            
            # Extract analysis and metadata from AgentResponse
            if not agent_response.success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Report analysis failed: {agent_response.data}"
                )
            
            analysis = agent_response.data
            
            # Accumulate token usage
            if agent_response.metadata:
                total_input_tokens += agent_response.metadata.get("input_tokens", 0)
                total_output_tokens += agent_response.metadata.get("output_tokens", 0)
                total_tokens += agent_response.metadata.get("total_tokens", 0)
                if not model_name:
                    model_name = agent_response.metadata.get("model_name", "claude-sonnet-4.6")
            
            # Parse JSON output from report_agent (EHR format)
            analysis_dict = parse_llm_json_payload(analysis)
            if not isinstance(analysis_dict, dict):
                analysis_dict = {"raw_text": analysis}
            
            filenames.append(file.filename)
            individual_analyses.append({
                "filename": file.filename,
                "analysis": analysis_dict
            })
        
        
        combined_report = merge_dynamic_reports(
            [item.get("analysis", {}) for item in individual_analyses],
            filenames=filenames,
        )
        grouped_reports = group_report_analyses_by_category(individual_analyses)
        uploaded_at = datetime.now(timezone.utc).isoformat()

        structured_profiles = []
        for grouped_report in grouped_reports:
            try:
                structured_profile = await HealthTimelineService.sync_structured_report_data(
                    db=db,
                    user_id=current_user.id,
                    parsed_report=grouped_report.get("merged_report") or {},
                    filenames=grouped_report.get("filenames") or [],
                )
                structured_profiles.append(
                    {
                        **structured_profile,
                        "filenames": grouped_report.get("filenames") or [],
                    }
                )
                logger.info(
                    "Structured report data synced successfully",
                    user_id=str(current_user.id),
                    report_category=structured_profile.get("report_category"),
                    structured_version=structured_profile.get("version"),
                )
            except Exception as structured_error:
                logger.error(
                    "Structured report sync failed",
                    user_id=str(current_user.id),
                    report_category=grouped_report.get("report_category"),
                    filenames=grouped_report.get("filenames") or [],
                    error=str(structured_error),
                    exc_info=True,
                )
        latest_version = max((profile.get("version") or 0 for profile in structured_profiles), default=0) or None
        
        # Track token usage for report extraction
        await TokenUsageService.track_token_usage(
            db=db,
            user=current_user,
            model_name=model_name or "claude-sonnet-4.6",
            agent_type="report_agent",
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            total_tokens=total_tokens,
            endpoint="/api/v1/ai/upload-report"
        )
        
        # Increment upload count
        await SubscriptionService.increment_upload_count(db, current_user)
        
        logger.info(f"Report analysis completed for user {current_user.id}", 
                   files_processed=len(filenames),
                   version=latest_version)
        
        # Return response
        return {
            "files_processed": len(filenames),
            "filenames": filenames,
            "ehr_data": combined_report,
            "version": latest_version,
            "uploaded_at": uploaded_at,
            "structured_health_profile": structured_profiles[0] if len(structured_profiles) == 1 else None,
            "structured_health_profiles": structured_profiles,
        }

        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report upload error for user {current_user.id}", 
                    error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process medical reports: " + str(e) + ""
        )


@router.post(
    "/nutrition-advice",
    response_model=NutritionAdviceResponse,
    summary="Get AI Nutrition Advice",
    description="""
    Ask nutrition questions and get AI-powered personalized advice.
    
    **Authentication Required:** Yes (JWT Bearer token)
    
    **Subscription Limits:**
    - Free: 2 queries/day
    - Trial: 20 queries/day
    - Paid: 20 queries/day
    
    **Examples:**
    - "What should I eat for breakfast to lose weight?"
    - "How can I increase my protein intake?"
    - "What foods are good for lowering cholesterol?"
    
    **Returns:**
    - user_email
    - meal_type (if provided)
    - nutritionist_recommendations in markdown format
    """,
    responses={
        200: {
            "description": "Successful nutrition advice",
            "model": NutritionAdviceResponse
        },
        401: {
            "description": "Unauthorized - Invalid or missing JWT token",
            "model": ErrorResponse
        },
        403: {
            "description": "Forbidden - Daily query limit reached",
            "model": SubscriptionLimitError
        }
    }
)
async def get_nutrition_advice(
    request: NutritionAdviceRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get AI-powered nutrition advice based on food analysis and user profile.
    
    Requires authentication and enforces daily query limits based on subscription.
    User profile data (age, gender, weight, height) and medical report are fetched automatically.
    Food analysis is saved to database for future reference.
    """
    try:
        logger.info(f"Nutrition advice request from user {current_user.id}", 
                   meal_type=request.meal_type)
        
        # Check subscription limits for nutrition queries
        try:
            limit_check = await SubscriptionService.check_nutrition_limit(db, current_user)
            logger.info("Nutrition limit check passed", user_id=str(current_user.id))
        except ValueError as e:
            logger.warning("Nutrition query limit exceeded", user_id=str(current_user.id), error=str(e))
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
        
        from ...application.services.patient_service import PatientService
        
        # Get patient profile data (includes age, gender, etc.)
        patient_profile = await PatientService.get_patient_profile(db, current_user.id)
        
        # Extract patient data
        persona_data = patient_profile.get("persona", {})
        age = persona_data.get("age", 0) or 0
        gender = persona_data.get("gender") or "not specified"
        weight = persona_data.get("weight_kg")
        height = persona_data.get("height_cm")
        
        logger.info("Patient profile retrieved", user_id=str(current_user.id), 
                   age=age, gender=gender, has_weight=weight is not None, has_height=height is not None)
        
        medical_report = ""
        health_profile = await HealthTimelineService.get_current_health_profile(db, current_user.id)

        if health_profile["report"]["version"]:
            medical_report = health_profile["health_context_summary"]
            logger.info("Structured medical profile found for user", user_id=str(current_user.id))
        else:
            logger.info("No medical report found for user", user_id=str(current_user.id))
        
        # Prepare meal timing data
        from datetime import time as time_type
        meal_date = request.meal_date or date_type.today()
        
        # Parse meal_time string to time object (HH:MM -> time)
        hour, minute = map(int, request.meal_time.split(':'))
        meal_time = time_type(hour, minute)
        
        food_analysis_data = request.food_analysis.model_dump()
        meal_items = _build_meal_items_from_food_analysis(food_analysis_data)
        await HealthTimelineService.create_meal_event(
            db=db,
            user_id=current_user.id,
            meal_type=request.meal_type,
            meal_date=meal_date,
            meal_time_value=meal_time,
            items=meal_items,
            nutrition=food_analysis_data["nutrition"],
            fooditem_details=food_analysis_data.get("fooditem_details", []),
            source="nutrition_advice",
        )
        logger.info(
            "Food analysis saved to structured meal timeline",
            user_id=str(current_user.id),
            meal_time=request.meal_time,
            meal_date=str(meal_date),
            item_count=len(meal_items),
        )
        
        # Build a readable meal summary from the item-level nutrition structure
        fooditems = extract_food_item_names(food_analysis_data)
        fooditems_str = format_food_analysis_summary(food_analysis_data)
        
        # Extract nutrition values to pass to nutritionist agent
        nutrition_values = food_analysis_data.get("nutrition", {})
        
        logger.info("Calling nutritionist agent", 
                   age=age, 
                   gender=gender, 
                   has_medical_report=bool(medical_report),
                   food_item_count=len(fooditems),
                   has_nutrition=bool(nutrition_values),
                   meal_time=request.meal_time)
        
        # Call nutritionist agent with the structured meal summary, nutrition values, and meal timing
        nutritionist_response = await nutritionist_agent(
            food_analysis=fooditems_str,
            medical_report=medical_report,
            meal_type=request.meal_type,
            meal_time=request.meal_time,  # Pass meal time to agent
            gender=gender,
            age=age,
            weight=weight,
            height=height,
            nutrition_values=nutrition_values if nutrition_values else None
        )
        
        # Check if nutritionist agent failed
        if not nutritionist_response.success:
            raise HTTPException(status_code=500, detail=nutritionist_response.error_message)
        
        # Extract recommendations and metadata
        nutritionist_advice = nutritionist_response.data
        metadata = nutritionist_response.metadata if hasattr(nutritionist_response, 'metadata') else {}
        
        # Track token usage
        if metadata:
            await TokenUsageService.track_token_usage(
                db=db,
                user=current_user,
                model_name=metadata.get("model_name", "unknown"),
                agent_type="nutritionist_agent",
                input_tokens=metadata.get("input_tokens", 0),
                output_tokens=metadata.get("output_tokens", 0),
                total_tokens=metadata.get("total_tokens", 0),
                endpoint="/api/v1/ai/nutrition-advice",
                cache_creation_tokens=metadata.get("cache_creation_tokens", 0),
                cache_read_tokens=metadata.get("cache_read_tokens", 0)
            )
        
        # Increment nutrition query count
        await SubscriptionService.increment_nutrition_count(db, current_user)
        
        logger.info(f"Nutrition advice completed for user {current_user.id}")
        
        # Import MealInfo schema
        from ..schemas.nutrition_schemas import MealInfo
        
        return NutritionAdviceResponse(
            user_email=current_user.email,
            meal_type=request.meal_type,
            meal_info=MealInfo(
                meal_time=request.meal_time,
                meal_date=(request.meal_date or date_type.today()).isoformat()
            ),
            nutritionist_recommendations=nutritionist_advice
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Nutrition advice error for user {current_user.id}", 
                    error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate nutrition advice. Please try again later."
        )


@router.post(
    "/calculate-nutrition",
    response_model=NutritionCalculationResponse,
    summary="Calculate Nutrition from Food Item Names",
    description="""
    Calculate clinically accurate nutrition values from food item names (text input only).

    **Authentication Required:** Yes (JWT Bearer token)

    **Use Case:**
    Fresh nutrition calculation from text food item descriptions without image analysis.
    This is useful when users manually enter food items or for quick nutrition lookups.

    **Input Format:**
    - Provide food item names with quantities (e.g., "1 grilled chicken breast", "150g rice")
    - The agent will parse quantities and calculate nutrition accordingly
    - If no quantity is specified, standard serving sizes are used

    **Examples:**
    - "1 grilled chicken breast"
    - "2 slices whole wheat bread"
    - "150g cooked brown rice"

    **Returns:**
    - food_analysis object containing:
      - fooditem_details: Per-item nutrition values for each food item
      - nutrition: Clinically accurate total nutrition values

    **Note:** This endpoint does NOT save the meal. Use `/health/meals/confirm` to save.
    """,
    responses={
        200: {
            "description": "Successful nutrition calculation",
            "model": NutritionCalculationResponse
        },
        401: {
            "description": "Unauthorized - Invalid or missing JWT token",
            "model": ErrorResponse
        }
    }
)
async def calculate_nutrition(
    request: NutritionCalculationRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate nutrition values from food item names.

    Accepts food item names with quantities and returns clinically accurate nutrition data.
    This is a simple calculation without reference data (no old_food_analysis needed).
    """
    try:
        logger.info(f"Nutrition calculation request from user {current_user.id}",
                   item_count=len(request.fooditems))

        # Call nutrition calculator agent (simple, fresh calculation)
        nutrition_response = await nutrition_calculator_agent(fooditems=request.fooditems)

        # Check if agent failed
        if not nutrition_response.success:
            raise HTTPException(status_code=500, detail=nutrition_response.error_message)

        # Extract nutrition data and metadata
        nutrition_data = nutrition_response.data
        metadata = nutrition_response.metadata if hasattr(nutrition_response, 'metadata') else {}

        # Track token usage (but don't count against limits)
        if metadata:
            await TokenUsageService.track_token_usage(
                db=db,
                user=current_user,
                model_name=metadata.get("model_name", "unknown"),
                agent_type="nutrition_calculator_agent",
                input_tokens=metadata.get("input_tokens", 0),
                output_tokens=metadata.get("output_tokens", 0),
                total_tokens=metadata.get("total_tokens", 0),
                endpoint="/api/v1/ai/calculate-nutrition",
                cache_creation_tokens=metadata.get("cache_creation_tokens", 0),
                cache_read_tokens=metadata.get("cache_read_tokens", 0)
            )

        logger.info(f"Nutrition calculation completed for user {current_user.id}")

        return NutritionCalculationResponse(
            food_analysis={
                "fooditem_details": nutrition_data.get("fooditem_details", []),
                "nutrition": nutrition_data.get("nutrition", {})
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Nutrition calculation error for user {current_user.id}",
                    error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate nutrition. Please try again later."
        )


@router.post(
    "/recalculate-nutrition",
    response_model=NutritionCalculationResponse,
    summary="Recalculate Nutrition from Corrected Food Items",
    description="""
    Recalculate clinically accurate nutrition values when users correct AI-identified foods.

    **Authentication Required:** Yes (JWT Bearer token)

    **Use Case:**
    After the AI extracts food items from images via `/draft-from-image`, users can correct the identified foods.
    This endpoint recalculates nutrition values for the corrected food items with accurate macros and calories.

    **Flow:**
    1. User uploads meal images → `/draft-from-image` returns AI-extracted foods
    2. User reviews and corrects food names/quantities in the UI
    3. User calls this endpoint with corrected items → receives updated nutrition
    4. User confirms meal → nutrition values are saved

    **Input Format:**
    - Provide corrected food item names with quantities (e.g., "1 grilled chicken with naan roti")
    - The agent will parse quantities and calculate nutrition accordingly
    - If no quantity is specified, standard serving sizes are used

    **Examples:**
    - "1 grilled chicken with naan roti"
    - "2 slices pizza with cheese and tomato"
    - "150g brown rice with vegetables"

    **Returns:**
    - food_analysis object containing:
      - fooditem_details: Per-item nutrition values for each identified food item
      - nutrition: Clinically accurate total nutrition values

    **Note:** This endpoint tracks usage but does not count against daily limits.
    """,
    responses={
        200: {
            "description": "Successful nutrition recalculation",
            "model": NutritionCalculationResponse
        },
        401: {
            "description": "Unauthorized - Invalid or missing JWT token",
            "model": ErrorResponse
        }
    }
)
async def recalculate_nutrition(
    request: NutritionCalculationRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Recalculate nutrition values after user corrects AI-identified food items.

    Accepts corrected food item names with quantities and returns updated clinically accurate nutrition data.
    If `old_food_analysis` is provided (from the original AI extraction), it is used as reference context
    to maintain calculation consistency.
    """
    try:
        logger.info(f"Nutrition recalculation request from user {current_user.id}",
                   item_count=len(request.fooditems),
                   has_old_analysis=request.old_food_analysis is not None)

        # Validate that old_food_analysis is provided (required for recalculation)
        if not request.old_food_analysis:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="old_food_analysis is required for nutrition recalculation. Use this endpoint only for correcting AI-extracted foods."
            )

        # Call nutrition recalculator agent (specialized for correction flow)
        nutrition_response = await nutrition_recalculator_agent(
            corrected_fooditems=request.fooditems,
            old_food_analysis=request.old_food_analysis
        )

        # Check if agent failed
        if not nutrition_response.success:
            raise HTTPException(status_code=500, detail=nutrition_response.error_message)

        # Extract nutrition data and metadata
        nutrition_data = nutrition_response.data
        metadata = nutrition_response.metadata if hasattr(nutrition_response, 'metadata') else {}

        # Track token usage (but don't count against limits)
        if metadata:
            await TokenUsageService.track_token_usage(
                db=db,
                user=current_user,
                model_name=metadata.get("model_name", "unknown"),
                agent_type="nutrition_recalculator_agent",
                input_tokens=metadata.get("input_tokens", 0),
                output_tokens=metadata.get("output_tokens", 0),
                total_tokens=metadata.get("total_tokens", 0),
                endpoint="/api/v1/ai/recalculate-nutrition",
                cache_creation_tokens=metadata.get("cache_creation_tokens", 0),
                cache_read_tokens=metadata.get("cache_read_tokens", 0)
            )

        logger.info(f"Nutrition recalculation completed for user {current_user.id}")
        
        return NutritionCalculationResponse(
            food_analysis={
                "fooditem_details": nutrition_data.get("fooditem_details", []),
                "nutrition": nutrition_data.get("nutrition", {})
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Nutrition calculation error for user {current_user.id}", 
                    error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate nutrition values. Please try again later."
        )


@router.get(
    "/report-data",
    response_model=StructuredHealthProfileResponse,
    summary="Get My Structured Report Data",
    description="""
    Retrieve the current structured health profile derived from uploaded reports.
    
    **Authentication Required:** Yes (JWT Bearer token)
    
    **Returns:**
    - Latest uploaded report metadata
    - All active current-category reports
    - Merged snapshots, labs, medications, and entities
    """,
    tags=["AI Agents"]
)
async def get_my_report_data(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    logger.info("Structured report data requested", user_id=str(current_user.id))
    profile = await HealthTimelineService.get_current_health_profile(db, current_user.id)
    if not profile["report"]["version"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No structured medical report found")
    return profile


@router.delete(
    "/report-data",
    summary="Delete My Structured Report Data",
    description="""
    Delete all structured medical report history for the authenticated user.
    
    **Authentication Required:** Yes (JWT Bearer token)
    
    **Returns:**
    - Success message with deleted report count
    """,
    tags=["AI Agents"]
)
async def delete_my_report_data(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    logger.info("Structured report deletion requested", user_id=str(current_user.id))
    deleted_count = await HealthTimelineService.delete_report_history(db, current_user.id)
    if deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No report history found to delete")
    return {"message": "Structured report history deleted successfully", "deleted_count": deleted_count}


@router.get(
    "/nutrition-data",
    response_model=PaginatedMealHistoryResponse,
    summary="Get Nutrition Data with Pagination",
    description="""
    Retrieve structured meal history with pagination and date filtering.
    
    **Authentication Required:** Yes (JWT Bearer token)
    
    **Query Parameters:**
    - `start_date`: Filter records from this date (format: YYYY-MM-DD, example: 2025-12-01)
    - `end_date`: Filter records until this date (format: YYYY-MM-DD, example: 2025-12-27)
    - `page`: Page number (default: 1, example: 1)
    - `page_size`: Items per page (default: 10, max: 100, example: 10)
    
    **Returns:**
    - Paginated list of nutrition analyses
    - Total count and page information
    - Records sorted by newest first
    
    **Example Request:**
    ```
    GET /api/v1/ai/nutrition-data?start_date=2026-03-01&end_date=2026-03-14&page=1&page_size=10
    ```
    """,
    responses={
        200: {
            "description": "Successfully retrieved nutrition data"
        },
        401: {
            "description": "Unauthorized - Invalid or missing JWT token"
        }
    }
)
async def get_nutrition_data_paginated(
    start_date: date_type | None = Query(
        None, 
        description="Start date filter (format: YYYY-MM-DD)",
        examples=["2026-03-01"],
    ),
    end_date: date_type | None = Query(
        None, 
        description="End date filter (format: YYYY-MM-DD)",
        examples=["2026-03-14"],
    ),
    page: int = Query(
        1, 
        ge=1, 
        description="Page number (1-indexed)",
        examples=[1],
    ),
    page_size: int = Query(
        10, 
        ge=1, 
        le=100, 
        description="Items per page (max 100)",
        examples=[10],
    ),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get paginated structured meal history for the authenticated user.
    """
    try:
        if start_date and end_date and start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date cannot be after end_date",
            )

        logger.info(
            "Fetching paginated structured meal history",
            user_id=str(current_user.id),
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
            page=page,
            page_size=page_size,
        )

        return await HealthTimelineService.get_meal_history(
            db=db,
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to retrieve structured meal history",
            user_id=str(current_user.id),
            error=str(e),
            exception_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve meal history. Please try again later."
        )


@router.get(
    "/nutrition-data/today",
    response_model=PaginatedMealHistoryResponse,
    summary="Get Today's Nutrition Data",
    description="""
    Retrieve today's structured meal history for the authenticated user.
    
    **Authentication Required:** Yes (JWT Bearer token)
    
    **Returns:**
    - Today's confirmed meal entries
    - Sorted by newest first
    """,
    responses={
        200: {
            "description": "Successfully retrieved today's nutrition data"
        },
        401: {
            "description": "Unauthorized - Invalid or missing JWT token"
        }
    }
)
async def get_todays_nutrition_data(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get today's structured meal history for the authenticated user.
    """
    try:
        target_date = datetime.now(timezone.utc).date()
        logger.info(
            "Fetching today's structured meal history",
            user_id=str(current_user.id),
            target_date=target_date.isoformat(),
        )
        return await HealthTimelineService.get_meal_history(
            db=db,
            user_id=current_user.id,
            start_date=target_date,
            end_date=target_date,
            page=1,
            page_size=100,
        )
    except Exception as e:
        logger.error(
            "Failed to retrieve today's structured meal history",
            user_id=str(current_user.id),
            error=str(e),
            exception_type=type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve today's meal history. Please try again later."
        )
