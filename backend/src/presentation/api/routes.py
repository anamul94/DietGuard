from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from ..schemas import FoodUploadResponse, NutritionAdviceRequest, NutritionAdviceResponse
import asyncio
import socketio
from ...infrastructure.utils.logger import logger
from ...infrastructure.utils.image_utils import encode_image_to_base64, encode_pdf_to_base64
from ...infrastructure.agents.report_agent import report_agent
from ...infrastructure.agents.food_agent import food_agent
from ...infrastructure.agents.nutritionist_agent import nutritionist_agent
from ...infrastructure.agents.summary_agent import summary_agent
from ...infrastructure.database.postgres_client import PostgresClient
from ...infrastructure.database.database import get_db
from ...infrastructure.database.auth_models import User
from ...infrastructure.auth.dependencies import get_current_active_user
from ...application.services.subscription_service import SubscriptionService
from sqlalchemy.ext.asyncio import AsyncSession
# from ...infrastructure.messaging.rabbitmq_client import rabbitmq_client

import json

# Import routers
from .auth_routes import router as auth_router
from .user_routes import router as user_router
from .payment_routes import router as payment_router
from .admin_routes import router as admin_router

# Create FastAPI app first
app = FastAPI(
    title="DietGuard API",
    description="AI-Powered Nutritionist with Authentication",
    version="1.0.0"
)

# Include routers
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(payment_router)
app.include_router(admin_router)

@app.on_event("startup")
async def startup_event():
    """Create database tables on startup if they don't exist"""
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from ...infrastructure.database.database import DATABASE_URL, Base
        
        logger.info("Starting database initialization")
        engine = create_async_engine(DATABASE_URL)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()
        logger.info("Database tables created/verified successfully")
    except Exception as e:
        logger.error("Database table creation failed", error=str(e), exception_type=type(e).__name__)
        # Don't fail startup - app can still run without DB for some endpoints

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add request/response logging middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import time

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request
        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown"
        )
        
        # Process request
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            # Log response
            logger.info(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2)
            )
            
            return response
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "Request failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
                exception_type=type(e).__name__,
                duration_ms=round(duration * 1000, 2)
            )
            raise

app.add_middleware(RequestLoggingMiddleware)

# Create Socket.IO server
sio = socketio.AsyncServer(
    cors_allowed_origins="*",
    async_mode='asgi'
)

@app.get("/")
async def read_root():
    return {"message": "Hello from prodmeasure!"}

@app.get("/health")
async def health_check():
    logger.info("Health check requested")
    
    health_status = {
        "status": "healthy",
        "service": "dietguard-backend",
        "version": "1.0.0",
        "checks": {
            "database": "unknown"
        }
    }
    
    # Check database connectivity
    try:
        # postgres_client = PostgresClient()
        # await postgres_client.health_check()
        health_status["checks"]["database"] = "healthy no db"
        logger.info("Database health check passed")
        return health_status
    except Exception as e:
        health_status["checks"]["database"] = "unhealthy"
        health_status["status"] = "unhealthy"
        logger.error("Database health check failed", error=str(e))
        # Return 500 status code for Route53 health check failover
        raise HTTPException(status_code=500, detail=health_status)


@app.get("/get_report/{user_id}")
async def get_report(user_id: str):
    """Get saved report data for user"""
    logger.info("Report data requested", user_id=user_id)
    postgres_client = PostgresClient()
    data = await postgres_client.get_report_data(user_id)
    
    if not data:
        logger.warning("Report data not found", user_id=user_id)
        raise HTTPException(status_code=404, detail="No report data found or data expired")
    
    logger.info("Report data retrieved successfully", user_id=user_id)
    return data

# Create Socket.IO ASGI app
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)



@app.post("/upload_food/", response_model=FoodUploadResponse)
async def upload_food(
    files: List[UploadFile] = File(..., description="Food images"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload food images and get AI-powered food analysis.
    
    Returns detailed nutritional breakdown and food identification.
    Does not include nutritionist recommendations - use /get_nutritionist_advice/ for that.
    
    **Limits:** Free users can upload 2 times per day. Paid users have unlimited uploads.
    """
    logger.info("Food upload started", user_id=str(current_user.id), file_count=len(files))
    
    # Check upload limits
    try:
        limit_check = await SubscriptionService.check_upload_limit(db, current_user)
        logger.info("Upload limit check passed", user_id=str(current_user.id), remaining=limit_check.get("remaining_uploads"))
    except ValueError as e:
        logger.warning("Upload limit exceeded", user_id=str(current_user.id), error=str(e))
        raise HTTPException(status_code=429, detail=str(e))
    
    allowed_extensions = {".jpg", ".jpeg", ".png"}
    
    try:
        # Validate and encode all files
        encoded_images = []
        filenames = []
        
        for file in files:
            file_extension = file.filename.split(".")[-1].lower()
            if f".{file_extension}" not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
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
        
        food_analysis = food_analysis_response.data
        
        # Increment upload count
        await SubscriptionService.increment_upload_count(db, current_user)

        result_data = {
            "user_email": current_user.email,
            "files_processed": len(files),
            "filenames": filenames,
            "food_analysis": food_analysis,
        }

        logger.info("Food upload completed successfully", user_id=str(current_user.id), files_processed=len(files))
        return result_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Food upload failed", user_id=str(current_user.id), error=str(e))
        raise HTTPException(status_code=500, detail=f"Error processing food images: {str(e)}")


@app.post("/get_nutritionist_advice/", response_model=NutritionAdviceResponse)
async def get_nutritionist_advice(
    request: NutritionAdviceRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get personalized nutritionist recommendations.
    
    Analyzes food based on your age, gender, and optional medical conditions.
    Saves recommendations to your profile for tracking.
    
    **Limits:** Free users can get 2 nutrition analyses per day. Paid users have unlimited analyses.
    """
    meal_time = request.meal_time
    logger.info("Nutrition analysis started", user_id=str(current_user.id), meal_time=meal_time)
    
    # Check nutrition analysis limits
    try:
        limit_check = await SubscriptionService.check_nutrition_limit(db, current_user)
        logger.info("Nutrition limit check passed", user_id=str(current_user.id), remaining=limit_check.get("remaining_analyses"))
    except ValueError as e:
        logger.warning("Nutrition analysis limit exceeded", user_id=str(current_user.id), error=str(e))
        raise HTTPException(status_code=429, detail=str(e))
    
    allowed_meal_times = {"breakfast", "lunch", "dinner", "snack"}
    
    if meal_time.lower() not in allowed_meal_times:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid meal time. Allowed: {', '.join(allowed_meal_times)}"
        )
    
    try:
        # Use provided medical report or default message
        medical_report_text = request.medical_report if request.medical_report else 'No medical report available'
        
        # Get nutritionist recommendations
        nutritionist_advice = await nutritionist_agent(request.food_analysis, medical_report_text, request.meal_time)
        
        # Prepare data to save (only nutritionist recommendations + meal_time)
        save_data = {
            "user_email": current_user.email,
            "meal_time": request.meal_time,
            "age": request.age,
            "gender": request.gender,
            "nutritionist_recommendations": nutritionist_advice,
        }
        
        # Save to PostgreSQL
        postgres_client = PostgresClient()
        await postgres_client.save_nutrition_data(current_user.email, save_data)
        
        # Increment nutrition analysis count
        await SubscriptionService.increment_nutrition_count(db, current_user)
        
        # Get formatted summary for speech
        formated_summary_for_speech = await summary_agent(nutritionist_advice)
        logger.debug("Summary generated for speech", summary_length=len(formated_summary_for_speech))
        
        # Emit via WebSocket (non-blocking) - send only summary text
        asyncio.create_task(sio.emit('food_analysis_complete', formated_summary_for_speech))
        
        result_data = {
            "user_email": current_user.email,
            "meal_time": request.meal_time,
            "nutritionist_recommendations": nutritionist_advice,
        }
        
        logger.info("Nutrition analysis completed successfully", user_id=str(current_user.id), meal_time=meal_time)
        return result_data
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Nutrition analysis failed", user_id=str(current_user.id), meal_time=meal_time, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error processing nutrition analysis: {str(e)}")


@app.delete("/delete_report/{user_id}")
async def delete_report(user_id: str):
    """Delete saved report data for user"""
    logger.info("Report deletion requested", user_id=user_id)
    postgres_client = PostgresClient()
    success = await postgres_client.delete_report_data(user_id)
    
    if not success:
        logger.warning("Report data not found for deletion", user_id=user_id)
        raise HTTPException(status_code=404, detail="No report data found to delete")
    
    logger.info("Report data deleted successfully", user_id=user_id)
    return {"message": f"Report data deleted for user: {user_id}"}


@app.get("/debug/redis/{user_id}")
async def debug_redis(user_id: str):
    """Debug Redis connection and data"""
    postgres_client = PostgresClient()
    try:
        # Test connection by getting data
        data = await postgres_client.get_report_data(user_id)
        
        return {
            "postgres_connected": True,
            "user_id": user_id,
            "data_exists": data is not None,
            "raw_data": data
        }
    except Exception as e:
        return {
            "postgres_connected": False,
            "error": str(e)
        }


@app.post("/upload_report/")
async def upload_report(
    files: List[UploadFile] = File(..., description="Image or PDF files"),
    current_user: User = Depends(get_current_active_user)
):
    logger.info("Report upload started", user_id=str(current_user.id), file_count=len(files))
    # Validate mobile number
    # if not mobile_number.strip() or len(mobile_number) < 10:
    #     raise HTTPException(status_code=400, detail="Valid mobile number is required")

    allowed_extensions = {".jpg", ".jpeg", ".png", ".pdf"}
    responses = []

    async def process_file(file):
        # Validate file type
        file_extension = file.filename.split(".")[-1].lower()
        if f".{file_extension}" not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {file.filename}. Only PDF and image files allowed",
            )

        # Process based on file type
        if file_extension == "pdf":
            encoded_data = encode_pdf_to_base64(file)
            agent_response = await report_agent(
                encoded_data["base64_string"], "file", encoded_data["mime_type"]
            )
        else:  # image files
            encoded_data = encode_image_to_base64(file)
            agent_response = await report_agent(
                encoded_data["base64_string"], "image", encoded_data["mime_type"]
            )

        return {
            "filename": file.filename,
            "response": agent_response
        }

    try:
        # Process all files in parallel
        responses = await asyncio.gather(*[process_file(file) for file in files])

        # Concatenate all responses
        combined_response = "\n\n".join([f"File: {r['filename']}\n{r['response']}" for r in responses])

        result_data = {
            "mobile_number": current_user.email,
            "files_processed": len(files),
            "individual_responses": responses,
            "combined_response": combined_response
        }

        # Save to PostgreSQL with 12 hours expiration
        postgres_client = PostgresClient()
        await postgres_client.save_report_data(current_user.email, result_data, expiration_hours=12)
        
        logger.info("Report upload completed successfully", user_id=str(current_user.id), files_processed=len(files))
        return result_data

    except Exception as e:
        logger.error("Report upload failed", user_id=str(current_user.id), error=str(e))
        raise HTTPException(status_code=500, detail=f"Error processing files: {str(e)}")


@app.get("/get_nutrition/{user_id}")
async def get_nutrition(user_id: str):
    """Get saved nutrition data for user"""
    postgres_client = PostgresClient()
    data = await postgres_client.get_nutrition_data(user_id)

    if not data:
        raise HTTPException(
            status_code=404, detail="No nutrition data found or data expired"
        )

    return data

@app.get("/test_llm")
async def test_llm_connection():
    """Test LLM connection with simple query"""
    try:
        from ...infrastructure.agents.test_agent import test_agent
        
        response = await test_agent()
        
        return {
            "status": "success",
            "llm_connected": True,
            "test_query": "How are you?",
            "llm_response": response
        }
    except Exception as e:
        return {
            "status": "error",
            "llm_connected": False,
            "error": str(e)
        }
