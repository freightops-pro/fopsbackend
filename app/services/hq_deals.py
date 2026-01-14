"""HQ Deals service for unified sales pipeline management."""

import json
import uuid
import aiohttp
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple, Dict, Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.hq_deal import HQDeal, HQDealActivity, DealStage, DealSource
from app.models.hq_employee import HQEmployee, HQRole
from app.core.llm_router import LLMRouter

# FMCSA Census Data - SoDA 2.1 API
FMCSA_CENSUS_API = "https://data.transportation.gov/resource/az4n-8mr2.json"

from app.core.config import get_settings


# Stage probability mappings
STAGE_PROBABILITY = {
    DealStage.LEAD: Decimal("10"),
    DealStage.CONTACTED: Decimal("20"),
    DealStage.QUALIFIED: Decimal("40"),
    DealStage.DEMO: Decimal("60"),
    DealStage.CLOSING: Decimal("80"),
    DealStage.WON: Decimal("100"),
    DealStage.LOST: Decimal("0"),
}


class HQDealsService:
    """Service for managing the unified deals pipeline."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _generate_deal_number(self) -> str:
        """Generate unique deal number like DL-000001."""
        result = await self.db.execute(
            select(func.count(HQDeal.id))
        )
        count = result.scalar() or 0
        return f"DL-{count + 1:06d}"

    async def get_deals(
        self,
        current_user_id: str,
        current_user_role: HQRole,
        stage: Optional[str] = None,
        source: Optional[str] = None,
        assigned_to_me: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get deals with optional filtering. Sales reps only see their own deals."""
        query = select(HQDeal).options(
            selectinload(HQDeal.assigned_sales_rep),
            selectinload(HQDeal.subscription)
        )

        # Sales managers only see their own deals
        if current_user_role == HQRole.SALES_MANAGER or assigned_to_me:
            query = query.where(HQDeal.assigned_sales_rep_id == current_user_id)

        if stage:
            query = query.where(HQDeal.stage == stage)
        if source:
            query = query.where(HQDeal.source == source)

        query = query.order_by(HQDeal.created_at.desc()).offset(offset).limit(limit)

        result = await self.db.execute(query)
        deals = result.scalars().all()

        return [self._to_response(deal) for deal in deals]

    async def get_deal(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Get a single deal by ID."""
        result = await self.db.execute(
            select(HQDeal)
            .options(
                selectinload(HQDeal.assigned_sales_rep),
                selectinload(HQDeal.subscription)
            )
            .where(HQDeal.id == deal_id)
        )
        deal = result.scalar_one_or_none()
        if not deal:
            return None
        return self._to_response(deal)

    async def create_deal(
        self,
        data: Dict[str, Any],
        created_by_id: str
    ) -> Dict[str, Any]:
        """Create a new deal."""
        deal_number = await self._generate_deal_number()

        # Map source
        source = DealSource.OTHER
        if data.get("source"):
            try:
                source = DealSource(data["source"])
            except ValueError:
                source = DealSource.OTHER

        deal = HQDeal(
            id=str(uuid.uuid4()),
            deal_number=deal_number,
            company_name=data["company_name"],
            contact_name=data.get("contact_name"),
            contact_email=data.get("contact_email"),
            contact_phone=data.get("contact_phone"),
            contact_title=data.get("contact_title"),
            source=source,
            stage=DealStage.LEAD,
            probability=STAGE_PROBABILITY[DealStage.LEAD],
            estimated_mrr=Decimal(str(data.get("estimated_mrr", 0))) if data.get("estimated_mrr") else None,
            estimated_setup_fee=Decimal(str(data.get("estimated_setup_fee", 0))) if data.get("estimated_setup_fee") else None,
            estimated_trucks=data.get("estimated_trucks"),
            estimated_close_date=data.get("estimated_close_date"),
            assigned_sales_rep_id=data.get("assigned_sales_rep_id") or created_by_id,
            next_follow_up_date=data.get("next_follow_up_date"),
            dot_number=data.get("dot_number"),
            mc_number=data.get("mc_number"),
            state=data.get("state"),
            notes=data.get("notes"),
            created_by_id=created_by_id,
        )

        self.db.add(deal)
        await self.db.commit()
        await self.db.refresh(deal)

        # Log creation activity
        await self._log_activity(
            deal.id,
            "created",
            f"Deal created for {deal.company_name}",
            created_by_id
        )

        return await self.get_deal(deal.id)

    async def update_deal(
        self,
        deal_id: str,
        data: Dict[str, Any],
        updated_by_id: str
    ) -> Optional[Dict[str, Any]]:
        """Update an existing deal."""
        result = await self.db.execute(
            select(HQDeal).where(HQDeal.id == deal_id)
        )
        deal = result.scalar_one_or_none()
        if not deal:
            return None

        old_stage = deal.stage

        # Update fields
        for field in ["company_name", "contact_name", "contact_email", "contact_phone",
                      "contact_title", "estimated_trucks", "estimated_close_date",
                      "next_follow_up_date", "dot_number", "mc_number", "state",
                      "notes", "lost_reason", "competitor", "assigned_sales_rep_id"]:
            if field in data:
                setattr(deal, field, data[field])

        # Handle numeric fields
        if "estimated_mrr" in data:
            deal.estimated_mrr = Decimal(str(data["estimated_mrr"])) if data["estimated_mrr"] else None
        if "estimated_setup_fee" in data:
            deal.estimated_setup_fee = Decimal(str(data["estimated_setup_fee"])) if data["estimated_setup_fee"] else None
        if "probability" in data:
            deal.probability = Decimal(str(data["probability"]))

        # Handle stage change
        if "stage" in data and data["stage"]:
            new_stage = DealStage(data["stage"])
            if new_stage != old_stage:
                deal.stage = new_stage
                deal.probability = STAGE_PROBABILITY.get(new_stage, deal.probability)

                # Track outcome timestamps
                if new_stage == DealStage.WON:
                    deal.won_at = datetime.utcnow()
                elif new_stage == DealStage.LOST:
                    deal.lost_at = datetime.utcnow()

                # Log stage change
                await self._log_activity(
                    deal.id,
                    "stage_change",
                    f"Stage changed from {old_stage.value} to {new_stage.value}",
                    updated_by_id,
                    from_stage=old_stage.value,
                    to_stage=new_stage.value
                )

        # Handle source
        if "source" in data and data["source"]:
            try:
                deal.source = DealSource(data["source"])
            except ValueError:
                pass

        # Update last_contacted_at if stage changed to contacted
        if data.get("stage") == "contacted":
            deal.last_contacted_at = datetime.utcnow()

        await self.db.commit()
        return await self.get_deal(deal_id)

    async def delete_deal(self, deal_id: str) -> bool:
        """Delete a deal."""
        result = await self.db.execute(
            select(HQDeal).where(HQDeal.id == deal_id)
        )
        deal = result.scalar_one_or_none()
        if not deal:
            return False

        await self.db.delete(deal)
        await self.db.commit()
        return True

    async def win_deal(
        self,
        deal_id: str,
        billing_interval: str,
        monthly_rate: Decimal,
        setup_fee: Optional[Decimal],
        created_by_id: str
    ) -> Optional[Dict[str, Any]]:
        """Win a deal and create a subscription for it."""
        from app.services.hq_subscriptions import HQSubscriptionsService
        from app.models.hq_tenant import HQTenant

        # Get the deal
        result = await self.db.execute(
            select(HQDeal).where(HQDeal.id == deal_id)
        )
        deal = result.scalar_one_or_none()
        if not deal:
            return None

        # Create tenant if DOT number exists and tenant doesn't exist
        tenant_id = None
        if deal.dot_number:
            # Check if tenant with this DOT exists
            tenant_result = await self.db.execute(
                select(HQTenant).where(HQTenant.dot_number == deal.dot_number)
            )
            tenant = tenant_result.scalar_one_or_none()
            if tenant:
                tenant_id = tenant.id

        # For now, we require a tenant_id to create a subscription
        # In a full implementation, we'd create the tenant here
        if not tenant_id:
            # Mark deal as won without creating subscription
            deal.stage = DealStage.WON
            deal.won_at = datetime.utcnow()
            deal.probability = STAGE_PROBABILITY[DealStage.WON]
            await self._log_activity(
                deal.id,
                "deal_won",
                f"Deal won - subscription creation pending (no tenant)",
                created_by_id
            )
            await self.db.commit()
            return self._to_response(deal)

        # Create subscription
        subscription_service = HQSubscriptionsService(self.db)
        subscription_data = {
            "tenant_id": tenant_id,
            "deal_id": deal_id,
            "billing_interval": billing_interval,
            "monthly_rate": float(monthly_rate),
            "setup_fee": float(setup_fee) if setup_fee else 0,
        }
        subscription = await subscription_service.create_subscription(
            subscription_data,
            created_by_id
        )

        # Update deal to won
        deal.stage = DealStage.WON
        deal.won_at = datetime.utcnow()
        deal.probability = STAGE_PROBABILITY[DealStage.WON]

        # Log activity
        await self._log_activity(
            deal.id,
            "deal_won",
            f"Deal won - subscription {subscription['subscriptionNumber']} created",
            created_by_id
        )

        await self.db.commit()
        return self._to_response(deal)

    async def get_pipeline_summary(
        self,
        current_user_id: str,
        current_user_role: HQRole
    ) -> List[Dict[str, Any]]:
        """Get summary of deals by stage for pipeline view."""
        # Build base query
        base_conditions = []
        if current_user_role == HQRole.SALES_MANAGER:
            base_conditions.append(HQDeal.assigned_sales_rep_id == current_user_id)

        summary = []
        for stage in DealStage:
            conditions = base_conditions + [HQDeal.stage == stage]

            # Count
            count_result = await self.db.execute(
                select(func.count(HQDeal.id)).where(and_(*conditions) if conditions else True)
            )
            count = count_result.scalar() or 0

            # Total value
            value_result = await self.db.execute(
                select(func.coalesce(func.sum(HQDeal.estimated_mrr), 0)).where(and_(*conditions) if conditions else True)
            )
            total_value = float(value_result.scalar() or 0)

            # Weighted value (value * probability)
            weighted_result = await self.db.execute(
                select(func.coalesce(func.sum(HQDeal.estimated_mrr * HQDeal.probability / 100), 0))
                .where(and_(*conditions) if conditions else True)
            )
            weighted_value = float(weighted_result.scalar() or 0)

            summary.append({
                "stage": stage.value,
                "count": count,
                "totalValue": total_value,
                "weightedValue": weighted_value
            })

        return summary

    async def import_deals_from_fmcsa(
        self,
        state: Optional[str],
        min_trucks: int,
        max_trucks: int,
        limit: int,
        assign_to_sales_rep_id: Optional[str],
        created_by_id: str,
        auto_assign_round_robin: bool = False,
        authority_days: Optional[int] = None
    ) -> Tuple[List[Dict[str, Any]], List[dict]]:
        """Import deals from FMCSA Motor Carrier Census data."""
        settings = get_settings()

        # Build SoDA 2.1 API query
        where_conditions = []

        if state:
            where_conditions.append(f"phy_state = '{state.upper()}'")

        # Active carriers only
        where_conditions.append("status_code = 'A'")

        # Filter for actual motor carriers (not shippers or registrants)
        # entity_type field: C = Carrier, S = Shipper, B = Both, R = Registrant
        where_conditions.append("entity_type IN ('C', 'B')")

        # Filter for authorized for-hire carriers (not private/exempt)
        # carrier_operation: A = Authorized For Hire, B = Exempt For Hire, C = Private Property
        where_conditions.append("carrier_operation = 'A'")

        # Ensure they have actual power units (trucks)
        where_conditions.append("power_units > 0")

        # Authority age filter
        if authority_days:
            from datetime import timedelta
            cutoff_date = (datetime.utcnow() - timedelta(days=authority_days)).strftime("%Y%m%d")
            where_conditions.append(f"add_date >= '{cutoff_date}'")

        # Build query
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
            headers = {"Accept": "application/json"}
            if settings.fmcsa_app_token:
                headers["X-App-Token"] = settings.fmcsa_app_token

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    full_url,
                    timeout=aiohttp.ClientTimeout(total=60),
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return [], [{"error": f"FMCSA API returned status {response.status}: {error_text[:500]}"}]
                    data = await response.json()

                    # SoDA 2.1 returns a list directly
                    if isinstance(data, list):
                        carriers = data
                    else:
                        carriers = []

        except Exception as e:
            import traceback
            return [], [{"error": f"Failed to fetch FMCSA data: {str(e)}", "traceback": traceback.format_exc()}]

        if not carriers:
            return [], [{"error": f"No carriers found matching criteria. URL: {full_url}"}]

        # Client-side filtering for power_units
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
            carriers = filtered_carriers[:limit]

        if not carriers:
            return [], [{"error": "No carriers found matching fleet size criteria"}]

        # Get sales reps for round-robin
        sales_reps = []
        if auto_assign_round_robin and not assign_to_sales_rep_id:
            result = await self.db.execute(
                select(HQEmployee)
                .where(HQEmployee.role == HQRole.SALES_MANAGER)
                .where(HQEmployee.is_active == True)
            )
            sales_reps = result.scalars().all()

        # Master Spec: Enhanced de-duplication by DOT number and company name
        # Check both existing deals AND existing tenants to prevent duplicates
        existing_names = set()
        existing_dots = set()

        # Check existing deals
        result = await self.db.execute(
            select(HQDeal.company_name, HQDeal.dot_number)
        )
        for name, dot in result.all():
            if name:
                existing_names.add(name.lower().strip())
            if dot:
                existing_dots.add(dot.strip())

        # Check existing tenants (already customers)
        from app.models import HQTenant, Company
        result = await self.db.execute(
            select(Company.name, Company.dot_number)
            .join(HQTenant, Company.id == HQTenant.company_id)
        )
        for name, dot in result.all():
            if name:
                existing_names.add(name.lower().strip())
            if dot:
                existing_dots.add(dot.strip())

        created_deals = []
        errors = []
        rep_index = 0

        for idx, carrier in enumerate(carriers):
            try:
                def get_field(*names):
                    for name in names:
                        val = carrier.get(name.lower()) or carrier.get(name.upper())
                        if val:
                            return str(val).strip()
                    return None

                company_name = get_field("dba_name") or get_field("legal_name")
                if not company_name:
                    continue

                # Master Spec: Check for duplicates by company name
                if company_name.lower().strip() in existing_names:
                    continue

                # Master Spec: Check for duplicates by DOT number (more reliable than name)
                dot_number = get_field("dot_number", "usdot_number")
                if dot_number and dot_number.strip() in existing_dots:
                    # Skip this carrier - they already exist as a deal or tenant
                    errors.append({
                        "company": company_name,
                        "dot": dot_number,
                        "reason": "Duplicate DOT number - already exists in system"
                    })
                    continue

                # Determine assigned sales rep
                if assign_to_sales_rep_id:
                    rep_id = assign_to_sales_rep_id
                elif sales_reps:
                    rep_id = sales_reps[rep_index % len(sales_reps)].id
                    rep_index += 1
                else:
                    rep_id = created_by_id if created_by_id != "system" else None

                # Get power units
                power_units_str = get_field("power_units") or "0"
                try:
                    power_units = int(power_units_str)
                except ValueError:
                    power_units = 0

                # Calculate estimated MRR
                if power_units <= 5:
                    estimated_mrr = Decimal("299")
                elif power_units <= 20:
                    estimated_mrr = Decimal("599")
                elif power_units <= 50:
                    estimated_mrr = Decimal("999")
                else:
                    estimated_mrr = Decimal("1499")

                # Build address for notes
                address_parts = [
                    get_field("phy_street") or "",
                    get_field("phy_city") or "",
                    get_field("phy_state") or "",
                    get_field("phy_zip") or "",
                ]
                address = ", ".join(p for p in address_parts if p)

                # Already extracted dot_number earlier for de-duplication check
                telephone = get_field("phone")
                email = get_field("email_address")
                phy_state = get_field("phy_state") or ""
                carrier_operation = get_field("carrier_operation") or "Motor Carrier"
                add_date = get_field("add_date") or ""

                # Create deal
                actual_created_by = None if created_by_id == "system" else created_by_id

                deal_number = await self._generate_deal_number()
                deal = HQDeal(
                    id=str(uuid.uuid4()),
                    deal_number=deal_number,
                    company_name=company_name,
                    contact_name=None,
                    contact_email=email,
                    contact_phone=telephone,
                    contact_title=None,
                    source=DealSource.FMCSA,
                    stage=DealStage.LEAD,
                    probability=STAGE_PROBABILITY[DealStage.LEAD],
                    estimated_mrr=estimated_mrr,
                    estimated_trucks=str(power_units) if power_units else None,
                    state=phy_state,
                    dot_number=dot_number,
                    carrier_type=carrier_operation,
                    assigned_sales_rep_id=rep_id if rep_id and rep_id != "system" else None,
                    notes=f"DOT#: {dot_number}\nFleet Size: {power_units} trucks\nAdded: {add_date}\nAddress: {address}\nSource: FMCSA Census",
                    created_by_id=actual_created_by,
                )

                self.db.add(deal)
                await self.db.flush()
                created_deals.append(deal.id)
                existing_names.add(company_name.lower().strip())

            except Exception as e:
                errors.append({"index": idx, "company": carrier.get("legal_name"), "error": str(e)})

        await self.db.commit()

        # Fetch full deal responses
        deal_responses = []
        for deal_id in created_deals:
            deal_response = await self.get_deal(deal_id)
            if deal_response:
                deal_responses.append(deal_response)

        return deal_responses, errors

    async def import_deals_from_content(
        self,
        content: str,
        content_type: str,
        assign_to_sales_rep_id: Optional[str],
        created_by_id: str,
        auto_assign_round_robin: bool = False
    ) -> Tuple[List[Dict[str, Any]], List[dict]]:
        """Use AI to parse content and create deals automatically."""
        llm = LLMRouter()

        system_prompt = """You are a lead data extraction specialist for a freight/trucking TMS software company.

Your job is to analyze the provided content and extract potential sales leads (trucking companies, freight carriers, logistics companies).

For each lead found, extract:
- company_name (REQUIRED): The company/business name
- contact_name: Contact person's full name
- contact_email: Email address
- contact_phone: Phone number (any format)
- contact_title: Job title (e.g., Owner, Fleet Manager)
- source: One of: referral, website, cold_call, partner, trade_show, linkedin, other
- estimated_trucks: Estimated fleet size (just the number or range like "10-25")
- estimated_mrr: Estimated monthly subscription value in dollars
- notes: Any relevant notes about the company

Return ONLY valid JSON array, no markdown:
[
  {
    "company_name": "ABC Trucking",
    "contact_name": "John Smith",
    "contact_email": "john@abctrucking.com",
    "estimated_trucks": "15",
    "estimated_mrr": 599
  }
]"""

        user_prompt = f"""Content Type: {content_type}

Content to parse:
---
{content}
---

Extract all sales leads from this content and return as JSON array."""

        try:
            response, metadata = await llm.generate(
                agent_role="alex",
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=4096
            )

            response_text = response.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

            parsed_leads = json.loads(response_text)

        except json.JSONDecodeError as e:
            return [], [{"error": f"Failed to parse AI response as JSON: {str(e)}"}]
        except Exception as e:
            return [], [{"error": f"AI processing failed: {str(e)}"}]

        if not isinstance(parsed_leads, list):
            return [], [{"error": "AI response was not a list of leads"}]

        # Get sales reps for round-robin
        sales_reps = []
        if auto_assign_round_robin and not assign_to_sales_rep_id:
            result = await self.db.execute(
                select(HQEmployee)
                .where(HQEmployee.role == HQRole.SALES_MANAGER)
                .where(HQEmployee.is_active == True)
            )
            sales_reps = result.scalars().all()

        created_deals = []
        errors = []
        rep_index = 0

        for idx, lead_data in enumerate(parsed_leads):
            try:
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
                    "referral": DealSource.REFERRAL,
                    "website": DealSource.WEBSITE,
                    "cold_call": DealSource.COLD_CALL,
                    "partner": DealSource.PARTNER,
                    "trade_show": DealSource.TRADE_SHOW,
                    "linkedin": DealSource.LINKEDIN,
                    "other": DealSource.OTHER,
                }
                source = source_map.get(lead_data.get("source", "other"), DealSource.OTHER)

                deal_number = await self._generate_deal_number()
                deal = HQDeal(
                    id=str(uuid.uuid4()),
                    deal_number=deal_number,
                    company_name=lead_data["company_name"],
                    contact_name=lead_data.get("contact_name"),
                    contact_email=lead_data.get("contact_email"),
                    contact_phone=lead_data.get("contact_phone"),
                    contact_title=lead_data.get("contact_title"),
                    source=source,
                    stage=DealStage.LEAD,
                    probability=STAGE_PROBABILITY[DealStage.LEAD],
                    estimated_mrr=Decimal(str(lead_data.get("estimated_mrr", 0))) if lead_data.get("estimated_mrr") else None,
                    estimated_trucks=str(lead_data.get("estimated_trucks")) if lead_data.get("estimated_trucks") else None,
                    assigned_sales_rep_id=rep_id,
                    notes=lead_data.get("notes"),
                    created_by_id=created_by_id,
                )

                self.db.add(deal)
                await self.db.flush()
                created_deals.append(deal.id)

            except Exception as e:
                errors.append({"index": idx, "company": lead_data.get("company_name"), "error": str(e)})

        await self.db.commit()

        # Fetch full deal responses
        deal_responses = []
        for deal_id in created_deals:
            deal_response = await self.get_deal(deal_id)
            if deal_response:
                deal_responses.append(deal_response)

        return deal_responses, errors

    async def enrich_deal_with_ai(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Use AI to search for and enrich a deal with contact information."""
        result = await self.db.execute(
            select(HQDeal).where(HQDeal.id == deal_id)
        )
        deal = result.scalar_one_or_none()
        if not deal:
            return None

        llm = LLMRouter()

        system_prompt = """You are a business intelligence researcher for the trucking industry.

Find contact information for a trucking company. Return ONLY valid JSON:
{
  "contact_name": "John Smith",
  "contact_title": "Owner",
  "contact_email": "john@company.com",
  "contact_phone": "555-123-4567",
  "linkedin_url": "https://linkedin.com/in/johnsmith",
  "notes": "Founded in 2010, specializes in refrigerated freight.",
  "confidence": "high"
}"""

        user_prompt = f"""Find contact information for this trucking company:

Company Name: {deal.company_name}
Current Phone: {deal.contact_phone or 'Unknown'}
Current Email: {deal.contact_email or 'Unknown'}
Fleet Size: {deal.estimated_trucks or 'Unknown'} trucks
DOT Number: {deal.dot_number or 'Unknown'}
Notes: {deal.notes or 'None'}"""

        try:
            response, metadata = await llm.generate(
                agent_role="alex",
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=2048
            )

            response_text = response.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

            enrichment_data = json.loads(response_text)

            updated = False

            if enrichment_data.get("contact_name") and not deal.contact_name:
                deal.contact_name = enrichment_data["contact_name"]
                updated = True

            if enrichment_data.get("contact_title") and not deal.contact_title:
                deal.contact_title = enrichment_data["contact_title"]
                updated = True

            if enrichment_data.get("contact_email") and not deal.contact_email:
                deal.contact_email = enrichment_data["contact_email"]
                updated = True

            if enrichment_data.get("contact_phone") and not deal.contact_phone:
                deal.contact_phone = enrichment_data["contact_phone"]
                updated = True

            # Append enrichment notes
            enrichment_notes = []
            if enrichment_data.get("linkedin_url"):
                enrichment_notes.append(f"LinkedIn: {enrichment_data['linkedin_url']}")
            if enrichment_data.get("notes"):
                enrichment_notes.append(f"AI Notes: {enrichment_data['notes']}")

            if enrichment_notes:
                new_notes = "\n".join(enrichment_notes)
                if deal.notes:
                    deal.notes = f"{deal.notes}\n\n--- AI Enrichment ---\n{new_notes}"
                else:
                    deal.notes = f"--- AI Enrichment ---\n{new_notes}"
                updated = True

            if updated:
                await self.db.commit()

            return await self.get_deal(deal_id)

        except Exception as e:
            print(f"[Deal Enrichment] Failed to enrich deal {deal_id}: {str(e)}")
            return await self.get_deal(deal_id)

    async def get_activities(self, deal_id: str) -> List[Dict[str, Any]]:
        """Get activities for a deal."""
        result = await self.db.execute(
            select(HQDealActivity)
            .options(selectinload(HQDealActivity.created_by))
            .where(HQDealActivity.deal_id == deal_id)
            .order_by(HQDealActivity.created_at.desc())
        )
        activities = result.scalars().all()

        return [
            {
                "id": a.id,
                "dealId": a.deal_id,
                "activityType": a.activity_type,
                "description": a.description,
                "fromStage": a.from_stage,
                "toStage": a.to_stage,
                "createdById": a.created_by_id,
                "createdByName": f"{a.created_by.first_name} {a.created_by.last_name}" if a.created_by else None,
                "createdAt": a.created_at.isoformat() if a.created_at else None
            }
            for a in activities
        ]

    async def add_activity(
        self,
        deal_id: str,
        activity_type: str,
        description: str,
        created_by_id: str
    ) -> Dict[str, Any]:
        """Add an activity to a deal."""
        activity = HQDealActivity(
            id=str(uuid.uuid4()),
            deal_id=deal_id,
            activity_type=activity_type,
            description=description,
            created_by_id=created_by_id
        )
        self.db.add(activity)
        await self.db.commit()

        # Update last_contacted_at if relevant activity
        if activity_type in ["call", "email", "meeting"]:
            result = await self.db.execute(
                select(HQDeal).where(HQDeal.id == deal_id)
            )
            deal = result.scalar_one_or_none()
            if deal:
                deal.last_contacted_at = datetime.utcnow()
                await self.db.commit()

        return {
            "id": activity.id,
            "dealId": activity.deal_id,
            "activityType": activity.activity_type,
            "description": activity.description,
            "createdAt": activity.created_at.isoformat() if activity.created_at else None
        }

    async def _log_activity(
        self,
        deal_id: str,
        activity_type: str,
        description: str,
        created_by_id: Optional[str],
        from_stage: Optional[str] = None,
        to_stage: Optional[str] = None
    ):
        """Internal method to log deal activities."""
        activity = HQDealActivity(
            id=str(uuid.uuid4()),
            deal_id=deal_id,
            activity_type=activity_type,
            description=description,
            from_stage=from_stage,
            to_stage=to_stage,
            created_by_id=created_by_id
        )
        self.db.add(activity)

    def _to_response(self, deal: HQDeal) -> Dict[str, Any]:
        """Convert deal model to response dict."""
        return {
            "id": deal.id,
            "dealNumber": deal.deal_number,
            "companyName": deal.company_name,
            "contactName": deal.contact_name,
            "contactEmail": deal.contact_email,
            "contactPhone": deal.contact_phone,
            "contactTitle": deal.contact_title,
            "stage": deal.stage.value if deal.stage else "lead",
            "probability": float(deal.probability) if deal.probability else 10,
            "estimatedMrr": float(deal.estimated_mrr) if deal.estimated_mrr else None,
            "estimatedSetupFee": float(deal.estimated_setup_fee) if deal.estimated_setup_fee else 0,
            "estimatedTrucks": deal.estimated_trucks,
            "estimatedCloseDate": deal.estimated_close_date.isoformat() if deal.estimated_close_date else None,
            "source": deal.source.value if deal.source else "other",
            "assignedSalesRepId": deal.assigned_sales_rep_id,
            "assignedSalesRepName": f"{deal.assigned_sales_rep.first_name} {deal.assigned_sales_rep.last_name}" if deal.assigned_sales_rep else None,
            "nextFollowUpDate": deal.next_follow_up_date.isoformat() if deal.next_follow_up_date else None,
            "lastContactedAt": deal.last_contacted_at.isoformat() if deal.last_contacted_at else None,
            "dotNumber": deal.dot_number,
            "mcNumber": deal.mc_number,
            "state": deal.state,
            "carrierType": deal.carrier_type,
            "lostReason": deal.lost_reason,
            "competitor": deal.competitor,
            "wonAt": deal.won_at.isoformat() if deal.won_at else None,
            "lostAt": deal.lost_at.isoformat() if deal.lost_at else None,
            "subscriptionId": deal.subscription.id if deal.subscription else None,
            "notes": deal.notes,
            "createdById": deal.created_by_id,
            "createdAt": deal.created_at.isoformat() if deal.created_at else None,
            "updatedAt": deal.updated_at.isoformat() if deal.updated_at else None,
        }

    # ========================================================================
    # Master Spec: Lead Claiming & Locking (30-day exclusivity)
    # ========================================================================

    async def claim_deal(self, deal_id: str, agent_id: str) -> dict:
        """
        Claim a lead for exclusive access (30-day lock).

        Master Spec Module 1: Prevents lead poaching by giving agents exclusive
        access to leads they claim for 30 days.
        """
        from datetime import timedelta

        # Get the deal
        result = await self.db.execute(
            select(HQDeal).where(HQDeal.id == deal_id)
        )
        deal = result.scalar_one_or_none()
        if not deal:
            raise ValueError(f"Deal {deal_id} not found")

        # Check if already claimed by someone else
        if deal.claimed_by_id and deal.claimed_by_id != agent_id:
            # Check if claim has expired
            if deal.claimed_at:
                claim_expiry = deal.claimed_at + timedelta(days=30)
                if datetime.utcnow() < claim_expiry:
                    # Still claimed by someone else
                    time_remaining = claim_expiry - datetime.utcnow()
                    days_remaining = time_remaining.days
                    raise ValueError(
                        f"Deal is already claimed by another agent. "
                        f"Claim expires in {days_remaining} days."
                    )

        # Claim the deal
        deal.claimed_by_id = agent_id
        deal.claimed_at = datetime.utcnow()

        # Create activity
        activity = HQDealActivity(
            id=str(uuid.uuid4()),
            deal_id=deal_id,
            activity_type="lead_claimed",
            description=f"Lead claimed for 30-day exclusive access",
            created_by_id=agent_id,
        )
        self.db.add(activity)

        await self.db.commit()
        await self.db.refresh(deal)

        claim_expiry = deal.claimed_at + timedelta(days=30)

        return {
            "success": True,
            "dealId": deal_id,
            "claimedBy": agent_id,
            "claimedAt": deal.claimed_at.isoformat(),
            "expiresAt": claim_expiry.isoformat(),
            "daysRemaining": 30
        }

    async def release_deal_claim(self, deal_id: str, agent_id: str, force: bool = False) -> dict:
        """
        Release a claimed lead back to the pool.

        Args:
            deal_id: ID of the deal to release
            agent_id: ID of the agent releasing the claim
            force: If True, allows admin to force-release any claim
        """
        result = await self.db.execute(
            select(HQDeal).where(HQDeal.id == deal_id)
        )
        deal = result.scalar_one_or_none()
        if not deal:
            raise ValueError(f"Deal {deal_id} not found")

        # Check permissions
        if not deal.claimed_by_id:
            raise ValueError("Deal is not claimed")

        if deal.claimed_by_id != agent_id and not force:
            raise ValueError("You can only release deals you have claimed")

        # Release the claim
        previous_owner = deal.claimed_by_id
        deal.claimed_by_id = None
        deal.claimed_at = None

        # Create activity
        activity = HQDealActivity(
            id=str(uuid.uuid4()),
            deal_id=deal_id,
            activity_type="lead_released",
            description=f"Lead claim released {'(forced by admin)' if force else '(voluntary)'}",
            created_by_id=agent_id,
        )
        self.db.add(activity)

        await self.db.commit()

        return {
            "success": True,
            "dealId": deal_id,
            "previousOwner": previous_owner,
            "releasedBy": agent_id,
            "forced": force
        }

    async def get_claimed_deals(self, agent_id: str) -> List[dict]:
        """Get all deals claimed by a specific agent."""
        result = await self.db.execute(
            select(HQDeal)
            .where(HQDeal.claimed_by_id == agent_id)
            .where(HQDeal.stage.not_in([DealStage.WON, DealStage.LOST]))
            .order_by(HQDeal.claimed_at.desc())
        )
        deals = result.scalars().all()

        from datetime import timedelta
        return [{
            "id": deal.id,
            "dealNumber": deal.deal_number,
            "companyName": deal.company_name,
            "claimedAt": deal.claimed_at.isoformat() if deal.claimed_at else None,
            "expiresAt": (deal.claimed_at + timedelta(days=30)).isoformat() if deal.claimed_at else None,
            "daysRemaining": (30 - (datetime.utcnow() - deal.claimed_at).days) if deal.claimed_at else 0,
            "stage": deal.stage.value,
            "estimatedMrr": float(deal.estimated_mrr) if deal.estimated_mrr else None,
        } for deal in deals]

    # ========================================================================
    # Master Spec: PQL (Product Qualified Lead) Scoring Algorithm
    # ========================================================================

    async def calculate_pql_score(self, deal_id: str) -> dict:
        """
        Calculate Product Qualified Lead score (0.00-1.00).

        Master Spec Module 1: PQL scoring helps prioritize leads based on:
        - Fleet size (40% weight) - Most important factor
        - Carrier operation type (20% weight)
        - Contact information completeness (20% weight)
        - Geographic location (10% weight)
        - Data quality (10% weight)
        """
        from app.models.hq_deal import EnrichmentStatus

        result = await self.db.execute(
            select(HQDeal).where(HQDeal.id == deal_id)
        )
        deal = result.scalar_one_or_none()
        if not deal:
            raise ValueError(f"Deal {deal_id} not found")

        # Initialize score and factors
        total_score = Decimal("0.0")
        factors = {}

        # 1. Fleet Size Score (40% weight)
        fleet_size_score = Decimal("0.0")
        if deal.estimated_trucks:
            try:
                # Parse truck count (handles "15", "10-25", etc.)
                truck_str = str(deal.estimated_trucks).strip()
                if "-" in truck_str:
                    # Range like "10-25" - take midpoint
                    parts = truck_str.split("-")
                    trucks = (int(parts[0]) + int(parts[1])) / 2
                else:
                    trucks = int(truck_str)

                # Score based on fleet size
                if trucks >= 100:
                    fleet_size_score = Decimal("1.0")
                elif trucks >= 50:
                    fleet_size_score = Decimal("0.85")
                elif trucks >= 20:
                    fleet_size_score = Decimal("0.70")
                elif trucks >= 10:
                    fleet_size_score = Decimal("0.55")
                elif trucks >= 5:
                    fleet_size_score = Decimal("0.40")
                else:
                    fleet_size_score = Decimal("0.25")

                factors["fleet_size"] = {
                    "trucks": trucks,
                    "score": float(fleet_size_score),
                    "weight": 0.40
                }
            except (ValueError, IndexError):
                factors["fleet_size"] = {"trucks": 0, "score": 0.0, "weight": 0.40}
        else:
            factors["fleet_size"] = {"trucks": 0, "score": 0.0, "weight": 0.40}

        total_score += fleet_size_score * Decimal("0.40")

        # 2. Carrier Type Score (20% weight)
        carrier_type_score = Decimal("0.0")
        if deal.carrier_type:
            carrier_type_lower = deal.carrier_type.lower()
            # Authorized for-hire carriers are ideal customers
            if "authorized" in carrier_type_lower or carrier_type_lower == "a":
                carrier_type_score = Decimal("1.0")
            # Exempt for-hire are good prospects
            elif "exempt" in carrier_type_lower or carrier_type_lower == "b":
                carrier_type_score = Decimal("0.70")
            # Private carriers are lower priority
            elif "private" in carrier_type_lower or carrier_type_lower == "c":
                carrier_type_score = Decimal("0.50")
            else:
                carrier_type_score = Decimal("0.30")

            factors["carrier_type"] = {
                "type": deal.carrier_type,
                "score": float(carrier_type_score),
                "weight": 0.20
            }
        else:
            factors["carrier_type"] = {"type": None, "score": 0.0, "weight": 0.20}

        total_score += carrier_type_score * Decimal("0.20")

        # 3. Contact Information Completeness (20% weight)
        contact_score = Decimal("0.0")
        contact_completeness = 0
        contact_total = 4

        if deal.contact_name:
            contact_completeness += 1
        if deal.contact_email:
            contact_completeness += 1
        if deal.contact_phone:
            contact_completeness += 1
        if deal.contact_title:
            contact_completeness += 1

        contact_score = Decimal(str(contact_completeness / contact_total))
        factors["contact_info"] = {
            "completeness": f"{contact_completeness}/{contact_total}",
            "score": float(contact_score),
            "weight": 0.20
        }

        total_score += contact_score * Decimal("0.20")

        # 4. Geographic Location (10% weight)
        # Prioritize states with high freight volume
        geo_score = Decimal("0.0")
        high_volume_states = ["TX", "CA", "FL", "IL", "GA", "OH", "PA", "NC"]
        medium_volume_states = ["TN", "AZ", "IN", "MI", "VA", "NJ", "WA", "MO"]

        if deal.state:
            state_upper = deal.state.upper()
            if state_upper in high_volume_states:
                geo_score = Decimal("1.0")
            elif state_upper in medium_volume_states:
                geo_score = Decimal("0.70")
            else:
                geo_score = Decimal("0.40")

            factors["geography"] = {
                "state": deal.state,
                "score": float(geo_score),
                "weight": 0.10
            }
        else:
            factors["geography"] = {"state": None, "score": 0.0, "weight": 0.10}

        total_score += geo_score * Decimal("0.10")

        # 5. Data Quality (10% weight)
        data_quality_score = Decimal("0.0")
        quality_points = 0
        quality_total = 5

        # Has DOT number
        if deal.dot_number:
            quality_points += 1

        # Has MC number
        if deal.mc_number:
            quality_points += 1

        # Source is not "other"
        if deal.source and deal.source != DealSource.OTHER:
            quality_points += 1

        # Has been enriched
        if deal.enrichment_status == EnrichmentStatus.COMPLETED:
            quality_points += 1

        # Has notes
        if deal.notes:
            quality_points += 1

        data_quality_score = Decimal(str(quality_points / quality_total))
        factors["data_quality"] = {
            "quality_points": f"{quality_points}/{quality_total}",
            "score": float(data_quality_score),
            "weight": 0.10
        }

        total_score += data_quality_score * Decimal("0.10")

        # Round to 2 decimal places
        final_score = round(total_score, 2)

        # Determine tier
        tier = self._get_pql_tier(final_score)

        # Update deal
        deal.pql_score = final_score
        deal.pql_scored_at = datetime.utcnow()
        deal.pql_factors = json.dumps(factors)

        await self.db.commit()

        return {
            "success": True,
            "dealId": deal_id,
            "pqlScore": float(final_score),
            "tier": tier,
            "factors": factors,
            "scoredAt": deal.pql_scored_at.isoformat()
        }

    def _get_pql_tier(self, score: Decimal) -> str:
        """Classify PQL score into tier."""
        if score >= Decimal("0.75"):
            return "Hot Lead"
        elif score >= Decimal("0.50"):
            return "Warm Lead"
        elif score >= Decimal("0.30"):
            return "Cold Lead"
        else:
            return "Low Priority"

    async def score_all_unscored_deals(self, limit: int = 100) -> dict:
        """
        Batch score all deals that haven't been scored yet.

        Master Spec Module 1: Run this periodically to score new leads.
        """
        # Get unscored deals
        result = await self.db.execute(
            select(HQDeal)
            .where(HQDeal.pql_score == None)
            .where(HQDeal.stage.in_([DealStage.LEAD, DealStage.CONTACTED, DealStage.QUALIFIED]))
            .limit(limit)
        )
        deals = result.scalars().all()

        scored_count = 0
        errors = []

        for deal in deals:
            try:
                await self.calculate_pql_score(deal.id)
                scored_count += 1
            except Exception as e:
                errors.append({
                    "dealId": deal.id,
                    "companyName": deal.company_name,
                    "error": str(e)
                })

        return {
            "success": True,
            "totalScored": scored_count,
            "errors": errors
        }
