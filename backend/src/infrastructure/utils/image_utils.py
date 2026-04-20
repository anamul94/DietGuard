import base64
import io
from typing import Dict, Tuple
from fastapi import UploadFile, HTTPException
from PIL import Image

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
MAX_DIMENSION = 2048  # Max dimension while preserving food detail


def encode_image_to_base64(image_file: UploadFile) -> Dict[str, str]:
    """Convert uploaded image to base64 string.

    Images over 5MB are compressed while preserving visual fidelity.
    """
    try:
        image_bytes = image_file.file.read()
        file_size = len(image_bytes)

        img = Image.open(io.BytesIO(image_bytes))
        original_format = img.format  # PIL loses .format after any transform

        if file_size > MAX_FILE_SIZE_BYTES:
            image_bytes, save_fmt = _compress_to_target(img, original_format, MAX_FILE_SIZE_BYTES)
            # Update mime type to reflect actual saved format
            original_format = save_fmt

        base64_string = base64.b64encode(image_bytes).decode('utf-8')

        format_lower = (original_format or 'jpeg').lower()
        if format_lower == 'jpg':
            format_lower = 'jpeg'
        mime_type = f"image/{format_lower}"

        return {
            "mime_type": mime_type,
            "base64_string": base64_string,
            "original_size": file_size,
            "compressed_size": len(image_bytes) if file_size > MAX_FILE_SIZE_BYTES else None,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {str(e)}")



def _resize_to_max_dimension(img: Image.Image, max_dim: int) -> Image.Image:
    w, h = img.size
    if w <= max_dim and h <= max_dim:
        return img
    scale = max_dim / max(w, h)
    return img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)


def _compress_to_target(img: Image.Image, original_format: str | None, target_bytes: int) -> Tuple[bytes, str]:
    """Compress to WebP, iterating quality then dimensions until under target_bytes.

    WebP handles alpha natively (no colour artifacts), gives better quality
    at smaller sizes than JPEG, and works for all input formats.
    """
    # WebP supports alpha natively — no need to flatten
    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGBA' if 'A' in img.getbands() else 'RGB')

    dim_scales = [1.0, 0.85, 0.70, 0.55, 0.40]
    quality_steps = [95, 90, 85, 80, 75, 65]

    orig_w, orig_h = img.size

    for scale in dim_scales:
        if scale < 1.0:
            target_w = int(orig_w * scale)
            target_h = int(orig_h * scale)
            max_at_scale = min(MAX_DIMENSION, max(target_w, target_h))
            scaled_img = _resize_to_max_dimension(
                img.resize((target_w, target_h), Image.Resampling.LANCZOS), max_at_scale
            )
        else:
            scaled_img = _resize_to_max_dimension(img, MAX_DIMENSION)

        for quality in quality_steps:
            buf = io.BytesIO()
            scaled_img.save(buf, format='WEBP', quality=quality, method=6)
            result = buf.getvalue()
            if len(result) <= target_bytes:
                return result, 'WEBP'

    # Return last attempt even if slightly over (extremely rare edge case)
    return result, 'WEBP'


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