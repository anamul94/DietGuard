"""
AI Agent Routes

This module contains API endpoints for AI-powered food and medical report analysis.
All endpoints require authentication and enforce subscription limits.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, status, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.food_schemas import FoodUploadResponse, FoodAnalysis
from ..schemas.nutrition_schemas import NutritionAdviceRequest, NutritionAdviceResponse
from ..schemas.ai_schemas import ReportUploadResponse, ErrorResponse, SubscriptionLimitError
from ..schemas.nutrition_calculator_schemas import NutritionCalculationRequest, NutritionCalculationResponse
from ...infrastructure.database.database import get_db
from ...infrastructure.database.auth_models import User
from ...infrastructure.auth.dependencies import get_current_active_user
from ...application.services.subscription_service import SubscriptionService
from ...application.services.token_usage_service import TokenUsageService
from ...infrastructure.utils.logger import logger
from ...infrastructure.utils.image_utils import encode_image_to_base64, encode_pdf_to_base64
from ...infrastructure.agents.food_agent import food_agent
from ...infrastructure.agents.nutritionist_agent import nutritionist_agent
from ...infrastructure.agents.report_agent import report_agent
from ...infrastructure.agents.summary_agent import summary_agent
from ...infrastructure.agents.nutrition_calculator_agent import nutrition_calculator_agent
from ...infrastructure.database.postgres_client import PostgresClient

router = APIRouter(tags=["AI Agents"])


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
    3. Nutritional information is calculated
    4. Structured response with food_items and nutrition
    
    **Returns:**
    - user_email
    - files_processed count
    - filenames list
    - food_analysis object with food_items and nutrition
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
    }
)
async def upload_food(
    files: List[UploadFile] = File(..., description="Food images (JPG, PNG)"),
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
        
        food_analysis_response = await food_agent(data_list, type_list, mime_list)
        
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
    "/upload-report",
    response_model=ReportUploadResponse,
    summary="Upload Medical Reports for AI Analysis",
    description="""
    Upload medical reports (PDF or images) for AI-powered analysis.
    
    **Authentication Required:** Yes (JWT Bearer token)
    
    **Subscription Limits:**
    - Free: 2 uploads/day
    - Trial: 20 uploads/day
    - Paid: 20 uploads/day
    
    **Supported Formats:** PDF, JPG, JPEG, PNG
    
    **Process:**
    1. Reports are analyzed by AI medical analysis agent
    2. Key findings are extracted from each report
    3. Combined summary is generated
    4. Health recommendations are provided
    
    **Returns:**
    - files_processed count
    - filenames list
    - individual_analyses for each report
    - combined_summary of all reports
    """,
    responses={
        200: {
            "description": "Successful report analysis",
            "model": ReportUploadResponse
        },
        401: {
            "description": "Unauthorized - Invalid or missing JWT token",
            "model": ErrorResponse
        },
        403: {
            "description": "Forbidden - Daily upload limit reached",
            "model": SubscriptionLimitError
        }
    }
)
async def upload_report(
    files: List[UploadFile] = File(..., description="Medical reports (PDF or images)"),
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
        
        for file in files:
            content = await file.read()
            
            # Handle PDF or image
            if file.content_type == 'application/pdf':
                base64_data = encode_pdf_to_base64(content)
            elif file.content_type and file.content_type.startswith('image/'):
                base64_data = encode_image_to_base64(content)
            else:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid file type: {file.filename}. Only PDF and images are allowed."
                )
            
            file_data_list.append(base64_data)
            filenames.append(file.filename)
            
            # Analyze individual report
            logger.info(f"Analyzing report: {file.filename}")
            analysis = await report_agent(base64_data)
            
            individual_analyses.append({
                "filename": file.filename,
                "analysis": analysis.get("analysis", "No analysis available")
            })
        
        # Generate combined summary
        logger.info("Generating combined summary")
        combined_summary = await summary_agent(
            [a["analysis"] for a in individual_analyses]
        )
        
        # Track token usage
        await TokenUsageService.track_token_usage(
            db=db,
            user=current_user,
            model_name="gemini-pro",
            agent_type="report_agent",
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            endpoint="/api/v1/ai/upload-report"
        )
        
        # Increment upload count
        await SubscriptionService.increment_upload_count(db, current_user)
        
        logger.info(f"Report analysis completed for user {current_user.id}", 
                   files_processed=len(filenames))
        
        return ReportUploadResponse(
            files_processed=len(filenames),
            filenames=filenames,
            individual_analyses=individual_analyses,
            combined_summary=combined_summary if isinstance(combined_summary, str) else combined_summary.get("summary", "No summary available")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report upload error for user {current_user.id}", 
                    error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process medical reports. Please try again later."
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
        
        # Import date utility
        from ...infrastructure.utils.date_utils import calculate_age
        from datetime import datetime, timezone
        import json
        
        # Calculate age from date of birth
        age = calculate_age(current_user.date_of_birth)
        if age is None:
            logger.warning("User has no date of birth", user_id=str(current_user.id))
            age = 0  # Default age if not provided
        
        # Get user profile data
        gender = current_user.gender or "not specified"
        weight = float(current_user.weight) if current_user.weight else None
        height = float(current_user.height) if current_user.height else None
        
        # Check for medical report
        postgres_client = PostgresClient()
        report_data = await postgres_client.get_report_data(str(current_user.id))
        medical_report = ""
        
        if report_data:
            # Extract medical report summary from stored data
            data = report_data.get("data", {})
            medical_report = data.get("combined_summary", "")
            logger.info("Medical report found for user", user_id=str(current_user.id))
        else:
            logger.info("No medical report found for user", user_id=str(current_user.id))
        
        # Save food_analysis to database
        food_analysis_data = request.food_analysis.model_dump()
        await postgres_client.save_nutrition_data(
            user_id=str(current_user.id),
            data={
                "food_analysis": food_analysis_data,
                "meal_type": request.meal_type,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        logger.info("Food analysis saved to database", user_id=str(current_user.id))
        
        # Extract only fooditems for nutritionist agent
        fooditems = food_analysis_data.get("fooditems", [])
        fooditems_str = ", ".join(fooditems) if fooditems else "No food items identified"
        
        # Extract nutrition values to pass to nutritionist agent
        nutrition_values = food_analysis_data.get("nutrition", {})
        
        logger.info("Calling nutritionist agent", 
                   age=age, 
                   gender=gender, 
                   has_medical_report=bool(medical_report),
                   fooditems_count=len(fooditems),
                   has_nutrition=bool(nutrition_values))
        
        # Call nutritionist agent with fooditems and nutrition values
        nutritionist_response = await nutritionist_agent(
            food_analysis=fooditems_str,
            medical_report=medical_report,
            meal_type=request.meal_type,
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
        
        return NutritionAdviceResponse(
            user_email=current_user.email,
            meal_type=request.meal_type,
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
    summary="Calculate Nutrition from Food Items",
    description="""
    Calculate clinically accurate nutrition values for given food items.
    
    **Authentication Required:** Yes (JWT Bearer token)
    
    **Use Case:**
    This endpoint is designed for when users correct AI-identified foods from the `/upload-food` endpoint.
    Users can provide corrected food item names with quantities to get updated nutrition values.
    
    **Input Format:**
    - Provide food items with quantities (e.g., "1 grilled chicken with naan roti")
    - The agent will parse quantities and calculate nutrition accordingly
    - If no quantity is specified, standard serving sizes are used
    
    **Examples:**
    - "1 grilled chicken with naan roti"
    - "2 slices pizza with cheese and tomato"
    - "150g brown rice with vegetables"
    
    **Returns:**
    - fooditems (echoed back)
    - nutrition object with clinically accurate values
    
    **Note:** This endpoint tracks usage but does not count against daily limits.
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
    Calculate nutrition values for given food items.
    
    Accepts food item names with quantities and returns clinically accurate nutrition data.
    Updates previously saved nutrition data if it was saved from food upload (not from nutrition advice).
    """
    try:
        logger.info(f"Nutrition calculation request from user {current_user.id}", 
                   item_count=len(request.fooditems))
        
        # Call nutrition calculator agent
        nutrition_response = await nutrition_calculator_agent(request.fooditems)
        
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
        
        # Check if there's existing nutrition data from food upload (not nutrition advice)
        postgres_client = PostgresClient()
        existing_data = await postgres_client.get_nutrition_data(str(current_user.id))
        
        # Update database only if data exists and was saved from food upload
        # (i.e., doesn't have nutritionist_recommendations field)
        if existing_data:
            data_content = existing_data.get("data", {})
            # Check if this was from food upload (has food_analysis but no nutritionist_recommendations)
            if "food_analysis" in data_content and "nutritionist_recommendations" not in data_content:
                logger.info("Updating existing nutrition data from food upload", 
                           user_id=str(current_user.id))
                
                from datetime import datetime, timezone
                
                # Update the food_analysis with new nutrition values
                updated_data = {
                    "food_analysis": {
                        "fooditems": nutrition_data.get("fooditems", []),
                        "nutrition": nutrition_data.get("nutrition", {})
                    },
                    "meal_type": data_content.get("meal_type"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "updated_via_calculator": True
                }
                
                await postgres_client.save_nutrition_data(
                    user_id=str(current_user.id),
                    data=updated_data
                )
                logger.info("Nutrition data updated successfully", user_id=str(current_user.id))
            else:
                logger.info("Skipping database update - data is from nutrition advice", 
                           user_id=str(current_user.id))
        else:
            logger.info("No existing nutrition data to update", user_id=str(current_user.id))
        
        logger.info(f"Nutrition calculation completed for user {current_user.id}")
        
        return NutritionCalculationResponse(
            fooditems=nutrition_data.get("fooditems", []),
            nutrition=nutrition_data.get("nutrition", {})
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
    "/nutrition-data",
    summary="Get My Saved Nutrition Data",
    description="""
    Retrieve your previously saved nutrition analysis data.
    
    **Authentication Required:** Yes (JWT Bearer token)
    
    **Returns:**
    - Saved nutrition analysis data
    - Meal type
    - Nutritionist recommendations
    """,
    tags=["AI Agents"]
)
async def get_my_nutrition_data(
    current_user: User = Depends(get_current_active_user)
):
    """Get saved nutrition data for authenticated user"""
    logger.info("Nutrition data requested", user_id=str(current_user.id))
    postgres_client = PostgresClient()
    data = await postgres_client.get_nutrition_data(current_user.email)
    
    if not data:
        logger.warning("Nutrition data not found", user_id=str(current_user.id))
        raise HTTPException(status_code=404, detail="No nutrition data found or data expired")
    
    logger.info("Nutrition data retrieved successfully", user_id=str(current_user.id))
    return data


@router.get(
    "/report-data",
    summary="Get My Saved Report Data",
    description="""
    Retrieve your previously saved medical report analysis data.
    
    **Authentication Required:** Yes (JWT Bearer token)
    
    **Returns:**
    - Saved report analysis data
    - Individual file analyses
    - Combined summary
    """,
    tags=["AI Agents"]
)
async def get_my_report_data(
    current_user: User = Depends(get_current_active_user)
):
    """Get saved report data for authenticated user"""
    logger.info("Report data requested", user_id=str(current_user.id))
    postgres_client = PostgresClient()
    data = await postgres_client.get_report_data(current_user.email)
    
    if not data:
        logger.warning("Report data not found", user_id=str(current_user.id))
        raise HTTPException(status_code=404, detail="No report data found or data expired")
    
    logger.info("Report data retrieved successfully", user_id=str(current_user.id))
    return data


@router.delete(
    "/report-data",
    summary="Delete My Saved Report Data",
    description="""
    Delete your previously saved medical report analysis data.
    
    **Authentication Required:** Yes (JWT Bearer token)
    
    **Returns:**
    - Success message
    """,
    tags=["AI Agents"]
)
async def delete_my_report_data(
    current_user: User = Depends(get_current_active_user)
):
    """Delete saved report data for authenticated user"""
    logger.info("Report deletion requested", user_id=str(current_user.id))
    postgres_client = PostgresClient()
    success = await postgres_client.delete_report_data(current_user.email)
    
    if not success:
        logger.warning("Report data not found for deletion", user_id=str(current_user.id))
        raise HTTPException(status_code=404, detail="No report data found to delete")
    
    logger.info("Report data deleted successfully", user_id=str(current_user.id))
    return {"message": "Report data deleted successfully"}


# Legacy endpoints for backward compatibility (deprecated)
@router.get(
    "/get-nutrition/{user_id}",
    summary="[DEPRECATED] Get Saved Nutrition Data",
    description="""
    **DEPRECATED:** Use GET /api/v1/ai/nutrition-data instead (with JWT authentication).
    
    This endpoint is kept for backward compatibility only.
    """,
    deprecated=True,
    tags=["AI Agents"]
)
async def get_nutrition_data_legacy(user_id: str):
    """Get saved nutrition data for user (legacy)"""
    logger.info("Nutrition data requested (legacy)", user_id=user_id)
    postgres_client = PostgresClient()
    data = await postgres_client.get_nutrition_data(user_id)
    
    if not data:
        logger.warning("Nutrition data not found", user_id=user_id)
        raise HTTPException(status_code=404, detail="No nutrition data found or data expired")
    
    logger.info("Nutrition data retrieved successfully", user_id=user_id)
    return data


@router.get(
    "/get-report/{user_id}",
    summary="[DEPRECATED] Get Saved Report Data",
    description="""
    **DEPRECATED:** Use GET /api/v1/ai/report-data instead (with JWT authentication).
    
    This endpoint is kept for backward compatibility only.
    """,
    deprecated=True,
    tags=["AI Agents"]
)
async def get_report_data_legacy(user_id: str):
    """Get saved report data for user (legacy)"""
    logger.info("Report data requested (legacy)", user_id=user_id)
    postgres_client = PostgresClient()
    data = await postgres_client.get_report_data(user_id)
    
    if not data:
        logger.warning("Report data not found", user_id=user_id)
        raise HTTPException(status_code=404, detail="No report data found or data expired")
    
    logger.info("Report data retrieved successfully", user_id=user_id)
    return data


@router.delete(
    "/delete-report/{user_id}",
    summary="[DEPRECATED] Delete Saved Report Data",
    description="""
    **DEPRECATED:** Use DELETE /api/v1/ai/report-data instead (with JWT authentication).
    
    This endpoint is kept for backward compatibility only.
    """,
    deprecated=True,
    tags=["AI Agents"]
)
async def delete_report_data_legacy(user_id: str):
    """Delete saved report data for user (legacy)"""
    logger.info("Report deletion requested (legacy)", user_id=user_id)
    postgres_client = PostgresClient()
    success = await postgres_client.delete_report_data(user_id)
    
    if not success:
        logger.warning("Report data not found for deletion", user_id=user_id)
        raise HTTPException(status_code=404, detail="No report data found to delete")
    
    logger.info("Report data deleted successfully", user_id=user_id)
    return {"message": f"Report data deleted for user: {user_id}"}


@router.get(
    "/nutrition-data",
    summary="Get Nutrition Data with Pagination",
    description="""
    Retrieve nutrition analysis history with pagination and date filtering.
    
    **Authentication Required:** Yes (JWT Bearer token)
    
    **Query Parameters:**
    - `start_date`: Filter records from this date (ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)
    - `end_date`: Filter records until this date (ISO format)
    - `page`: Page number (default: 1)
    - `page_size`: Items per page (default: 10, max: 100)
    
    **Returns:**
    - Paginated list of nutrition analyses
    - Total count and page information
    - Records sorted by newest first
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
    start_date: Optional[str] = Query(None, description="Start date filter (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date filter (ISO format)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page (max 100)"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get paginated nutrition data for the authenticated user.
    
    Supports date filtering and pagination for efficient data retrieval.
    """
    try:
        from datetime import datetime
        
        # Validate and parse dates
        start_datetime = None
        end_datetime = None
        
        if start_date:
            try:
                start_datetime = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid start_date format. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)"
                )
        
        if end_date:
            try:
                end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid end_date format. Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)"
                )
        
        logger.info("Fetching paginated nutrition data", 
                   user_id=str(current_user.id),
                   start_date=start_date,
                   end_date=end_date,
                   page=page,
                   page_size=page_size)
        
        # Get paginated data
        postgres_client = PostgresClient()
        result = await postgres_client.get_nutrition_data_paginated(
            user_id=str(current_user.id),
            start_date=start_datetime,
            end_date=end_datetime,
            page=page,
            page_size=page_size
        )
        
        logger.info("Nutrition data retrieved successfully",
                   user_id=str(current_user.id),
                   total_count=result["total_count"],
                   items_returned=len(result["items"]))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to retrieve nutrition data",
                    user_id=str(current_user.id),
                    error=str(e),
                    exception_type=type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve nutrition data. Please try again later."
        )


@router.get(
    "/nutrition-data/today",
    summary="Get Today's Nutrition Data",
    description="""
    Retrieve all nutrition analyses from today for the authenticated user.
    
    **Authentication Required:** Yes (JWT Bearer token)
    
    **Returns:**
    - List of all nutrition analyses from today
    - Sorted by newest first
    - Automatically filters by current date (00:00 to 23:59)
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
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all nutrition data from today for the authenticated user.
    
    Automatically filters by today's date in the user's timezone.
    """
    try:
        from datetime import datetime, timezone, timedelta
        
        # Get today's date range (UTC)
        now_utc = datetime.now(timezone.utc)
        start_of_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now_utc.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        logger.info("Fetching today's nutrition data", 
                   user_id=str(current_user.id),
                   start_of_day=start_of_day.isoformat(),
                   end_of_day=end_of_day.isoformat())
        
        # Get all data from today (no pagination limit)
        postgres_client = PostgresClient()
        result = await postgres_client.get_nutrition_data_paginated(
            user_id=str(current_user.id),
            start_date=start_of_day,
            end_date=end_of_day,
            page=1,
            page_size=100  # Get up to 100 entries from today
        )
        
        logger.info("Today's nutrition data retrieved successfully",
                   user_id=str(current_user.id),
                   total_count=result["total_count"],
                   items_returned=len(result["items"]))
        
        # Return just the items array for simpler response
        return {
            "date": now_utc.date().isoformat(),
            "total_count": result["total_count"],
            "items": result["items"]
        }
        
    except Exception as e:
        logger.error("Failed to retrieve today's nutrition data",
                    user_id=str(current_user.id),
                    error=str(e),
                    exception_type=type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve today's nutrition data. Please try again later."
        )
