from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from typing import List
import asyncio
from ...infrastructure.utils.image_utils import encode_image_to_base64, encode_pdf_to_base64
from ...infrastructure.agents.report_agent import report_agent
from ...infrastructure.utils.redis_utils import RedisClient

app = FastAPI()


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


@app.get("/get_report/{user_id}")
async def get_report(user_id: str):
    """Get saved report data for user"""
    redis_client = RedisClient()
    data = redis_client.get_report_data(user_id)

    if not data:
        raise HTTPException(
            status_code=404, detail="No report data found or data expired"
        )

    return data
