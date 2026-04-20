import base64
import io
from typing import Dict, List
from fastapi import UploadFile, HTTPException
from PIL import Image

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
MAX_DIMENSION = 1920  # Max dimension (width or height) while maintaining quality


def encode_image_to_base64(image_file: UploadFile) -> Dict[str, str]:
    """Convert uploaded image to base64 string
    
    If image is larger than 5MB, it will be compressed while maintaining quality
    """
    try:
        # Read the image file
        image_bytes = image_file.file.read()
        file_size = len(image_bytes)
        
        # Validate it's an image
        img = Image.open(io.BytesIO(image_bytes))
        
        # Compress if file size > 5MB
        if file_size > MAX_FILE_SIZE_BYTES:
            # Resize while maintaining aspect ratio
            img = _compress_image(img)
            
            # Re-encode to bytes with high quality
            img_byte_arr = io.BytesIO()
            save_format = img.format.upper() if img.format and img.format.lower() in ['jpeg', 'jpg', 'png', 'webp'] else 'JPEG'
            img.save(img_byte_arr, format=save_format, quality=90, optimize=True)
            img_byte_arr.seek(0)
            image_bytes = img_byte_arr.getvalue()
        
        # Convert to base64
        base64_string = base64.b64encode(image_bytes).decode('utf-8')
        
        # Get the image format
        format_lower = img.format.lower() if img.format else 'jpeg'
        mime_type = f"image/{format_lower}"
        
        return {
            "mime_type": mime_type,
            "base64_string": base64_string,
            "original_size": file_size,
            "compressed_size": len(image_bytes) if file_size > MAX_FILE_SIZE_BYTES else None
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {str(e)}")


def _compress_image(img: Image.Image) -> Image.Image:
    """Compress image by resizing while maintaining quality
    
    Uses Lanczos resampling for high-quality downscaling
    Maintains aspect ratio
    """
    # Get current dimensions
    width, height = img.size
    
    # Check if resizing is needed
    if width <= MAX_DIMENSION and height <= MAX_DIMENSION:
        return img
    
    # Calculate new dimensions maintaining aspect ratio
    if width > height:
        new_width = MAX_DIMENSION
        new_height = int((height / width) * MAX_DIMENSION)
    else:
        new_height = MAX_DIMENSION
        new_width = int((width / height) * MAX_DIMENSION)
    
    # Resize with high-quality resampling (Lanczos)
    resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    return resized_img


def encode_pdf_to_base64(pdf_file: UploadFile) -> Dict[str, str]:
    """Convert uploaded PDF to base64-encoded image (first page only)"""
    try:
        from pdf2image import convert_from_bytes
        from pdf2image.exceptions import PDFInfoNotInstalledError
        
        # Read the PDF file
        pdf_bytes = pdf_file.file.read()
        
        # Convert PDF to images (first page only for now)
        images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1, fmt='jpeg')
        
        if not images:
            raise HTTPException(status_code=400, detail="Could not convert PDF to image")
        
        # Get the first page as image
        first_page = images[0]
        
        # Convert PIL Image to bytes
        img_byte_arr = io.BytesIO()
        first_page.save(img_byte_arr, format='JPEG', quality=95)
        img_byte_arr.seek(0)
        
        # Convert to base64
        base64_string = base64.b64encode(img_byte_arr.read()).decode('utf-8')
        
        return {
            "mime_type": "image/jpeg",
            "base64_string": base64_string
        }
    
    except PDFInfoNotInstalledError:
        raise HTTPException(
            status_code=500, 
            detail="PDF conversion service unavailable. Poppler is not installed on the server."
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid PDF file or conversion failed: {str(e)}")