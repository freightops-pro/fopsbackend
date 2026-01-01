from __future__ import annotations

import base64
import io
import json
import os
from typing import Tuple

import pdfplumber
import fitz  # PyMuPDF - no external dependencies like poppler


class ClaudeOCRService:
    """
    Service for AI-powered document extraction.

    Supports multiple AI providers:
    - Gemini 2.0 Flash (recommended, 40x cheaper)
    - Claude 3.5 Sonnet (highest accuracy)
    - GPT-4o-mini (good balance)
    """

    def __init__(self) -> None:
        # Check which AI provider is configured
        self.provider = os.getenv("AI_OCR_PROVIDER", "gemini").lower()  # gemini, claude, or openai

        # Load appropriate API key
        self.gemini_api_key = os.getenv("GOOGLE_AI_API_KEY", "")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")

        # Determine if enabled
        if self.provider == "gemini":
            self.enabled = bool(self.gemini_api_key)
            self.model = "gemini-2.5-flash"  # Stable Gemini 2.5 Flash
        elif self.provider == "claude":
            self.enabled = bool(self.anthropic_api_key)
            self.model = "claude-3-5-sonnet-20241022"
        elif self.provider == "openai":
            self.enabled = bool(self.openai_api_key)
            self.model = "gpt-4o-mini"
        else:
            self.enabled = False
            self.model = None

    async def extract_from_document(
        self,
        file_bytes: bytes,
        filename: str,
        document_type: str = "rate_confirmation",
    ) -> Tuple[dict, dict, str]:
        """
        Extract structured data from document using AI.

        Strategy:
        1. Try text extraction first (works without poppler)
        2. If text found, use AI for structured extraction
        3. If no text, try image conversion (requires poppler)

        Returns:
            (parsed_data, confidence_scores, raw_text)
        """
        if not self.enabled:
            raise ValueError("AI OCR not enabled. Check API key configuration.")

        # First, try extracting text (works for most PDFs, no poppler needed)
        raw_text = self._extract_text_fallback(file_bytes, filename)

        # Build extraction prompt
        prompt = self._build_extraction_prompt(document_type)

        # If we got text, use text-based AI extraction
        if raw_text and not raw_text.startswith("No text") and not raw_text.startswith("PDF extraction error"):
            try:
                print(f"[INFO] Extracted {len(raw_text)} characters of text from PDF")
                print("[INFO] Sending text to Gemini for AI extraction...")
                parsed_data, confidence = await self._call_ai_with_text(raw_text, prompt)
                print("[INFO] Text-based AI extraction successful!")
                return parsed_data, confidence, raw_text
            except Exception as e:
                # Text-based extraction failed - this is the real error we want to see
                raise ValueError(f"Text-based AI extraction failed: {str(e)}")

        # No extractable text found - this is a scanned/image-based PDF
        print("[INFO] No extractable text found in PDF - attempting image-based AI extraction")
        try:
            image_data = await self._prepare_document(file_bytes, filename)
            parsed_data, confidence = await self._call_claude_api(image_data, prompt)
            return parsed_data, confidence, raw_text
        except Exception as e:
            raise ValueError(f"Image-based extraction failed: {str(e)}. The PDF may be corrupted or in an unsupported format.")

    async def _prepare_document(self, file_bytes: bytes, filename: str) -> str:
        """Convert document to base64-encoded image for AI vision processing."""
        lower_filename = filename.lower()

        if lower_filename.endswith(".pdf"):
            # Convert PDF first page to image using PyMuPDF (no poppler required)
            try:
                # Open PDF with PyMuPDF
                pdf_document = fitz.open(stream=file_bytes, filetype="pdf")

                if pdf_document.page_count == 0:
                    raise ValueError("PDF has no pages")

                # Get first page
                page = pdf_document[0]

                # Render page to image (matrix for 200 DPI: 200/72 = 2.78)
                mat = fitz.Matrix(2.78, 2.78)
                pix = page.get_pixmap(matrix=mat)

                # Convert to PNG bytes
                img_bytes = pix.tobytes("png")
                pdf_document.close()

                return base64.standard_b64encode(img_bytes).decode('utf-8')
            except Exception as e:
                raise ValueError(f"Failed to convert PDF to image: {str(e)}")

        elif lower_filename.endswith(('.png', '.jpg', '.jpeg', '.webp')):
            # Already an image
            return base64.standard_b64encode(file_bytes).decode('utf-8')

        else:
            raise ValueError(f"Unsupported file type: {filename}")

    def _build_extraction_prompt(self, document_type: str) -> str:
        """Build prompt for Claude based on document type."""
        if document_type == "rate_confirmation":
            return """Analyze this freight rate confirmation document and extract the following fields into JSON format.
Use snake_case for all field names to match our backend schema:

{
  "customer_name": "Company name of the customer/shipper",
  "base_rate": 123.45,
  "commodity": "Description of freight/commodity (or 'General Freight' if not specified)",
  "equipment_type": "Equipment type: dry_van, reefer, flatbed, step_deck, container, or other",
  "weight": 12345,
  "reference_number": "Load or reference number",
  "pickup_location": {
    "full_address": "Complete pickup address",
    "city": "Pickup city",
    "state": "Pickup state (2-letter code)",
    "postal_code": "Pickup ZIP code"
  },
  "delivery_location": {
    "full_address": "Complete delivery address",
    "city": "Delivery city",
    "state": "Delivery state (2-letter code)",
    "postal_code": "Delivery ZIP code"
  },
  "pickup_date": "Pickup date in YYYY-MM-DD format",
  "delivery_date": "Delivery date in YYYY-MM-DD format",
  "special_instructions": "Any special instructions or notes",
  "container_number": "Container number if this is a container load",
  "container_size": "Container size if applicable (20, 40, 45, 53)",
  "container_type": "Container type if applicable"
}

CRITICAL INSTRUCTIONS:
- Return ONLY valid JSON, no markdown code blocks or additional text
- Use null for fields that are not found
- For base_rate: extract the main line haul amount (exclude fuel surcharges, accessorials)
- For equipment_type: standardize to one of: dry_van, reefer, flatbed, step_deck, container, or other
- For locations: parse addresses to extract city, state, and ZIP when possible
- For dates: convert to YYYY-MM-DD format (e.g., "2025-12-15")
- For commodity: if not explicitly stated, use "General Freight"
- If you find container-related information, this is a container load

Return the JSON object directly without any wrapping text."""

        elif document_type == "bol":
            return """Analyze this Bill of Lading (BOL) document and extract key information into JSON format:

{
  "bolNumber": "BOL number",
  "shipperName": "Shipper company name",
  "shipperAddress": "Full shipper address",
  "consigneeName": "Consignee company name",
  "consigneeAddress": "Full consignee address",
  "pickupDate": "Pickup date",
  "deliveryDate": "Delivery date",
  "commodity": "Freight description",
  "weight": 12345,
  "pieces": 10,
  "pallets": 5,
  "specialInstructions": "Any special handling instructions"
}

Return ONLY valid JSON with confidence scores."""

        else:
            return f"Extract all relevant freight/logistics information from this {document_type} document as JSON."

    async def _call_claude_api(self, image_base64: str, prompt: str) -> Tuple[dict, dict]:
        """Call AI API for vision-based extraction (routes to appropriate provider)."""
        if self.provider == "gemini":
            return await self._call_gemini_api(image_base64, prompt)
        elif self.provider == "claude":
            return await self._call_claude_direct(image_base64, prompt)
        elif self.provider == "openai":
            return await self._call_openai_api(image_base64, prompt)
        else:
            raise ValueError(f"Unknown AI provider: {self.provider}")

    async def _call_ai_with_text(self, text: str, prompt: str) -> Tuple[dict, dict]:
        """Call AI API with extracted text (no image needed - works without poppler)."""
        if self.provider == "gemini":
            return await self._call_gemini_with_text(text, prompt)
        elif self.provider == "claude":
            return await self._call_claude_with_text(text, prompt)
        elif self.provider == "openai":
            return await self._call_openai_with_text(text, prompt)
        else:
            raise ValueError(f"Unknown AI provider: {self.provider}")

    async def _call_gemini_api(self, image_base64: str, prompt: str) -> Tuple[dict, dict]:
        """Call Google Gemini API for vision-based extraction (40x cheaper than Claude)."""
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("google-generativeai package not installed. Run: poetry add google-generativeai")

        genai.configure(api_key=self.gemini_api_key)

        try:
            # Convert base64 to bytes for Gemini
            import base64 as b64
            image_bytes = b64.b64decode(image_base64)

            # Create model
            model = genai.GenerativeModel(self.model)

            # Prepare content
            from PIL import Image
            image = Image.open(io.BytesIO(image_bytes))

            # Generate content
            response = model.generate_content([prompt, image])

            # Parse response
            response_text = response.text

            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                data = json.loads(json_str)

                # Separate confidence scores if provided
                confidence = data.pop('confidence', {})

                # If no explicit confidence, assign high confidence to all fields
                if not confidence:
                    confidence = {key: 0.92 for key in data.keys() if data[key] is not None}

                return data, confidence
            else:
                raise ValueError("No valid JSON found in Gemini response")

        except Exception as e:
            raise ValueError(f"Gemini API error: {str(e)}")

    async def _call_claude_direct(self, image_base64: str, prompt: str) -> Tuple[dict, dict]:
        """Call Claude API directly."""
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic package not installed. Run: poetry add anthropic")

        client = anthropic.Anthropic(api_key=self.anthropic_api_key)

        try:
            message = client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_base64,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            }
                        ],
                    }
                ],
            )

            # Parse response
            response_text = message.content[0].text

            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                data = json.loads(json_str)

                # Separate confidence scores if provided
                confidence = data.pop('confidence', {})

                if not confidence:
                    confidence = {key: 0.95 for key in data.keys() if data[key] is not None}

                return data, confidence
            else:
                raise ValueError("No valid JSON found in Claude response")

        except Exception as e:
            raise ValueError(f"Claude API error: {str(e)}")

    async def _call_openai_api(self, image_base64: str, prompt: str) -> Tuple[dict, dict]:
        """Call OpenAI GPT-4o-mini API."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package not installed. Run: poetry add openai")

        client = OpenAI(api_key=self.openai_api_key)

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                }
                            }
                        ],
                    }
                ],
                max_tokens=2000,
            )

            response_text = response.choices[0].message.content

            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                data = json.loads(json_str)

                # Separate confidence scores
                confidence = data.pop('confidence', {})

                if not confidence:
                    confidence = {key: 0.93 for key in data.keys() if data[key] is not None}

                return data, confidence
            else:
                raise ValueError("No valid JSON found in OpenAI response")

        except Exception as e:
            raise ValueError(f"OpenAI API error: {str(e)}")

    async def _call_gemini_with_text(self, text: str, prompt: str) -> Tuple[dict, dict]:
        """Call Gemini with text only (no image - works without poppler)."""
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("google-generativeai package not installed. Run: poetry add google-generativeai")

        genai.configure(api_key=self.gemini_api_key)

        try:
            model = genai.GenerativeModel(self.model)

            # Combine prompt with extracted text
            full_prompt = f"{prompt}\n\nDocument Text:\n{text}"

            response = model.generate_content(full_prompt)
            response_text = response.text

            # Extract first complete JSON object from response
            json_start = response_text.find('{')
            if json_start < 0:
                raise ValueError("No JSON found in Gemini response")

            # Find matching closing brace by counting braces
            brace_count = 0
            json_end = -1
            for i in range(json_start, len(response_text)):
                if response_text[i] == '{':
                    brace_count += 1
                elif response_text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i + 1
                        break

            if json_end < 0:
                raise ValueError("No complete JSON found in Gemini response")

            json_str = response_text[json_start:json_end]
            data = json.loads(json_str)

            # Separate confidence scores if provided
            confidence = data.pop('confidence', {})

            # If no explicit confidence, assign high confidence to all fields
            if not confidence:
                confidence = {key: 0.92 for key in data.keys() if data[key] is not None}

            return data, confidence

        except Exception as e:
            raise ValueError(f"Gemini text extraction error: {str(e)}")

    async def _call_claude_with_text(self, text: str, prompt: str) -> Tuple[dict, dict]:
        """Call Claude with text only (no image - works without poppler)."""
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic package not installed. Run: poetry add anthropic")

        client = anthropic.Anthropic(api_key=self.anthropic_api_key)

        try:
            full_prompt = f"{prompt}\n\nDocument Text:\n{text}"

            message = client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": full_prompt}]
            )

            response_text = message.content[0].text

            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                data = json.loads(json_str)

                # Separate confidence scores if provided
                confidence = data.pop('confidence', {})

                if not confidence:
                    confidence = {key: 0.95 for key in data.keys() if data[key] is not None}

                return data, confidence
            else:
                raise ValueError("No valid JSON found in Claude response")

        except Exception as e:
            raise ValueError(f"Claude text extraction error: {str(e)}")

    async def _call_openai_with_text(self, text: str, prompt: str) -> Tuple[dict, dict]:
        """Call OpenAI with text only (no image - works without poppler)."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package not installed. Run: poetry add openai")

        client = OpenAI(api_key=self.openai_api_key)

        try:
            full_prompt = f"{prompt}\n\nDocument Text:\n{text}"

            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": full_prompt}],
                max_tokens=2000,
            )

            response_text = response.choices[0].message.content

            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                data = json.loads(json_str)

                # Separate confidence scores
                confidence = data.pop('confidence', {})

                if not confidence:
                    confidence = {key: 0.93 for key in data.keys() if data[key] is not None}

                return data, confidence
            else:
                raise ValueError("No valid JSON found in OpenAI response")

        except Exception as e:
            raise ValueError(f"OpenAI text extraction error: {str(e)}")

    def _extract_text_fallback(self, file_bytes: bytes, filename: str) -> str:
        """Fallback text extraction using pdfplumber (non-AI)."""
        lower_filename = filename.lower()

        if lower_filename.endswith(".pdf"):
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

        return "No text extraction available for this file type."
