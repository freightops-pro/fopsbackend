import os
from typing import Dict, Any, Optional
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

async def extract_bol_data(file_content: bytes) -> Dict[str, Any]:
    """
    Extract text from BOL/POD using Google Vision API
    Returns structured data for load creation
    """
    try:
        # Import Google Cloud Vision
        from google.cloud import vision
        
        # Initialize the client
        credentials_path = os.getenv("GOOGLE_VISION_CREDENTIALS_PATH")
        if credentials_path and os.path.exists(credentials_path):
            client = vision.ImageAnnotatorClient.from_service_account_file(credentials_path)
        else:
            # Use default credentials (for cloud deployment)
            client = vision.ImageAnnotatorClient()
        
        # Create image object
        image = vision.Image(content=file_content)
        
        # Perform text detection
        response = client.text_detection(image=image)
        
        if response.error.message:
            raise HTTPException(status_code=500, detail=f"Vision API error: {response.error.message}")
        
        # Extract text
        texts = response.text_annotations
        if not texts:
            raise HTTPException(status_code=400, detail="No text found in image")
        
        # Get full text
        full_text = texts[0].description
        
        # Parse structured data from text
        parsed_data = parse_bol_text(full_text)
        
        return {
            "success": True,
            "raw_text": full_text,
            "parsed_data": parsed_data
        }
        
    except ImportError:
        logger.warning("Google Cloud Vision not installed, using fallback parsing")
        # Fallback: basic text parsing without OCR
        return {
            "success": False,
            "error": "OCR service not configured. Please install google-cloud-vision package.",
            "raw_text": "",
            "parsed_data": {}
        }
    except Exception as e:
        logger.error(f"OCR processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")

def parse_bol_text(text: str) -> Dict[str, Any]:
    """
    Parse BOL text to extract structured data
    This is a simplified parser - can be enhanced with more sophisticated NLP
    """
    lines = text.split('\n')
    parsed = {
        "customer_name": "",
        "pickup_location": "",
        "delivery_location": "",
        "commodity": "",
        "weight": "",
        "pieces": "",
        "reference_number": "",
        "special_instructions": ""
    }
    
    # Keywords to look for
    pickup_keywords = ["pickup", "origin", "shipper", "from"]
    delivery_keywords = ["delivery", "destination", "consignee", "to"]
    commodity_keywords = ["commodity", "freight", "product", "description"]
    weight_keywords = ["weight", "lbs", "pounds", "kg"]
    pieces_keywords = ["pieces", "pcs", "quantity", "qty"]
    
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        
        # Look for pickup location
        if any(keyword in line_lower for keyword in pickup_keywords):
            if i + 1 < len(lines):
                parsed["pickup_location"] = lines[i + 1].strip()
        
        # Look for delivery location
        if any(keyword in line_lower for keyword in delivery_keywords):
            if i + 1 < len(lines):
                parsed["delivery_location"] = lines[i + 1].strip()
        
        # Look for commodity
        if any(keyword in line_lower for keyword in commodity_keywords):
            if i + 1 < len(lines):
                parsed["commodity"] = lines[i + 1].strip()
        
        # Look for weight
        if any(keyword in line_lower for keyword in weight_keywords):
            # Extract numbers from the line
            import re
            numbers = re.findall(r'\d+(?:\.\d+)?', line)
            if numbers:
                parsed["weight"] = numbers[0]
        
        # Look for pieces
        if any(keyword in line_lower for keyword in pieces_keywords):
            import re
            numbers = re.findall(r'\d+', line)
            if numbers:
                parsed["pieces"] = numbers[0]
        
        # Look for reference/BOL number
        if "bol" in line_lower or "bill" in line_lower or "reference" in line_lower:
            parsed["reference_number"] = line.strip()
    
    # Clean up empty values
    parsed = {k: v for k, v in parsed.items() if v}
    
    return parsed

async def validate_image_file(file_content: bytes) -> bool:
    """
    Validate that the uploaded file is a valid image
    """
    try:
        # Check file size (max 10MB)
        if len(file_content) > 10 * 1024 * 1024:
            return False
        
        # Check if it's a valid image format
        import imghdr
        image_type = imghdr.what(None, file_content)
        valid_types = ['jpeg', 'jpg', 'png', 'tiff', 'bmp']
        
        return image_type in valid_types
        
    except Exception:
        return False