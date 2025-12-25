"""HQ Lead service for sales lead management."""

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.hq_lead import HQLead, LeadStatus, LeadSource
from app.models.hq_opportunity import HQOpportunity, OpportunityStage
from app.models.hq_employee import HQEmployee, HQRole
from app.schemas.hq import (
    HQLeadCreate, HQLeadUpdate, HQLeadResponse, HQLeadConvert,
    HQOpportunityResponse
)
from app.core.llm_router import LLMRouter


class HQLeadService:
    """Service for managing sales leads."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _generate_lead_number(self) -> str:
        """Generate unique lead number like LD-000001."""
        result = await self.db.execute(
            select(func.count(HQLead.id))
        )
        count = result.scalar() or 0
        return f"LD-{count + 1:06d}"

    async def get_leads(
        self,
        current_user_id: str,
        current_user_role: HQRole,
        status: Optional[str] = None,
        source: Optional[str] = None,
        assigned_to_me: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[HQLeadResponse]:
        """Get leads with optional filtering. Sales reps only see their own leads."""
        query = select(HQLead).options(
            selectinload(HQLead.assigned_sales_rep)
        )

        # Sales managers only see their own leads
        if current_user_role == HQRole.SALES_MANAGER or assigned_to_me:
            query = query.where(HQLead.assigned_sales_rep_id == current_user_id)

        if status:
            query = query.where(HQLead.status == status)
        if source:
            query = query.where(HQLead.source == source)

        query = query.order_by(HQLead.created_at.desc()).offset(offset).limit(limit)

        result = await self.db.execute(query)
        leads = result.scalars().all()

        return [self._to_response(lead) for lead in leads]

    async def get_lead(self, lead_id: str) -> Optional[HQLeadResponse]:
        """Get a single lead by ID."""
        result = await self.db.execute(
            select(HQLead)
            .options(selectinload(HQLead.assigned_sales_rep))
            .where(HQLead.id == lead_id)
        )
        lead = result.scalar_one_or_none()
        if not lead:
            return None
        return self._to_response(lead)

    async def create_lead(
        self,
        data: HQLeadCreate,
        created_by_id: str
    ) -> HQLeadResponse:
        """Create a new lead."""
        lead_number = await self._generate_lead_number()

        lead = HQLead(
            id=str(uuid.uuid4()),
            lead_number=lead_number,
            company_name=data.company_name,
            contact_name=data.contact_name,
            contact_email=data.contact_email,
            contact_phone=data.contact_phone,
            contact_title=data.contact_title,
            source=LeadSource(data.source) if data.source else LeadSource.OTHER,
            status=LeadStatus.NEW,
            estimated_mrr=data.estimated_mrr,
            estimated_trucks=data.estimated_trucks,
            estimated_drivers=data.estimated_drivers,
            assigned_sales_rep_id=data.assigned_sales_rep_id or created_by_id,
            next_follow_up_date=data.next_follow_up_date,
            notes=data.notes,
            created_by_id=created_by_id,
        )

        self.db.add(lead)
        await self.db.commit()
        await self.db.refresh(lead)

        # Reload with relationships
        return await self.get_lead(lead.id)

    async def update_lead(
        self,
        lead_id: str,
        data: HQLeadUpdate
    ) -> Optional[HQLeadResponse]:
        """Update an existing lead."""
        result = await self.db.execute(
            select(HQLead).where(HQLead.id == lead_id)
        )
        lead = result.scalar_one_or_none()
        if not lead:
            return None

        update_data = data.model_dump(exclude_unset=True, by_alias=False)
        for field, value in update_data.items():
            if field == "status" and value:
                setattr(lead, field, LeadStatus(value))
            elif field == "source" and value:
                setattr(lead, field, LeadSource(value))
            else:
                setattr(lead, field, value)

        # Update last_contacted_at if status changed to contacted
        if data.status == "contacted":
            lead.last_contacted_at = datetime.utcnow()

        await self.db.commit()
        return await self.get_lead(lead_id)

    async def convert_to_opportunity(
        self,
        lead_id: str,
        data: HQLeadConvert,
        converted_by_id: str
    ) -> Optional[HQOpportunityResponse]:
        """Convert a lead to an opportunity."""
        result = await self.db.execute(
            select(HQLead).where(HQLead.id == lead_id)
        )
        lead = result.scalar_one_or_none()
        if not lead:
            return None

        if lead.status == LeadStatus.CONVERTED:
            raise ValueError("Lead has already been converted")

        # Generate opportunity number
        opp_count = await self.db.execute(select(func.count(HQOpportunity.id)))
        opp_number = f"OPP-{(opp_count.scalar() or 0) + 1:06d}"

        # Create opportunity from lead
        opportunity = HQOpportunity(
            id=str(uuid.uuid4()),
            opportunity_number=opp_number,
            lead_id=lead.id,
            company_name=lead.company_name,
            contact_name=lead.contact_name,
            contact_email=lead.contact_email,
            contact_phone=lead.contact_phone,
            title=data.title,
            stage=OpportunityStage.DISCOVERY,
            probability=Decimal("20"),
            estimated_mrr=data.estimated_mrr,
            estimated_trucks=lead.estimated_trucks,
            estimated_close_date=data.estimated_close_date,
            assigned_sales_rep_id=lead.assigned_sales_rep_id,
            notes=lead.notes,
            created_by_id=converted_by_id,
        )

        self.db.add(opportunity)

        # Update lead status
        lead.status = LeadStatus.CONVERTED
        lead.converted_to_opportunity_id = opportunity.id
        lead.converted_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(opportunity)

        # Return opportunity response
        return await self._get_opportunity_response(opportunity.id)

    async def _get_opportunity_response(self, opportunity_id: str) -> HQOpportunityResponse:
        """Get opportunity response with relationships."""
        result = await self.db.execute(
            select(HQOpportunity)
            .options(selectinload(HQOpportunity.assigned_sales_rep))
            .where(HQOpportunity.id == opportunity_id)
        )
        opp = result.scalar_one()
        return HQOpportunityResponse(
            id=opp.id,
            opportunity_number=opp.opportunity_number,
            lead_id=opp.lead_id,
            tenant_id=opp.tenant_id,
            company_name=opp.company_name,
            contact_name=opp.contact_name,
            contact_email=opp.contact_email,
            contact_phone=opp.contact_phone,
            title=opp.title,
            description=opp.description,
            stage=opp.stage.value,
            probability=opp.probability,
            estimated_mrr=opp.estimated_mrr,
            estimated_setup_fee=opp.estimated_setup_fee,
            estimated_trucks=opp.estimated_trucks,
            estimated_close_date=opp.estimated_close_date,
            actual_close_date=opp.actual_close_date,
            assigned_sales_rep_id=opp.assigned_sales_rep_id,
            assigned_sales_rep_name=f"{opp.assigned_sales_rep.first_name} {opp.assigned_sales_rep.last_name}" if opp.assigned_sales_rep else None,
            converted_to_quote_id=opp.converted_to_quote_id,
            converted_at=opp.converted_at,
            lost_reason=opp.lost_reason,
            competitor=opp.competitor,
            notes=opp.notes,
            created_by_id=opp.created_by_id,
            created_at=opp.created_at,
            updated_at=opp.updated_at,
        )

    async def import_leads_from_content(
        self,
        content: str,
        content_type: str,  # "csv", "email", "spreadsheet", "text"
        assign_to_sales_rep_id: Optional[str],
        created_by_id: str,
        auto_assign_round_robin: bool = False
    ) -> Tuple[List[HQLeadResponse], List[dict]]:
        """
        Use AI to parse content and create leads automatically.

        Args:
            content: Raw content (CSV data, email text, or any unstructured text)
            content_type: Type of content being parsed
            assign_to_sales_rep_id: Specific sales rep to assign all leads to
            created_by_id: User creating the leads
            auto_assign_round_robin: If True and no specific rep, distribute evenly

        Returns:
            Tuple of (created_leads, errors)
        """
        llm = LLMRouter()

        system_prompt = """You are a lead data extraction specialist for a freight/trucking TMS (Transportation Management System) software company.

Your job is to analyze the provided content and extract potential sales leads (trucking companies, freight carriers, logistics companies).

For each lead found, extract:
- company_name (REQUIRED): The company/business name
- contact_name: Contact person's full name
- contact_email: Email address
- contact_phone: Phone number (any format)
- contact_title: Job title (e.g., Owner, Fleet Manager, Operations Manager)
- source: One of: referral, website, cold_call, partner, trade_show, linkedin, other
- estimated_trucks: Estimated fleet size (just the number or range like "10-25")
- estimated_mrr: Estimated monthly subscription value in dollars (your best guess based on fleet size: small=299, medium=599, large=999)
- notes: Any relevant notes about the company

IMPORTANT:
- Only extract trucking/freight/logistics related companies
- For emails, look for signature blocks, company mentions, fleet information
- For CSV/spreadsheet data, map columns intelligently
- If you're not sure about a value, omit it rather than guess
- Return ONLY valid JSON, no markdown or explanations

Return format (JSON array):
[
  {
    "company_name": "ABC Trucking",
    "contact_name": "John Smith",
    "contact_email": "john@abctrucking.com",
    "contact_phone": "555-123-4567",
    "contact_title": "Owner",
    "source": "referral",
    "estimated_trucks": "15",
    "estimated_mrr": 599,
    "notes": "Interested in ELD compliance features"
  }
]

If no valid leads are found, return an empty array: []"""

        user_prompt = f"""Content Type: {content_type}

Content to parse:
---
{content}
---

Extract all sales leads from this content and return as JSON array."""

        try:
            response, metadata = await llm.generate(
                agent_role="alex",  # Sales and Analytics agent
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.3,  # Lower temperature for structured extraction
                max_tokens=4096
            )

            # Parse the JSON response
            # Handle potential markdown code blocks
            response_text = response.strip()
            if response_text.startswith("```"):
                # Remove markdown code block
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

            parsed_leads = json.loads(response_text)

        except json.JSONDecodeError as e:
            return [], [{"error": f"Failed to parse AI response as JSON: {str(e)}", "raw_response": response[:500]}]
        except Exception as e:
            return [], [{"error": f"AI processing failed: {str(e)}"}]

        if not isinstance(parsed_leads, list):
            return [], [{"error": "AI response was not a list of leads"}]

        # Get sales reps for round-robin assignment if needed
        sales_reps = []
        if auto_assign_round_robin and not assign_to_sales_rep_id:
            result = await self.db.execute(
                select(HQEmployee)
                .where(HQEmployee.role == HQRole.SALES_MANAGER)
                .where(HQEmployee.is_active == True)
            )
            sales_reps = result.scalars().all()

        created_leads = []
        errors = []
        rep_index = 0

        for idx, lead_data in enumerate(parsed_leads):
            try:
                # Validate required field
                if not lead_data.get("company_name"):
                    errors.append({"index": idx, "error": "Missing company_name"})
                    continue

                # Determine assigned sales rep
                if assign_to_sales_rep_id:
                    rep_id = assign_to_sales_rep_id
                elif sales_reps:
                    rep_id = sales_reps[rep_index % len(sales_reps)].id
                    rep_index += 1
                else:
                    rep_id = created_by_id

                # Map source
                source_map = {
                    "referral": LeadSource.REFERRAL,
                    "website": LeadSource.WEBSITE,
                    "cold_call": LeadSource.COLD_CALL,
                    "partner": LeadSource.PARTNER,
                    "trade_show": LeadSource.TRADE_SHOW,
                    "linkedin": LeadSource.LINKEDIN,
                    "other": LeadSource.OTHER,
                }
                source = source_map.get(lead_data.get("source", "other"), LeadSource.OTHER)

                # Create lead
                lead_number = await self._generate_lead_number()
                lead = HQLead(
                    id=str(uuid.uuid4()),
                    lead_number=lead_number,
                    company_name=lead_data["company_name"],
                    contact_name=lead_data.get("contact_name"),
                    contact_email=lead_data.get("contact_email"),
                    contact_phone=lead_data.get("contact_phone"),
                    contact_title=lead_data.get("contact_title"),
                    source=source,
                    status=LeadStatus.NEW,
                    estimated_mrr=Decimal(str(lead_data.get("estimated_mrr", 0))) if lead_data.get("estimated_mrr") else None,
                    estimated_trucks=str(lead_data.get("estimated_trucks")) if lead_data.get("estimated_trucks") else None,
                    assigned_sales_rep_id=rep_id,
                    notes=lead_data.get("notes"),
                    created_by_id=created_by_id,
                )

                self.db.add(lead)
                await self.db.flush()  # Get the ID

                # Add to results (will fetch full response after commit)
                created_leads.append(lead.id)

            except Exception as e:
                errors.append({"index": idx, "company": lead_data.get("company_name"), "error": str(e)})

        # Commit all leads
        await self.db.commit()

        # Fetch full lead responses
        lead_responses = []
        for lead_id in created_leads:
            lead_response = await self.get_lead(lead_id)
            if lead_response:
                lead_responses.append(lead_response)

        return lead_responses, errors

    def _to_response(self, lead: HQLead) -> HQLeadResponse:
        """Convert lead model to response schema."""
        return HQLeadResponse(
            id=lead.id,
            lead_number=lead.lead_number,
            company_name=lead.company_name,
            contact_name=lead.contact_name,
            contact_email=lead.contact_email,
            contact_phone=lead.contact_phone,
            contact_title=lead.contact_title,
            source=lead.source.value if lead.source else "other",
            status=lead.status.value if lead.status else "new",
            estimated_mrr=lead.estimated_mrr,
            estimated_trucks=lead.estimated_trucks,
            estimated_drivers=lead.estimated_drivers,
            assigned_sales_rep_id=lead.assigned_sales_rep_id,
            assigned_sales_rep_name=f"{lead.assigned_sales_rep.first_name} {lead.assigned_sales_rep.last_name}" if lead.assigned_sales_rep else None,
            next_follow_up_date=lead.next_follow_up_date,
            last_contacted_at=lead.last_contacted_at,
            converted_to_opportunity_id=lead.converted_to_opportunity_id,
            converted_at=lead.converted_at,
            notes=lead.notes,
            created_by_id=lead.created_by_id,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
        )
