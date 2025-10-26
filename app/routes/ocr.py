from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.config.db import get_db
from app.routes.user import verify_token
from app.services.ocr_service import extract_bol_data
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/loads/ocr", tags=["OCR Processing"])

@router.post("/extract-from-rate-confirmation")
async def extract_from_rate_confirmation(
    rateConfirmation: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token)
):
    """
    Extract load data from uploaded rate confirmation using OCR
    """
    try:
        # Validate file type
        allowed_types = ['image/', 'application/pdf']
        if not rateConfirmation.content_type or not any(rateConfirmation.content_type.startswith(t) for t in allowed_types):
            raise HTTPException(
                status_code=400, 
                detail="Invalid file type. Please upload an image file (PNG, JPG) or PDF."
            )
        
        # Read file content
        file_content = await rateConfirmation.read()
        
        logger.info(f"Processing rate confirmation: {rateConfirmation.filename}")
        
        # Use real OCR service to extract data
        extracted_data = await extract_bol_data(file_content)
        
        return {
            "success": True,
            "message": "Rate confirmation processed successfully using OCR",
            "loadData": extracted_data,
            "confidence": extracted_data.get("confidence_score", 0.8),
            "extractedFields": [k for k, v in extracted_data.items() if v and k not in ["source", "extraction_date", "original_filename", "confidence_score"]]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR processing error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "detail": f"OCR processing failed: {str(e)}"}
        )

@router.post("/extract-from-bol")
async def extract_from_bol(
    bol: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token)
):
    """
    Extract load data from uploaded Bill of Lading using OCR
    """
    try:
        # Validate file type
        allowed_types = ['image/', 'application/pdf']
        if not bol.content_type or not any(bol.content_type.startswith(t) for t in allowed_types):
            raise HTTPException(
                status_code=400, 
                detail="Invalid file type. Please upload an image file (PNG, JPG) or PDF."
            )
        
        # Read file content
        file_content = await bol.read()
        
        logger.info(f"Processing BOL: {bol.filename}")
        
        # Use real OCR service to extract data
        extracted_data = await extract_bol_data(file_content)
        
        return {
            "success": True,
            "message": "Bill of Lading processed successfully using OCR",
            "loadData": extracted_data,
            "confidence": extracted_data.get("confidence_score", 0.8),
            "extractedFields": [k for k, v in extracted_data.items() if v and k not in ["source", "extraction_date", "original_filename", "confidence_score"]]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"BOL OCR processing error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "detail": f"BOL OCR processing failed: {str(e)}"}
        )
