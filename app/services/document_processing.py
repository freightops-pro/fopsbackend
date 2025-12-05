from __future__ import annotations

import io
import re
import uuid
from datetime import datetime
from typing import Tuple, Optional

import pdfplumber
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentProcessingJob
from app.schemas.document import DocumentProcessingJobResponse


class DocumentProcessingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def process_document(
        self,
        *,
        company_id: str,
        file: UploadFile,
        load_id: str | None = None,
    ) -> DocumentProcessingJobResponse:
        file_bytes = await file.read()
        filename = file.filename or "document"

        # Extract text based on file type
        raw_text = self._extract_text(file_bytes, filename)
        parsed_payload, confidence = self._parse_rate_confirmation(raw_text)

        job = DocumentProcessingJob(
            id=str(uuid.uuid4()),
            company_id=company_id,
            load_id=load_id,
            filename=filename,
            status="COMPLETED",
            raw_text=raw_text,
            parsed_payload=parsed_payload,
            field_confidence=confidence,
            errors=None,
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
    ) -> dict:
        """Extract load data from a rate confirmation PDF."""
        file_bytes = await file.read()
        filename = file.filename or "rate_confirmation.pdf"

        raw_text = self._extract_text(file_bytes, filename)
        parsed_payload, confidence = self._parse_rate_confirmation(raw_text)

        return {
            "success": True,
            "loadData": parsed_payload,
            "confidence": confidence,
            "rawText": raw_text[:500] if raw_text else None,  # First 500 chars for debugging
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
        """Parse rate confirmation text to extract load details."""
        payload = {}
        confidence = {}

        if not raw_text or raw_text.startswith("No text") or raw_text.startswith("PDF extraction error"):
            return payload, confidence

        lines = raw_text.splitlines()
        full_text_lower = raw_text.lower()

        # Customer/Shipper name
        for line in lines:
            lowered = line.lower()
            if any(kw in lowered for kw in ["customer", "shipper", "consignor", "bill to"]) and ":" in line:
                payload["customerName"] = line.split(":", 1)[1].strip()
                confidence["customerName"] = 0.85
                break

        # Rate/Amount
        rate_patterns = [
            r"(?:rate|total|amount|line\s*haul)[\s:]*\$?([\d,]+\.?\d*)",
            r"\$\s*([\d,]+\.?\d*)",
        ]
        for pattern in rate_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                rate_str = match.group(1).replace(",", "")
                try:
                    payload["rate"] = float(rate_str)
                    confidence["rate"] = 0.80
                    break
                except ValueError:
                    continue

        # Pickup location
        pickup_patterns = [
            r"(?:pickup|origin|ship\s*from|pick\s*up)[\s:]*([^\n]+)",
            r"(?:from|origin)[\s:]*([A-Za-z\s]+,\s*[A-Z]{2})",
        ]
        for pattern in pickup_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                if len(location) > 3:
                    payload["pickupLocation"] = location[:100]  # Limit length
                    confidence["pickupLocation"] = 0.75
                    break

        # Delivery location
        delivery_patterns = [
            r"(?:delivery|destination|deliver\s*to|ship\s*to|consignee)[\s:]*([^\n]+)",
            r"(?:to|destination)[\s:]*([A-Za-z\s]+,\s*[A-Z]{2})",
        ]
        for pattern in delivery_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                if len(location) > 3:
                    payload["deliveryLocation"] = location[:100]
                    confidence["deliveryLocation"] = 0.75
                    break

        # Reference/Load number
        ref_patterns = [
            r"(?:load\s*#?|reference\s*#?|ref\s*#?|order\s*#?)[\s:]*([A-Z0-9\-]+)",
            r"(?:confirmation\s*#?)[\s:]*([A-Z0-9\-]+)",
        ]
        for pattern in ref_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                payload["referenceNumber"] = match.group(1).strip()
                confidence["referenceNumber"] = 0.85
                break

        # Pickup date
        date_patterns = [
            r"(?:pickup\s*date|ship\s*date)[\s:]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
            r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
        ]
        for pattern in date_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                payload["pickupDate"] = match.group(1)
                confidence["pickupDate"] = 0.70
                break

        # Commodity/Description
        commodity_patterns = [
            r"(?:commodity|description|freight|cargo)[\s:]*([^\n]+)",
        ]
        for pattern in commodity_patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                commodity = match.group(1).strip()
                if len(commodity) > 2:
                    payload["commodity"] = commodity[:100]
                    confidence["commodity"] = 0.80
                    break

        # Weight
        weight_pattern = r"(?:weight|lbs|pounds)[\s:]*(\d{1,3}(?:,\d{3})*)"
        match = re.search(weight_pattern, raw_text, re.IGNORECASE)
        if match:
            weight_str = match.group(1).replace(",", "")
            try:
                payload["weight"] = int(weight_str)
                confidence["weight"] = 0.75
            except ValueError:
                pass

        payload["processedAt"] = datetime.utcnow().isoformat()
        return payload, confidence
