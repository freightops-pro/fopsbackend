"""HQ Lead service for sales lead management."""

import json
import uuid
import aiohttp
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

# FMCSA Census Data - SoDA 2.1 API with SoQL
# Dataset: Company Census File (az4n-8mr2) - has add_date, power_units, etc.
# Docs: https://catalog.data.gov/dataset/motor-carrier-registrations-census-files
FMCSA_CENSUS_API = "https://data.transportation.gov/resource/az4n-8mr2.json"

from app.core.config import get_settings


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

        # Sales managers see their own leads + unassigned leads (for claiming)
        if current_user_role == HQRole.SALES_MANAGER:
            from sqlalchemy import or_
            query = query.where(
                or_(
                    HQLead.assigned_sales_rep_id == current_user_id,
                    HQLead.assigned_sales_rep_id.is_(None)  # Unassigned leads visible to all sales reps
                )
            )
        elif assigned_to_me:
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

    async def import_leads_from_fmcsa(
        self,
        state: Optional[str],
        min_trucks: int,
        max_trucks: int,
        limit: int,
        assign_to_sales_rep_id: Optional[str],
        created_by_id: str,
        auto_assign_round_robin: bool = False,
        authority_days: Optional[int] = None
    ) -> Tuple[List[HQLeadResponse], List[dict]]:
        """
        Import leads from FMCSA Motor Carrier Census data using Socrata SODA API.

        Args:
            state: Two-letter state code (e.g., "TX", "CA") or None for all states
            min_trucks: Minimum number of power units (trucks)
            max_trucks: Maximum number of power units
            limit: Maximum number of leads to import
            assign_to_sales_rep_id: Specific sales rep to assign all leads to
            created_by_id: User creating the leads
            auto_assign_round_robin: If True, distribute leads among sales reps
            authority_days: Only include carriers with authority granted in the last N days

        Returns:
            Tuple of (created_leads, errors)
        """
        # Build SoDA 2.1 API query using SoQL
        # Dataset fields: legal_name, dba_name, phy_street, phy_city, phy_state,
        #                 phy_zip, phone, dot_number, power_units, status_code, add_date
        settings = get_settings()

        # Build SoQL WHERE clause for Company Census File (az4n-8mr2)
        where_conditions = []

        # State filter (using phy_state - physical address state)
        if state:
            where_conditions.append(f"phy_state = '{state.upper()}'")

        # Active carriers only
        where_conditions.append("status_code = 'A'")

        # Authority age filter - add_date is in YYYYMMDD format
        if authority_days:
            from datetime import datetime, timedelta
            cutoff_date = (datetime.utcnow() - timedelta(days=authority_days)).strftime("%Y%m%d")
            where_conditions.append(f"add_date >= '{cutoff_date}'")

        # Build the SoQL WHERE clause
        # Note: power_units filtering is done client-side since SoQL doesn't support CAST
        # Request more records than limit to account for filtering
        query_limit = limit * 3 if (min_trucks or max_trucks) else limit
        where_clause = " AND ".join(where_conditions)

        # SoDA 2.1 uses URL query parameters
        import urllib.parse
        params = {
            "$where": where_clause,
            "$order": "add_date DESC",
            "$limit": str(query_limit),
        }
        query_string = urllib.parse.urlencode(params)
        full_url = f"{FMCSA_CENSUS_API}?{query_string}"

        try:
            # Build headers with app token for authentication (increases rate limit)
            headers = {"Accept": "application/json"}
            if settings.fmcsa_app_token:
                headers["X-App-Token"] = settings.fmcsa_app_token

            import logging
            logging.info(f"FMCSA API request: {full_url}")

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    full_url,
                    timeout=aiohttp.ClientTimeout(total=60),
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logging.error(f"FMCSA API error: {response.status} - {error_text[:500]}")
                        return [], [{"error": f"FMCSA API returned status {response.status}: {error_text[:500]}"}]
                    data = await response.json()

                    # SoDA 2.1 returns a list directly
                    if isinstance(data, list):
                        carriers = data
                    else:
                        carriers = []

                    logging.info(f"FMCSA API returned {len(carriers)} carriers for state {state}")
        except Exception as e:
            import traceback
            return [], [{"error": f"Failed to fetch FMCSA data: {str(e)}", "traceback": traceback.format_exc()}]

        if not carriers:
            return [], [{"error": f"No carriers found matching criteria. URL: {full_url}"}]

        # Client-side filtering for power_units (fleet size)
        # SoQL doesn't support CAST, so we filter here
        if min_trucks or max_trucks:
            filtered_carriers = []
            for c in carriers:
                try:
                    units = int(c.get("power_units", 0) or 0)
                except (ValueError, TypeError):
                    units = 0
                if min_trucks and units < min_trucks:
                    continue
                if max_trucks and units > max_trucks:
                    continue
                filtered_carriers.append(c)
            carriers = filtered_carriers[:limit]  # Apply original limit after filtering

        if not carriers:
            return [], [{"error": "No carriers found matching fleet size criteria"}]

        # Get sales reps for round-robin assignment if needed
        sales_reps = []
        if auto_assign_round_robin and not assign_to_sales_rep_id:
            result = await self.db.execute(
                select(HQEmployee)
                .where(HQEmployee.role == HQRole.SALES_MANAGER)
                .where(HQEmployee.is_active == True)
            )
            sales_reps = result.scalars().all()

        # Check for existing leads by company name to avoid duplicates
        existing_names = set()
        result = await self.db.execute(
            select(HQLead.company_name)
        )
        for row in result.scalars().all():
            if row:
                existing_names.add(row.lower().strip())

        created_leads = []
        errors = []
        rep_index = 0

        for idx, carrier in enumerate(carriers):
            try:
                # Socrata API returns lowercase field names
                def get_field(*names):
                    """Get first matching field from list of possible names."""
                    for name in names:
                        val = carrier.get(name.lower()) or carrier.get(name.upper())
                        if val:
                            return str(val).strip()
                    return None

                # Get company name (prefer DBA, fall back to legal name)
                company_name = get_field("dba_name") or get_field("legal_name")
                if not company_name:
                    continue

                # Skip if already exists (silently - don't count as error)
                if company_name.lower().strip() in existing_names:
                    continue

                # Determine assigned sales rep
                if assign_to_sales_rep_id:
                    rep_id = assign_to_sales_rep_id
                elif sales_reps:
                    rep_id = sales_reps[rep_index % len(sales_reps)].id
                    rep_index += 1
                else:
                    rep_id = created_by_id

                # Get power units (fleet size) from this dataset
                power_units_str = get_field("power_units") or "0"
                try:
                    power_units = int(power_units_str)
                except ValueError:
                    power_units = 0

                # Calculate estimated MRR based on fleet size
                if power_units <= 5:
                    estimated_mrr = Decimal("299")
                elif power_units <= 20:
                    estimated_mrr = Decimal("599")
                elif power_units <= 50:
                    estimated_mrr = Decimal("999")
                else:
                    estimated_mrr = Decimal("1499")

                # Build address for notes (Company Census File uses phy_ fields)
                address_parts = [
                    get_field("phy_street") or "",
                    get_field("phy_city") or "",
                    get_field("phy_state") or "",
                    get_field("phy_zip") or "",
                ]
                address = ", ".join(p for p in address_parts if p)

                # Get other fields from Company Census File dataset
                dot_number = get_field("dot_number") or ""
                mc_number = ""  # This dataset doesn't have MC number
                telephone = get_field("phone")
                email = get_field("email_address")  # This dataset has email!
                phy_state = get_field("phy_state") or ""

                # Get carrier operation type
                carrier_operation = get_field("carrier_operation") or "Motor Carrier"
                add_date = get_field("add_date") or ""

                # Create lead
                # Use None for system/background jobs (created_by_id is nullable)
                actual_created_by = None if created_by_id == "system" else created_by_id

                lead_number = await self._generate_lead_number()
                lead = HQLead(
                    id=str(uuid.uuid4()),
                    lead_number=lead_number,
                    company_name=company_name,
                    contact_name=None,  # FMCSA doesn't provide contact names
                    contact_email=email,
                    contact_phone=telephone,
                    contact_title=None,
                    source=LeadSource.FMCSA,
                    status=LeadStatus.NEW,
                    estimated_mrr=estimated_mrr,
                    estimated_trucks=str(power_units) if power_units else None,
                    estimated_drivers=None,
                    state=phy_state,
                    dot_number=dot_number,
                    mc_number=mc_number,
                    carrier_type=carrier_operation,
                    assigned_sales_rep_id=rep_id if rep_id != "system" else None,
                    notes=f"DOT#: {dot_number}\nFleet Size: {power_units} trucks\nAdded: {add_date}\nAddress: {address}\nSource: FMCSA Census",
                    created_by_id=actual_created_by,
                )

                self.db.add(lead)
                await self.db.flush()
                created_leads.append(lead.id)
                existing_names.add(company_name.lower().strip())

            except Exception as e:
                errors.append({"index": idx, "company": carrier.get("legal_name"), "error": str(e)})

        # Commit all leads
        await self.db.commit()

        # Fetch full lead responses
        lead_responses = []
        for lead_id in created_leads:
            lead_response = await self.get_lead(lead_id)
            if lead_response:
                lead_responses.append(lead_response)

        return lead_responses, errors

    async def enrich_lead_with_ai(
        self,
        lead_id: str,
    ) -> Optional[HQLeadResponse]:
        """
        Use AI to search for and enrich a lead with contact information.

        The AI will search for:
        - Owner/Decision maker names
        - Email addresses
        - Phone numbers
        - LinkedIn profiles
        - Additional company info

        Args:
            lead_id: ID of the lead to enrich

        Returns:
            Updated lead response or None if not found
        """
        # Get the lead
        result = await self.db.execute(
            select(HQLead).where(HQLead.id == lead_id)
        )
        lead = result.scalar_one_or_none()
        if not lead:
            return None

        llm = LLMRouter()

        system_prompt = """You are a business intelligence researcher specializing in the trucking and freight industry.

Your task is to find contact information for a trucking company. Search your knowledge for:
1. Owner/CEO/President name
2. Operations Manager or Fleet Manager name
3. Business email addresses
4. Business phone numbers
5. Any relevant LinkedIn profile URLs
6. Additional company details (years in business, specialties, etc.)

IMPORTANT:
- Only provide information you are confident about
- For trucking companies, look for DOT/MC registration info
- Check industry directories, LinkedIn, company websites
- If you cannot find specific contact info, indicate that
- Return ONLY valid JSON, no markdown or explanations

Return format (JSON object):
{
  "contact_name": "John Smith",
  "contact_title": "Owner",
  "contact_email": "john@company.com",
  "contact_phone": "555-123-4567",
  "linkedin_url": "https://linkedin.com/in/johnsmith",
  "additional_contacts": [
    {"name": "Jane Doe", "title": "Fleet Manager", "email": "jane@company.com"}
  ],
  "notes": "Founded in 2010, specializes in refrigerated freight. Active on LinkedIn.",
  "confidence": "high"
}

If no additional information found, return:
{
  "contact_name": null,
  "notes": "No additional contact information found",
  "confidence": "low"
}"""

        user_prompt = f"""Find contact information for this trucking company:

Company Name: {lead.company_name}
Current Phone: {lead.contact_phone or 'Unknown'}
Current Email: {lead.contact_email or 'Unknown'}
Location: Check notes below
Fleet Size: {lead.estimated_trucks or 'Unknown'} trucks
Notes: {lead.notes or 'None'}

Search for the owner, key decision makers, and their contact details."""

        try:
            response, metadata = await llm.generate(
                agent_role="alex",  # Sales and Analytics agent
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=2048
            )

            # Parse the JSON response
            response_text = response.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

            enrichment_data = json.loads(response_text)

            # Update lead with found information
            updated = False

            if enrichment_data.get("contact_name") and not lead.contact_name:
                lead.contact_name = enrichment_data["contact_name"]
                updated = True

            if enrichment_data.get("contact_title") and not lead.contact_title:
                lead.contact_title = enrichment_data["contact_title"]
                updated = True

            if enrichment_data.get("contact_email") and not lead.contact_email:
                lead.contact_email = enrichment_data["contact_email"]
                updated = True

            if enrichment_data.get("contact_phone") and not lead.contact_phone:
                lead.contact_phone = enrichment_data["contact_phone"]
                updated = True

            # Append enrichment notes
            enrichment_notes = []
            if enrichment_data.get("linkedin_url"):
                enrichment_notes.append(f"LinkedIn: {enrichment_data['linkedin_url']}")

            if enrichment_data.get("additional_contacts"):
                for contact in enrichment_data["additional_contacts"]:
                    enrichment_notes.append(
                        f"Alt Contact: {contact.get('name', 'N/A')} ({contact.get('title', 'N/A')}) - {contact.get('email', 'N/A')}"
                    )

            if enrichment_data.get("notes"):
                enrichment_notes.append(f"AI Notes: {enrichment_data['notes']}")

            if enrichment_notes:
                new_notes = "\n".join(enrichment_notes)
                if lead.notes:
                    lead.notes = f"{lead.notes}\n\n--- AI Enrichment ---\n{new_notes}"
                else:
                    lead.notes = f"--- AI Enrichment ---\n{new_notes}"
                updated = True

            if updated:
                await self.db.commit()

            return await self.get_lead(lead_id)

        except Exception as e:
            # Log error but don't fail - just return the lead as-is
            print(f"[Lead Enrichment] Failed to enrich lead {lead_id}: {str(e)}")
            return await self.get_lead(lead_id)

    async def enrich_leads_batch(
        self,
        lead_ids: List[str],
    ) -> Tuple[List[HQLeadResponse], List[dict]]:
        """
        Enrich multiple leads with AI-found contact information.

        Args:
            lead_ids: List of lead IDs to enrich

        Returns:
            Tuple of (enriched_leads, errors)
        """
        enriched_leads = []
        errors = []

        for lead_id in lead_ids:
            try:
                result = await self.enrich_lead_with_ai(lead_id)
                if result:
                    enriched_leads.append(result)
                else:
                    errors.append({"lead_id": lead_id, "error": "Lead not found"})
            except Exception as e:
                errors.append({"lead_id": lead_id, "error": str(e)})

        return enriched_leads, errors

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
            # FMCSA fields
            state=lead.state,
            dot_number=lead.dot_number,
            mc_number=lead.mc_number,
            carrier_type=lead.carrier_type,
            cargo_types=lead.cargo_types,
            created_by_id=lead.created_by_id,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
        )
