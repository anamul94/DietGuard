from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import asyncio
import socketio
from ...infrastructure.utils.image_utils import encode_image_to_base64, encode_pdf_to_base64
from ...infrastructure.agents.report_agent import report_agent
from ...infrastructure.agents.food_agent import food_agent
from ...infrastructure.agents.nutritionist_agent import nutritionist_agent
from ...infrastructure.utils.redis_utils import RedisClient
from ...infrastructure.messaging.rabbitmq_client import rabbitmq_client
from ...infrastructure.websocket.socket_manager import socket_manager

app = FastAPI()

# Import Socket.IO server
from ...infrastructure.websocket.socket_manager import sio
socket_app = socketio.ASGIApp(sio, app)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3003", 
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3003",
        "http://15.207.68.194:3003",
        "*"  # Allow all origins for development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def read_root():
    return {"message": "Hello from prodmeasure!"}


@app.get("/get_report/{user_id}")
async def get_report(user_id: str):
    """Get saved report data for user"""
    redis_client = RedisClient()
    data = redis_client.get_report_data(user_id)
    
    if not data:
        raise HTTPException(status_code=404, detail="No report data found or data expired")
    
    return data





@app.post("/upload_food/")
async def upload_food(
    mobile_or_email: str = Form(..., description="User's mobile/email"),
    meal_time: str = Form(..., description="Meal time: breakfast, lunch, dinner, snack"),
    files: List[UploadFile] = File(..., description="Food images"),
):
    allowed_extensions = {".jpg", ".jpeg", ".png"}
    allowed_meal_times = {"breakfast", "lunch", "dinner", "snack"}
    
    if meal_time.lower() not in allowed_meal_times:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid meal time. Allowed: {', '.join(allowed_meal_times)}"
        )
    
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
        
        food_analysis = await food_agent(data_list, type_list, mime_list)

        # Get medical report data
        redis_client = RedisClient()
        medical_data = redis_client.get_report_data(mobile_or_email)
        medical_report = medical_data.get('data', {}).get('combined_response', 'No medical report available') if medical_data else 'No medical report available'

        # Get nutritionist recommendations
        nutritionist_advice = await nutritionist_agent(food_analysis, medical_report, meal_time)

        result_data = {
            "user_email": mobile_or_email,
            "meal_time": meal_time,
            "files_processed": len(files),
            "filenames": filenames,
            "food_analysis": food_analysis,
            "nutritionist_recommendations": nutritionist_advice,
        }

        # Save to Redis with nutrition data type
        redis_client.save_nutrition_data(mobile_or_email, result_data)

        # Publish event to RabbitMQ and emit via WebSocket (non-blocking)
        event_data = {
            "user_email": mobile_or_email,
            "meal_time": meal_time,
            "food_analysis": food_analysis,
            "nutritionist_recommendations": nutritionist_advice
        }
        # asyncio.create_task(rabbitmq_client.publish_food_event(event_data))
        asyncio.create_task(socket_manager.emit_food_event(event_data))

        return result_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing food images: {str(e)}")


@app.delete("/delete_report/{user_id}")
async def delete_report(user_id: str):
    """Delete saved report data for user"""
    redis_client = RedisClient()
    success = redis_client.delete_report_data(user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="No report data found to delete")
    
    return {"message": f"Report data deleted for user: {user_id}"}


@app.get("/debug/redis/{user_id}")
async def debug_redis(user_id: str):
    """Debug Redis connection and data"""
    redis_client = RedisClient()
    try:
        # Test connection
        redis_client.redis_client.ping()
        
        # Check if key exists
        key = f"dietguard:report:{user_id}"
        exists = redis_client.redis_client.exists(key)
        ttl = redis_client.redis_client.ttl(key)
        
        return {
            "redis_connected": True,
            "key": key,
            "key_exists": bool(exists),
            "ttl_seconds": ttl,
            "raw_data": redis_client.redis_client.get(key) if exists else None
        }
    except Exception as e:
        return {
            "redis_connected": False,
            "error": str(e)
        }


@app.post("/upload_report/")
async def upload_report(
    mobile_or_email: str = Form(..., description="User's mobile/email"),
    files: List[UploadFile] = File(..., description="Image or PDF files"),
):
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
            "mobile_number": mobile_or_email,
            "files_processed": len(files),
            "individual_responses": responses,
            "combined_response": combined_response
        }

        # Save to Redis with 12 hours expiration
        redis_client = RedisClient()
        redis_client.save_report_data(mobile_or_email, result_data)

        return result_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing files: {str(e)}")


@app.get("/get_nutrition/{user_id}")
async def get_nutrition(user_id: str):
    """Get saved nutrition data for user"""
    redis_client = RedisClient()
    data = redis_client.get_nutrition_data(user_id)

    if not data:
        raise HTTPException(
            status_code=404, detail="No nutrition data found or data expired"
        )

    return data
