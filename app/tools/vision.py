"""
Vision Tool - Llama 4 Scout Native Vision Processing

MDD Spec: "Accepts a PDF/Image URL. Passes it natively to Llama 4 Scout (no OCR library).
           Prompt: 'Extract Origin, Dest, Rate, and Pickup Date as JSON.'"

Uses Llama 4 Scout's native vision capabilities to extract data from:
- Rate confirmation PDFs
- BOL (Bill of Lading) documents
- Delivery receipts
- Other freight documentation

NO OCR LIBRARIES - relies entirely on Llama 4 Scout's multimodal capabilities.
"""

from typing import Dict, Any
import httpx
import base64
import json
from app.core.llm_router import LLMRouter


class VisionTool:
    """
    Extract structured data from freight documents using Llama 4 Scout vision.

    Strict Rule from MDD: Do not use OCR libraries (Tesseract). Rely entirely on Llama 4 Native Vision.
    """

    def __init__(self):
        self.llm_router = LLMRouter()

    async def extract_rate_confirmation(self, document_url: str) -> Dict[str, Any]:
        """
        Extract rate confirmation details from PDF/image.

        MDD Spec: "Extract Origin, Dest, Rate, and Pickup Date as JSON."

        Args:
            document_url: URL to PDF or image file

        Returns:
            {
                "origin_city": str,
                "origin_state": str,
                "dest_city": str,
                "dest_state": str,
                "rate": float,
                "pickup_date": str (YYYY-MM-DD),
                "delivery_date": str (YYYY-MM-DD) | None,
                "reference_number": str | None,
                "carrier_name": str | None,
                "confidence": float (0-1)
            }
        """
        # Download document
        document_base64 = await self._download_and_encode(document_url)

        # Construct vision prompt
        system_prompt = """You are Annie, an AI Dispatcher for FreightOps TMS.
Your job is to extract structured data from freight rate confirmation documents.

Extract the following fields:
- Origin city and state
- Destination city and state
- Rate (dollar amount)
- Pickup date
- Delivery date (if present)
- Reference/load number (if present)
- Carrier name (if present)

Return ONLY valid JSON in this exact format:
{
    "origin_city": "Chicago",
    "origin_state": "IL",
    "dest_city": "Los Angeles",
    "dest_state": "CA",
    "rate": 2500.00,
    "pickup_date": "2025-12-20",
    "delivery_date": "2025-12-22",
    "reference_number": "LOAD-12345",
    "carrier_name": "ABC Trucking",
    "confidence": 0.95
}

If any field is not found, use null. Set confidence to your certainty level (0-1).
"""

        user_prompt = "Extract the rate confirmation details from this document:"

        # Call Llama 4 Scout with vision
        response_text, metadata = await self.llm_router.generate(
            agent_role="annie",
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.1,  # Low temperature for structured extraction
            max_tokens=1000,
            image_data=document_base64  # Pass image to Scout's vision API
        )

        # Parse JSON response
        try:
            extracted_data = json.loads(response_text)
            return extracted_data
        except json.JSONDecodeError:
            # Fallback: try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                extracted_data = json.loads(json_match.group(0))
                return extracted_data
            else:
                return {
                    "error": "Failed to parse AI response",
                    "raw_response": response_text,
                    "confidence": 0.0
                }

    async def extract_bol(self, document_url: str) -> Dict[str, Any]:
        """
        Extract Bill of Lading details from document.

        Returns:
            {
                "bol_number": str,
                "shipper_name": str,
                "consignee_name": str,
                "origin": str,
                "destination": str,
                "pieces": int,
                "weight": float,
                "commodity": str,
                "special_instructions": str | None,
                "confidence": float
            }
        """
        document_base64 = await self._download_and_encode(document_url)

        system_prompt = """You are Annie, an AI Dispatcher extracting BOL (Bill of Lading) data.

Extract these fields from the document:
- BOL number
- Shipper name
- Consignee name
- Origin address
- Destination address
- Number of pieces
- Total weight (in lbs)
- Commodity/freight description
- Special instructions (if any)

Return ONLY valid JSON in this format:
{
    "bol_number": "BOL-12345",
    "shipper_name": "ABC Company",
    "consignee_name": "XYZ Warehouse",
    "origin": "123 Main St, Chicago, IL 60601",
    "destination": "456 Oak Ave, Los Angeles, CA 90001",
    "pieces": 10,
    "weight": 5000.0,
    "commodity": "Electronics",
    "special_instructions": "Liftgate required",
    "confidence": 0.92
}
"""

        user_prompt = "Extract the BOL details from this document:"

        response_text, metadata = await self.llm_router.generate(
            agent_role="annie",
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=1000,
            image_data=document_base64
        )

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                return {"error": "Failed to parse BOL", "raw_response": response_text}

    async def _download_and_encode(self, url: str) -> str:
        """
        Download document from URL and encode as base64.

        Required for passing to Llama 4 Scout's vision API.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()

            # Encode as base64
            document_bytes = response.content
            document_base64 = base64.b64encode(document_bytes).decode('utf-8')

            return document_base64
