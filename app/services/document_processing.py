from __future__ import annotations

import io
import os
import re
import uuid
from datetime import datetime
from typing import Tuple, Optional, Dict, List, Any

import pdfplumber
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentProcessingJob
from app.schemas.document import DocumentProcessingJobResponse
from app.services.ai_usage import AIUsageService
from app.services.claude_ocr import ClaudeOCRService


class DocumentProcessingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.ai_usage_service = AIUsageService(db)
        self.claude_ocr = ClaudeOCRService()
        self.use_ai = os.getenv("ENABLE_AI_OCR", "true").lower() == "true"

    def _transform_to_load_create(self, ocr_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform OCR extraction output to LoadCreate schema format.

        Converts:
        - equipment_type → load_type (container stays container, others map to ftl)
        - pickup_location/delivery_location dicts → stops array with LoadStopCreate objects
        - special_instructions → notes
        - Date strings → datetime objects
        """
        load_data = {}

        # Direct mappings (already in correct format from AI)
        if "customer_name" in ocr_data:
            load_data["customer_name"] = ocr_data["customer_name"]
        if "base_rate" in ocr_data:
            load_data["base_rate"] = float(ocr_data["base_rate"])
        if "commodity" in ocr_data:
            load_data["commodity"] = ocr_data["commodity"]

        # Map equipment_type to load_type
        equipment_type = ocr_data.get("equipment_type", "").lower()
        if equipment_type == "container":
            load_data["load_type"] = "container"
        else:
            # All other equipment types are FTL (Full Truckload)
            load_data["load_type"] = "ftl"

        # Map special_instructions to notes
        if ocr_data.get("special_instructions"):
            load_data["notes"] = ocr_data["special_instructions"]

        # Transform locations into stops array
        stops = []

        # Pickup stop
        if "pickup_location" in ocr_data and ocr_data["pickup_location"]:
            pickup = ocr_data["pickup_location"]
            pickup_stop = {
                "stop_type": "pickup",
                "location_name": pickup.get("city", "Pickup Location"),
                "address": pickup.get("full_address"),
                "city": pickup.get("city"),
                "state": pickup.get("state"),
                "postal_code": pickup.get("postal_code"),
            }

            # Add scheduled_at if pickup_date exists
            if ocr_data.get("pickup_date"):
                try:
                    pickup_stop["scheduled_at"] = datetime.fromisoformat(ocr_data["pickup_date"])
                except (ValueError, TypeError):
                    pass  # Skip if date parsing fails

            stops.append(pickup_stop)

        # Delivery stop
        if "delivery_location" in ocr_data and ocr_data["delivery_location"]:
            delivery = ocr_data["delivery_location"]
            delivery_stop = {
                "stop_type": "drop",
                "location_name": delivery.get("city", "Delivery Location"),
                "address": delivery.get("full_address"),
                "city": delivery.get("city"),
                "state": delivery.get("state"),
                "postal_code": delivery.get("postal_code"),
            }

            # Add scheduled_at if delivery_date exists
            if ocr_data.get("delivery_date"):
                try:
                    delivery_stop["scheduled_at"] = datetime.fromisoformat(ocr_data["delivery_date"])
                except (ValueError, TypeError):
                    pass  # Skip if date parsing fails

            stops.append(delivery_stop)

        if stops:
            load_data["stops"] = stops

        # Container-specific fields (pass through if present)
        container_fields = [
            "container_number", "container_size", "container_type",
            "vessel_name", "voyage_number", "origin_port_code",
            "destination_port_code", "drayage_appointment"
        ]
        for field in container_fields:
            if field in ocr_data and ocr_data[field]:
                load_data[field] = ocr_data[field]

        # Weight (store in metadata for now, as LoadCreate doesn't have weight field)
        if "weight" in ocr_data:
            if "metadata" not in load_data:
                load_data["metadata"] = {}
            load_data["metadata"]["weight"] = ocr_data["weight"]

        # Reference number (store in metadata)
        if "reference_number" in ocr_data:
            if "metadata" not in load_data:
                load_data["metadata"] = {}
            load_data["metadata"]["reference_number"] = ocr_data["reference_number"]

        return load_data

    async def process_document(
        self,
        *,
        company_id: str,
        file: UploadFile,
        load_id: str | None = None,
        user_id: str | None = None,
    ) -> DocumentProcessingJobResponse:
        file_bytes = await file.read()
        filename = file.filename or "document"

        # Check usage limits and decide on processing method
        use_claude = self.use_ai and self.claude_ocr.enabled
        parsed_payload = {}
        confidence = {}
        raw_text = ""
        errors = None
        status = "COMPLETED"
        extraction_method = "regex"  # default

        if use_claude:
            # Check usage quota
            allowed, quota_message = await self.ai_usage_service.check_and_update_quota(
                company_id, "ocr"
            )

            if allowed:
                # Try Claude API extraction
                try:
                    parsed_payload, confidence, raw_text = await self.claude_ocr.extract_from_document(
                        file_bytes, filename, "rate_confirmation"
                    )
                    extraction_method = "claude_ai"

                    # Transform OCR output to LoadCreate-compatible format
                    parsed_payload["load_create_data"] = self._transform_to_load_create(parsed_payload)

                    # Log successful usage
                    await self.ai_usage_service.log_usage(
                        company_id=company_id,
                        user_id=user_id,
                        operation_type="ocr",
                        status="success",
                        tokens_used=2000,  # Approximate
                        cost_usd=0.006,  # Approximate: $3/million input + $15/million output
                        entity_type="document",
                        entity_id=load_id,
                    )

                except Exception as e:
                    # Claude failed, fall back to regex
                    errors = {"claude_error": str(e)}
                    raw_text = self._extract_text(file_bytes, filename)
                    parsed_payload, confidence = self._parse_rate_confirmation(raw_text)
                    extraction_method = "regex_fallback"

                    # Log failed usage (don't count against quota since it already counted)
                    await self.ai_usage_service.log_usage(
                        company_id=company_id,
                        user_id=user_id,
                        operation_type="ocr",
                        status="failed",
                        error_message=str(e),
                    )
            else:
                # Quota exceeded, use free regex method
                raw_text = self._extract_text(file_bytes, filename)
                parsed_payload, confidence = self._parse_rate_confirmation(raw_text)
                extraction_method = "regex_quota_exceeded"
                errors = {"quota": quota_message}

                # Log rate limit
                await self.ai_usage_service.log_usage(
                    company_id=company_id,
                    user_id=user_id,
                    operation_type="ocr",
                    status="rate_limited",
                    error_message=quota_message,
                )
        else:
            # AI disabled or not configured, use regex
            raw_text = self._extract_text(file_bytes, filename)
            parsed_payload, confidence = self._parse_rate_confirmation(raw_text)

        # Add metadata about extraction method
        parsed_payload["_extraction_method"] = extraction_method

        job = DocumentProcessingJob(
            id=str(uuid.uuid4()),
            company_id=company_id,
            load_id=load_id,
            filename=filename,
            status=status,
            raw_text=raw_text,
            parsed_payload=parsed_payload,
            field_confidence=confidence,
            errors=errors,
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return DocumentProcessingJobResponse.model_validate(job)

    async def extract_rate_confirmation(
        self,
        *,
        company_id: str,
        file: UploadFile,
        user_id: str | None = None,
    ) -> dict:
        """Extract load data from a rate confirmation PDF."""
        file_bytes = await file.read()
        filename = file.filename or "rate_confirmation.pdf"

        # Check usage limits and decide on processing method
        use_claude = self.use_ai and self.claude_ocr.enabled
        parsed_payload = {}
        confidence = {}
        raw_text = ""
        extraction_method = "regex"

        if use_claude:
            # Check usage quota
            allowed, quota_message = await self.ai_usage_service.check_and_update_quota(
                company_id, "ocr"
            )

            if allowed:
                # Try Claude API extraction
                try:
                    parsed_payload, confidence, raw_text = await self.claude_ocr.extract_from_document(
                        file_bytes, filename, "rate_confirmation"
                    )
                    extraction_method = "claude_ai"

                    # Transform OCR output to LoadCreate-compatible format
                    parsed_payload["load_create_data"] = self._transform_to_load_create(parsed_payload)

                    # Log successful usage
                    await self.ai_usage_service.log_usage(
                        company_id=company_id,
                        user_id=user_id,
                        operation_type="ocr",
                        status="success",
                        tokens_used=2000,
                        cost_usd=0.006,
                        entity_type="rate_confirmation",
                    )

                except Exception as e:
                    # Claude failed, fall back to regex
                    raw_text = self._extract_text(file_bytes, filename)
                    parsed_payload, confidence = self._parse_rate_confirmation(raw_text)
                    extraction_method = "regex_fallback"

                    await self.ai_usage_service.log_usage(
                        company_id=company_id,
                        user_id=user_id,
                        operation_type="ocr",
                        status="failed",
                        error_message=str(e),
                    )
            else:
                # Quota exceeded, use free regex method
                raw_text = self._extract_text(file_bytes, filename)
                parsed_payload, confidence = self._parse_rate_confirmation(raw_text)
                extraction_method = "regex_quota_exceeded"

                # Log rate limit
                await self.ai_usage_service.log_usage(
                    company_id=company_id,
                    user_id=user_id,
                    operation_type="ocr",
                    status="rate_limited",
                    error_message=quota_message,
                )

                # Add quota info to response
                return {
                    "success": False,
                    "error": quota_message,
                    "loadData": parsed_payload,  # Still return regex results
                    "confidence": confidence,
                    "extractionMethod": extraction_method,
                    "quotaExceeded": True,
                }
        else:
            # AI disabled or not configured, use regex
            raw_text = self._extract_text(file_bytes, filename)
            parsed_payload, confidence = self._parse_rate_confirmation(raw_text)

        return {
            "success": True,
            "loadData": parsed_payload,
            "confidence": confidence,
            "rawText": raw_text[:500] if raw_text else None,
            "extractionMethod": extraction_method,
        }

    def _extract_text(self, file_bytes: bytes, filename: str) -> str:
        """Extract text from file based on type."""
        lower_filename = filename.lower()

        # Handle PDF files
        if lower_filename.endswith(".pdf"):
            return self._extract_pdf_text(file_bytes)

        # Handle plain text files
        try:
            return file_bytes.decode("utf-8", errors="ignore") or "No text extracted."
        except Exception:
            return "No text extracted."

    def _extract_pdf_text(self, file_bytes: bytes) -> str:
        """Extract text from PDF using pdfplumber."""
        try:
            text_parts = []
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

            full_text = "\n".join(text_parts)
            return full_text if full_text.strip() else "No text extracted from PDF."
        except Exception as e:
            return f"PDF extraction error: {str(e)}"

    def _parse_rate_confirmation(self, raw_text: str) -> Tuple[dict, dict]:
        """
        Parse rate confirmation text to extract load details using improved regex.

        Note: This is the improved fallback when AI quota is exceeded.
        Still not as accurate as AI extraction, but better than the original regex.
        """
        payload = {}
        confidence = {}

        if not raw_text or raw_text.startswith("No text") or raw_text.startswith("PDF extraction error"):
            return payload, confidence

        lines = raw_text.splitlines()
        full_text_lower = raw_text.lower()

        # Customer/Shipper name with validation
        for line in lines:
            lowered = line.lower()
            if any(kw in lowered for kw in ["customer", "shipper", "consignor", "bill to"]) and ":" in line:
                name = line.split(":", 1)[1].strip()
                # Filter out common junk values
                if len(name) > 2 and not name.isdigit() and name.lower() not in ["n/a", "na", "none", "tbd"]:
                    payload["customerName"] = name[:100]
                    confidence["customerName"] = 0.70  # Lower confidence for regex
                    break

        # Rate/Amount with sanity checks
        rate_patterns = [
            r"(?:rate|total|amount|line\s*haul)[\s:]*\$?([\d,]+\.?\d*)",
            r"\$\s*([\d,]+\.?\d*)",
        ]
        for pattern in rate_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                rate_str = match.group(1).replace(",", "")
                try:
                    rate_val = float(rate_str)
                    # Sanity check: typical freight rates are $10-$100,000
                    if 10.0 <= rate_val <= 100000.0:
                        payload["rate"] = rate_val
                        confidence["rate"] = 0.65
                        break
                except ValueError:
                    continue

        # Pickup location with better city/state detection
        pickup_patterns = [
            r"(?:pickup|origin)[\s:]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?,\s*[A-Z]{2})",  # City, ST format
            r"(?:pickup|origin|ship\s*from|pick\s*up)[\s:]*([^\n]{5,80})",  # Fallback
            r"(?:from|origin)[\s:]*([A-Za-z\s]+,\s*[A-Z]{2})",
        ]
        for pattern in pickup_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                # Validate location has reasonable length and content
                if 5 <= len(location) <= 80 and not location.isdigit():
                    payload["pickupLocation"] = location
                    confidence["pickupLocation"] = 0.70
                    break

        # Delivery location with better city/state detection
        delivery_patterns = [
            r"(?:delivery|destination|deliver\s*to|consignee)[\s:]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?,\s*[A-Z]{2})",
            r"(?:delivery|destination|deliver\s*to|ship\s*to|consignee)[\s:]*([^\n]{5,80})",
            r"(?:to|destination)[\s:]*([A-Za-z\s]+,\s*[A-Z]{2})",
        ]
        for pattern in delivery_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                if 5 <= len(location) <= 80 and not location.isdigit():
                    payload["deliveryLocation"] = location
                    confidence["deliveryLocation"] = 0.70
                    break

        # Reference/Load number with validation
        ref_patterns = [
            r"(?:load\s*#?|reference\s*#?|ref\s*#?|order\s*#?)[\s:]*([A-Z0-9\-]{3,20})",
            r"(?:confirmation\s*#?)[\s:]*([A-Z0-9\-]{3,20})",
        ]
        for pattern in ref_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                ref_num = match.group(1).strip()
                # Validate reference number format
                if 3 <= len(ref_num) <= 20:
                    payload["referenceNumber"] = ref_num
                    confidence["referenceNumber"] = 0.75
                    break

        # Pickup date with validation
        date_patterns = [
            r"(?:pickup\s*date|ship\s*date)[\s:]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
            r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
        ]
        for pattern in date_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                # Basic date format validation
                if "/" in date_str or "-" in date_str:
                    payload["pickupDate"] = date_str
                    confidence["pickupDate"] = 0.60
                    break

        # Commodity/Description with validation
        commodity_patterns = [
            r"(?:commodity|description|freight|cargo)[\s:]*([^\n]{3,100})",
        ]
        for pattern in commodity_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                commodity = match.group(1).strip()
                # Filter out junk values
                if 3 <= len(commodity) <= 100 and commodity.lower() not in ["n/a", "na", "none", "tbd"]:
                    payload["commodity"] = commodity
                    confidence["commodity"] = 0.70
                    break

        # Weight with sanity checks
        weight_patterns = [
            r"(?:weight|lbs|pounds)[\s:]*(\d{1,3}(?:,\d{3})*)",
            r"(\d{1,3}(?:,\d{3})*)\s*(?:lbs|pounds|lb)",
        ]
        for pattern in weight_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                weight_str = match.group(1).replace(",", "")
                try:
                    weight_val = int(weight_str)
                    # Sanity check: typical freight weights are 100-100,000 lbs
                    if 100 <= weight_val <= 100000:
                        payload["weight"] = weight_val
                        confidence["weight"] = 0.65
                        break
                except ValueError:
                    continue

        payload["processedAt"] = datetime.utcnow().isoformat()
        payload["_extraction_method"] = "regex_improved"  # Mark as improved regex
        return payload, confidence
