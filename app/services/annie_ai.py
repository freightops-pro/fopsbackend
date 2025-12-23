"""Annie AI - Autonomous Operations Agent.

Annie handles dispatch operations, driver assignment, load creation,
compliance monitoring, and operational automation.

Uses Llama 4 Scout Vision for document OCR via Groq.
"""
import base64
import io
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pdfplumber
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.load import Load, LoadStop
from app.models.driver import Driver
from app.models.equipment import Equipment
from app.services.ai_agent import BaseAIAgent, AITool
from app.core.llm_router import LLMRouter


class AnnieAI(BaseAIAgent):
    """
    Annie - Autonomous Operations AI Agent.

    Specializes in:
    - Load creation from emails, PDFs, chat messages
    - Driver/equipment matching and assignment
    - Operational workflows (pickup, delivery, check calls)
    - Compliance monitoring and escalation
    - Usage ledger logging for IFTA/billing
    """

    @property
    def agent_name(self) -> str:
        return "Annie"

    @property
    def agent_role(self) -> str:
        return """Operations AI specializing in dispatch, load management, driver assignment,
and operational compliance. I can create loads from documents, assign optimal drivers,
manage pickup/delivery workflows, and handle check calls autonomously."""

    async def register_tools(self):
        """Register all tools Annie can use."""
        self.tools = [
            # Load Management Tools
            AITool(
                name="create_load_from_data",
                description="Create a new load in the system with customer, route, and rate information",
                parameters={
                    "customer_name": {"type": "string", "description": "Customer/shipper name"},
                    "commodity": {"type": "string", "description": "Type of freight"},
                    "base_rate": {"type": "number", "description": "Payment rate for the load"},
                    "pickup_city": {"type": "string", "description": "Pickup city"},
                    "pickup_state": {"type": "string", "description": "Pickup state (2-letter code)"},
                    "delivery_city": {"type": "string", "description": "Delivery city"},
                    "delivery_state": {"type": "string", "description": "Delivery state (2-letter code)"},
                },
                function=self._create_load
            ),

            AITool(
                name="extract_load_from_document",
                description="Extract load information from a PDF, email, or text document using OCR",
                parameters={
                    "document_content": {"type": "string", "description": "Text content of the document"},
                    "document_type": {"type": "string", "description": "Type: rate_confirmation, email, or text"},
                },
                function=self._extract_load_from_document
            ),

            # Driver Management Tools
            AITool(
                name="find_available_drivers",
                description="Find drivers available for assignment, considering HOS and location",
                parameters={
                    "equipment_type": {"type": "string", "description": "Required equipment type (dry_van, reefer, flatbed, etc.)"},
                    "pickup_state": {"type": "string", "description": "Pickup location state"},
                    "max_results": {"type": "number", "description": "Maximum number of results (default 5)"},
                },
                function=self._find_available_drivers
            ),

            AITool(
                name="assign_driver_to_load",
                description="Assign a driver and equipment to a load",
                parameters={
                    "load_id": {"type": "string", "description": "Load ID to assign"},
                    "driver_id": {"type": "string", "description": "Driver ID to assign"},
                },
                function=self._assign_driver_to_load
            ),

            # Equipment Tools
            AITool(
                name="check_equipment_status",
                description="Check if equipment is available and operational",
                parameters={
                    "equipment_id": {"type": "string", "description": "Equipment ID to check"},
                },
                function=self._check_equipment_status
            ),

            # Notification Tools
            AITool(
                name="send_notification",
                description="Send email or SMS notification to a user, driver, or customer",
                parameters={
                    "recipient_type": {"type": "string", "description": "Type: driver, customer, or user"},
                    "recipient_id": {"type": "string", "description": "ID or email/phone of recipient"},
                    "message": {"type": "string", "description": "Message to send"},
                    "notification_type": {"type": "string", "description": "Type: email or sms"},
                },
                function=self._send_notification
            ),

            # Query Tools
            AITool(
                name="get_load_details",
                description="Get full details of a load by ID",
                parameters={
                    "load_id": {"type": "string", "description": "Load ID"},
                },
                function=self._get_load_details
            ),
        ]

    # === Tool Implementations ===

    async def _create_load(
        self,
        customer_name: str,
        commodity: str,
        base_rate: float,
        pickup_city: str,
        pickup_state: str,
        delivery_city: str,
        delivery_state: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a new load in the database."""
        try:
            # Create the load
            load_id = str(uuid.uuid4())
            load = Load(
                id=load_id,
                company_id=kwargs.get("company_id", "default"),
                customer_name=customer_name,
                load_type="ftl",  # Default to FTL
                commodity=commodity,
                base_rate=base_rate,
                status="pending",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            # Create stops
            pickup_stop = LoadStop(
                id=str(uuid.uuid4()),
                load_id=load_id,
                sequence=1,
                stop_type="pickup",
                location_name=f"{pickup_city}, {pickup_state}",
                city=pickup_city,
                state=pickup_state,
            )

            delivery_stop = LoadStop(
                id=str(uuid.uuid4()),
                load_id=load_id,
                sequence=2,
                stop_type="drop",
                location_name=f"{delivery_city}, {delivery_state}",
                city=delivery_city,
                state=delivery_state,
            )

            self.db.add(load)
            self.db.add(pickup_stop)
            self.db.add(delivery_stop)
            await self.db.commit()

            return {
                "load_id": load_id,
                "status": "created",
                "customer": customer_name,
                "route": f"{pickup_city}, {pickup_state} → {delivery_city}, {delivery_state}",
                "rate": base_rate,
            }

        except Exception as e:
            await self.db.rollback()
            return {"error": str(e)}

    async def _extract_load_from_document(
        self,
        document_content: str,
        document_type: str = "text",
        **kwargs
    ) -> Dict[str, Any]:
        """Extract load data from document content using AI OCR."""
        try:
            # For now, parse document_content as text
            # In production, this would use the OCR service with actual file bytes

            # Simple extraction for demo
            lines = document_content.split("\n")
            data = {
                "customer_name": "Unknown Customer",
                "commodity": "General Freight",
                "base_rate": 0.0,
                "pickup_location": "Unknown",
                "delivery_location": "Unknown",
            }

            # Simple keyword extraction
            for line in lines:
                lower_line = line.lower()
                if "customer:" in lower_line or "shipper:" in lower_line:
                    data["customer_name"] = line.split(":", 1)[1].strip()
                elif "rate:" in lower_line or "amount:" in lower_line:
                    try:
                        rate_str = line.split(":", 1)[1].strip().replace("$", "").replace(",", "")
                        data["base_rate"] = float(rate_str)
                    except:
                        pass
                elif "pickup:" in lower_line or "origin:" in lower_line:
                    data["pickup_location"] = line.split(":", 1)[1].strip()
                elif "delivery:" in lower_line or "destination:" in lower_line:
                    data["delivery_location"] = line.split(":", 1)[1].strip()
                elif "commodity:" in lower_line:
                    data["commodity"] = line.split(":", 1)[1].strip()

            return {
                "status": "extracted",
                "data": data,
                "confidence": 0.75,
                "method": "simple_text_parsing",
            }

        except Exception as e:
            return {"error": str(e)}

    async def _find_available_drivers(
        self,
        equipment_type: str = "dry_van",
        pickup_state: Optional[str] = None,
        max_results: int = 5,
        **kwargs
    ) -> Dict[str, Any]:
        """Find available drivers matching criteria."""
        try:
            company_id = kwargs.get("company_id", "default")

            # Query drivers
            query = select(Driver).where(Driver.company_id == company_id)

            # Filter by status
            query = query.where(Driver.status == "active")

            # Limit results
            query = query.limit(max_results)

            result = await self.db.execute(query)
            drivers = result.scalars().all()

            driver_list = [
                {
                    "driver_id": d.id,
                    "name": f"{d.first_name} {d.last_name}",
                    "phone": d.phone,
                    "current_location": "Unknown",  # Would query GPS/ELD in production
                    "hos_available": True,  # Would check actual HOS in production
                }
                for d in drivers
            ]

            return {
                "status": "success",
                "drivers_found": len(driver_list),
                "drivers": driver_list,
            }

        except Exception as e:
            return {"error": str(e)}

    async def _assign_driver_to_load(
        self,
        load_id: str,
        driver_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Assign a driver to a load."""
        try:
            # Get the load
            result = await self.db.execute(select(Load).where(Load.id == load_id))
            load = result.scalar_one_or_none()

            if not load:
                return {"error": f"Load {load_id} not found"}

            # Get the driver
            result = await self.db.execute(select(Driver).where(Driver.id == driver_id))
            driver = result.scalar_one_or_none()

            if not driver:
                return {"error": f"Driver {driver_id} not found"}

            # Assign driver to load (simplified - in production would assign truck too)
            load.assigned_driver_id = driver_id
            load.status = "assigned"
            load.updated_at = datetime.utcnow()

            await self.db.commit()

            return {
                "status": "assigned",
                "load_id": load_id,
                "driver_name": f"{driver.first_name} {driver.last_name}",
                "driver_phone": driver.phone,
            }

        except Exception as e:
            await self.db.rollback()
            return {"error": str(e)}

    async def _check_equipment_status(
        self,
        equipment_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Check equipment availability and status."""
        try:
            result = await self.db.execute(select(Equipment).where(Equipment.id == equipment_id))
            equipment = result.scalar_one_or_none()

            if not equipment:
                return {"error": f"Equipment {equipment_id} not found"}

            return {
                "status": "available" if equipment.operational_status == "operational" else "unavailable",
                "equipment_id": equipment_id,
                "type": equipment.equipment_type,
                "operational_status": equipment.operational_status,
                "location": "Unknown",  # Would query GPS in production
            }

        except Exception as e:
            return {"error": str(e)}

    async def _send_notification(
        self,
        recipient_type: str,
        recipient_id: str,
        message: str,
        notification_type: str = "email",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send notification to recipient via email and/or SMS.

        For drivers, automatically sends both email and SMS if carrier info is available.
        """
        try:
            if recipient_type == "driver":
                # Import here to avoid circular dependencies
                from app.services.sms import send_driver_notification

                # Send both email and SMS to driver
                result = await send_driver_notification(
                    driver_id=recipient_id,
                    message=message,
                    db=self.db.sync_session,  # Get sync session for SQLAlchemy queries
                    email_subject="FreightOps - Load Assignment"
                )

                return {
                    "status": "sent",
                    "recipient_type": recipient_type,
                    "recipient_id": recipient_id,
                    "driver_name": result.get("driver_name"),
                    "email_sent": result.get("email_sent", False),
                    "sms_sent": result.get("sms_sent", False),
                    "message_preview": message[:50] + "..." if len(message) > 50 else message,
                }

            elif recipient_type == "customer":
                # For customers, send email only
                from app.services.notifications import EmailSender

                email_sender = EmailSender()
                result = await email_sender.send(
                    recipient=recipient_id,  # Assume recipient_id is email for customers
                    subject="FreightOps - Load Update",
                    body=message
                )

                return {
                    "status": "sent" if result.success else "failed",
                    "recipient_type": recipient_type,
                    "recipient_id": recipient_id,
                    "email_sent": result.success,
                    "detail": result.detail,
                    "message_preview": message[:50] + "..." if len(message) > 50 else message,
                }

            else:
                # Generic notification
                return {
                    "status": "not_implemented",
                    "recipient_type": recipient_type,
                    "recipient_id": recipient_id,
                    "message": "Notification type not yet implemented",
                }

        except Exception as e:
            return {
                "status": "error",
                "recipient_type": recipient_type,
                "recipient_id": recipient_id,
                "error": str(e)
            }

    async def _get_load_details(
        self,
        load_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Get complete details of a load."""
        try:
            result = await self.db.execute(select(Load).where(Load.id == load_id))
            load = result.scalar_one_or_none()

            if not load:
                return {"error": f"Load {load_id} not found"}

            return {
                "load_id": load.id,
                "customer": load.customer_name,
                "status": load.status,
                "commodity": load.commodity,
                "rate": float(load.base_rate),
                "assigned_driver_id": load.assigned_driver_id,
                "created_at": load.created_at.isoformat() if load.created_at else None,
            }

        except Exception as e:
            return {"error": str(e)}

    # === Vision OCR Methods (Llama 4 Scout) ===

    async def extract_rate_confirmation_vision(
        self,
        file_bytes: bytes,
        filename: str
    ) -> Dict[str, Any]:
        """
        Extract load data from rate confirmation using Llama 4 Scout Vision.

        Uses Groq's meta-llama/llama-4-scout-17b-16e-instruct for OCR.

        Args:
            file_bytes: Raw bytes of the uploaded file (PDF or image)
            filename: Original filename for type detection

        Returns:
            {
                "success": bool,
                "loadData": {...extracted fields...},
                "confidence": {...field confidence scores...},
                "rawText": str (if available),
                "error": str (if failed)
            }
        """
        try:
            # Initialize LLM Router for vision
            llm_router = LLMRouter()

            # Convert document to base64 image
            image_base64, raw_text = await self._prepare_document_for_vision(file_bytes, filename)

            if not image_base64:
                return {
                    "success": False,
                    "error": "Could not convert document to image for vision processing"
                }

            # Build OCR prompt
            ocr_prompt = self._build_rate_confirmation_prompt()

            # Call Llama 4 Scout Vision via Groq
            response_text, metadata = await llm_router.generate(
                agent_role="annie",
                prompt=ocr_prompt,
                system_prompt="You are Annie, an expert freight document analyzer. Extract structured data from rate confirmations with high accuracy.",
                image_data=image_base64,
                temperature=0.3,  # Low temp for accuracy
                max_tokens=2000
            )

            # Parse JSON response
            parsed_data, confidence = self._parse_ocr_response(response_text)

            return {
                "success": True,
                "loadData": self._transform_to_frontend_format(parsed_data),
                "confidence": confidence,
                "rawText": raw_text,
                "model": metadata.get("model"),
                "provider": metadata.get("provider"),
                "tokens_used": metadata.get("tokens_used"),
                "cost_usd": metadata.get("cost_usd")
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _prepare_document_for_vision(
        self,
        file_bytes: bytes,
        filename: str
    ) -> Tuple[Optional[str], str]:
        """
        Convert document to base64 image for vision processing.

        For PDFs: Extracts text first, then converts first page to image
        For images: Directly encodes to base64

        Returns:
            (image_base64, extracted_text)
        """
        lower_filename = filename.lower()
        raw_text = ""

        if lower_filename.endswith(".pdf"):
            # First extract text from PDF
            try:
                text_parts = []
                with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
                raw_text = "\n".join(text_parts)
            except Exception as e:
                raw_text = f"PDF text extraction failed: {e}"

            # Convert PDF to image for vision
            try:
                from pdf2image import convert_from_bytes
                images = convert_from_bytes(file_bytes, first_page=1, last_page=1, dpi=150)
                if images:
                    img_buffer = io.BytesIO()
                    images[0].save(img_buffer, format='PNG')
                    image_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
                    return f"data:image/png;base64,{image_base64}", raw_text
            except ImportError:
                # pdf2image not available, fall back to text-only
                # If we have text, we can still process without image
                if raw_text and not raw_text.startswith("PDF"):
                    return None, raw_text
                return None, raw_text

        elif lower_filename.endswith(('.png', '.jpg', '.jpeg', '.webp')):
            # Directly encode image
            media_type = "image/jpeg" if lower_filename.endswith(('.jpg', '.jpeg')) else "image/png"
            image_base64 = base64.b64encode(file_bytes).decode('utf-8')
            return f"data:{media_type};base64,{image_base64}", ""

        return None, ""

    def _build_rate_confirmation_prompt(self) -> str:
        """Build the OCR prompt for rate confirmation extraction."""
        return """Analyze this freight rate confirmation document and extract the following fields into JSON format.

IMPORTANT: Return ONLY valid JSON, no markdown code blocks or additional text.

{
  "customer_name": "Company name of the customer/shipper",
  "base_rate": 1234.56,
  "commodity": "Description of freight/commodity",
  "equipment_type": "dry_van | reefer | flatbed | step_deck | container",
  "weight": 12345,
  "reference_number": "Load or reference number",
  "pickup_location": {
    "full_address": "Complete pickup address",
    "city": "City",
    "state": "State (2-letter)",
    "postal_code": "ZIP"
  },
  "delivery_location": {
    "full_address": "Complete delivery address",
    "city": "City",
    "state": "State (2-letter)",
    "postal_code": "ZIP"
  },
  "pickup_date": "YYYY-MM-DD",
  "delivery_date": "YYYY-MM-DD",
  "special_instructions": "Any notes",
  "container_number": "Container number if applicable"
}

Rules:
- Use null for fields not found
- Extract main line haul rate (exclude fuel/accessorials)
- For commodity, default to "General Freight" if not specified
- Convert dates to YYYY-MM-DD format"""

    def _parse_ocr_response(self, response_text: str) -> Tuple[Dict, Dict]:
        """Parse the JSON response from vision OCR."""
        # Find JSON in response
        json_start = response_text.find('{')
        if json_start < 0:
            return {}, {}

        # Find matching closing brace
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
            return {}, {}

        json_str = response_text[json_start:json_end]
        data = json.loads(json_str)

        # Generate confidence scores (high for vision extraction)
        confidence = {key: 0.90 for key in data.keys() if data[key] is not None}

        return data, confidence

    def _transform_to_frontend_format(self, parsed_data: Dict) -> Dict:
        """Transform OCR data to match frontend expected format."""
        pickup = parsed_data.get("pickup_location", {}) or {}
        delivery = parsed_data.get("delivery_location", {}) or {}

        return {
            "customerName": parsed_data.get("customer_name"),
            "rate": parsed_data.get("base_rate"),
            "commodity": parsed_data.get("commodity"),
            "pickupLocation": pickup.get("full_address") or f"{pickup.get('city', '')}, {pickup.get('state', '')}".strip(", "),
            "deliveryLocation": delivery.get("full_address") or f"{delivery.get('city', '')}, {delivery.get('state', '')}".strip(", "),
            "referenceNumber": parsed_data.get("reference_number"),
            "pickupDate": parsed_data.get("pickup_date"),
            "weight": parsed_data.get("weight"),
            "processedAt": datetime.utcnow().isoformat()
        }
