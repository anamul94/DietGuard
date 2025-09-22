from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from typing import List
from ...infrastructure.utils.image_utils import encode_image_to_base64, encode_pdf_to_base64
from ...infrastructure.agents.report_agent import report_agent

app = FastAPI()



@app.get("/")
async def read_root():
    return {"message": "Hello from prodmeasure!"}


@app.post("/upload_report/")
async def upload_report(
    mobile_number: str = Form(..., description="User's mobile number"),
    files: List[UploadFile] = File(..., description="Image or PDF files"),
):
    # Validate mobile number
    # if not mobile_number.strip() or len(mobile_number) < 10:
    #     raise HTTPException(status_code=400, detail="Valid mobile number is required")

    allowed_extensions = {".jpg", ".jpeg", ".png", ".pdf"}
    responses = []

    try:
        for file in files:
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

            responses.append({
                "filename": file.filename,
                "response": agent_response
            })

        # Concatenate all responses
        combined_response = "\n\n".join([f"File: {r['filename']}\n{r['response']}" for r in responses])

        return {
            "mobile_number": mobile_number,
            "files_processed": len(files),
            "individual_responses": responses,
            "combined_response": combined_response
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing files: {str(e)}")
