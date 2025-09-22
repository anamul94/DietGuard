import base64
import io
from typing import Dict, List
from fastapi import UploadFile, HTTPException
from PIL import Image


def encode_image_to_base64(image_file: UploadFile) -> Dict[str, str]:
    """Convert uploaded image to base64 string"""
    try:
        # Read the image file
        image_bytes = image_file.file.read()
        
        # Validate it's an image
        img = Image.open(io.BytesIO(image_bytes))
        
        # Convert to base64
        base64_string = base64.b64encode(image_bytes).decode('utf-8')
        
        # Get the image format
        format_lower = img.format.lower() if img.format else 'jpeg'
        mime_type = f"image/{format_lower}"
        
        return {
            "mime_type": mime_type,
            "base64_string": base64_string
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {str(e)}")


def encode_pdf_to_base64(pdf_file: UploadFile) -> Dict[str, str]:
    """Convert uploaded PDF to base64 string"""
    try:
        # Read the PDF file
        pdf_bytes = pdf_file.file.read()
        
        # Convert to base64
        base64_string = base64.b64encode(pdf_bytes).decode('utf-8')
        
        return {
            "mime_type": "application/pdf",
            "base64_string": base64_string
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid PDF file: {str(e)}")