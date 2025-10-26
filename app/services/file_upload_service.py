import os
import uuid
from datetime import datetime
from typing import Dict, Any
import aiofiles
from fastapi import UploadFile, HTTPException, status
from pathlib import Path

# Configuration
UPLOAD_DIR = "uploads"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".gif"}

def ensure_upload_directory(subdir: str = ""):
    """Ensure the upload directory exists"""
    upload_path = Path(UPLOAD_DIR) / subdir if subdir else Path(UPLOAD_DIR)
    upload_path.mkdir(parents=True, exist_ok=True)

def validate_file(file: UploadFile) -> None:
    """Validate uploaded file"""
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    if file.filename:
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            )

def generate_filename(load_id: str, file_type: str, original_filename: str) -> str:
    """Generate unique filename for upload"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_ext = Path(original_filename).suffix.lower()
    unique_id = str(uuid.uuid4())[:8]
    
    return f"{file_type}_{load_id}_{timestamp}_{unique_id}{file_ext}"

async def save_uploaded_file(file: UploadFile, filename: str, subdir: str = "") -> str:
    """Save uploaded file to disk"""
    ensure_upload_directory(subdir)
    file_path = Path(UPLOAD_DIR) / subdir / filename if subdir else Path(UPLOAD_DIR) / filename
    
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    return str(file_path)

def get_file_url(filename: str, subdir: str = "") -> str:
    """Generate URL for accessing the uploaded file"""
    if subdir:
        return f"/uploads/{subdir}/{filename}"
    return f"/uploads/{filename}"

async def upload_bill_of_lading(load_id: str, file: UploadFile) -> Dict[str, Any]:
    """Upload bill of lading file"""
    try:
        validate_file(file)
        filename = generate_filename(load_id, "bol", file.filename)
        file_path = await save_uploaded_file(file, filename, "bol")
        file_url = get_file_url(filename, "bol")
        
        return {
            "success": True,
            "message": "Bill of lading uploaded successfully",
            "filename": filename,
            "file_url": file_url,
            "file_size": file.size,
            "content_type": file.content_type
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )
