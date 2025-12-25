"""HQ Opportunity service for sales pipeline management."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.hq_opportunity import HQOpportunity, OpportunityStage
from app.models.hq_quote import HQQuote, QuoteStatus
from app.models.hq_employee import HQEmployee, HQRole
from app.schemas.hq import (
    HQOpportunityCreate, HQOpportunityUpdate, HQOpportunityResponse,
    HQOpportunityConvert, HQPipelineSummary, HQQuoteResponse
)


class HQOpportunityService:
    """Service for managing sales opportunities."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _generate_opportunity_number(self) -> str:
        """Generate unique opportunity number like OPP-000001."""
        result = await self.db.execute(
            select(func.count(HQOpportunity.id))
        )
        count = result.scalar() or 0
        return f"OPP-{count + 1:06d}"

    async def get_opportunities(
        self,
        current_user_id: str,
        current_user_role: HQRole,
        stage: Optional[str] = None,
        assigned_to_me: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[HQOpportunityResponse]:
        """Get opportunities with optional filtering. Sales reps only see their own."""
        query = select(HQOpportunity).options(
            selectinload(HQOpportunity.assigned_sales_rep)
        )

        # Sales managers only see their own opportunities
        if current_user_role == HQRole.SALES_MANAGER or assigned_to_me:
            query = query.where(HQOpportunity.assigned_sales_rep_id == current_user_id)

        if stage:
            query = query.where(HQOpportunity.stage == stage)

        query = query.order_by(HQOpportunity.created_at.desc()).offset(offset).limit(limit)

        result = await self.db.execute(query)
        opportunities = result.scalars().all()

        return [self._to_response(opp) for opp in opportunities]

    async def get_opportunity(self, opportunity_id: str) -> Optional[HQOpportunityResponse]:
        """Get a single opportunity by ID."""
        result = await self.db.execute(
            select(HQOpportunity)
            .options(selectinload(HQOpportunity.assigned_sales_rep))
            .where(HQOpportunity.id == opportunity_id)
        )
        opp = result.scalar_one_or_none()
        if not opp:
            return None
        return self._to_response(opp)

    async def create_opportunity(
        self,
        data: HQOpportunityCreate,
        created_by_id: str
    ) -> HQOpportunityResponse:
        """Create a new opportunity."""
        opp_number = await self._generate_opportunity_number()

        opportunity = HQOpportunity(
            id=str(uuid.uuid4()),
            opportunity_number=opp_number,
            lead_id=data.lead_id,
            tenant_id=data.tenant_id,
            company_name=data.company_name,
            contact_name=data.contact_name,
            contact_email=data.contact_email,
            contact_phone=data.contact_phone,
            title=data.title,
            description=data.description,
            stage=OpportunityStage.DISCOVERY,
            probability=data.probability or Decimal("20"),
            estimated_mrr=data.estimated_mrr,
            estimated_setup_fee=data.estimated_setup_fee,
            estimated_trucks=data.estimated_trucks,
            estimated_close_date=data.estimated_close_date,
            assigned_sales_rep_id=data.assigned_sales_rep_id or created_by_id,
            notes=data.notes,
            created_by_id=created_by_id,
        )

        self.db.add(opportunity)
        await self.db.commit()
        await self.db.refresh(opportunity)

        return await self.get_opportunity(opportunity.id)

    async def update_opportunity(
        self,
        opportunity_id: str,
        data: HQOpportunityUpdate
    ) -> Optional[HQOpportunityResponse]:
        """Update an existing opportunity."""
        result = await self.db.execute(
            select(HQOpportunity).where(HQOpportunity.id == opportunity_id)
        )
        opp = result.scalar_one_or_none()
        if not opp:
            return None

        update_data = data.model_dump(exclude_unset=True, by_alias=False)
        for field, value in update_data.items():
            if field == "stage" and value:
                new_stage = OpportunityStage(value)
                setattr(opp, field, new_stage)
                # Update probability based on stage
                stage_probabilities = {
                    OpportunityStage.DISCOVERY: Decimal("20"),
                    OpportunityStage.PROPOSAL: Decimal("40"),
                    OpportunityStage.NEGOTIATION: Decimal("70"),
                    OpportunityStage.CLOSED_WON: Decimal("100"),
                    OpportunityStage.CLOSED_LOST: Decimal("0"),
                }
                if data.probability is None:
                    opp.probability = stage_probabilities.get(new_stage, opp.probability)
                # Set actual close date for closed stages
                if new_stage in [OpportunityStage.CLOSED_WON, OpportunityStage.CLOSED_LOST]:
                    opp.actual_close_date = datetime.utcnow()
            else:
                setattr(opp, field, value)

        await self.db.commit()
        return await self.get_opportunity(opportunity_id)

    async def get_pipeline_summary(
        self,
        current_user_id: str,
        current_user_role: HQRole
    ) -> List[HQPipelineSummary]:
        """Get pipeline summary grouped by stage."""
        query = select(
            HQOpportunity.stage,
            func.count(HQOpportunity.id).label("count"),
            func.sum(HQOpportunity.estimated_mrr).label("total_value"),
            func.sum(HQOpportunity.estimated_mrr * HQOpportunity.probability / 100).label("weighted_value")
        ).where(
            HQOpportunity.stage.notin_([OpportunityStage.CLOSED_WON, OpportunityStage.CLOSED_LOST])
        )

        # Sales managers only see their own pipeline
        if current_user_role == HQRole.SALES_MANAGER:
            query = query.where(HQOpportunity.assigned_sales_rep_id == current_user_id)

        query = query.group_by(HQOpportunity.stage)

        result = await self.db.execute(query)
        rows = result.all()

        # Build response with all stages (even if empty)
        stage_order = [OpportunityStage.DISCOVERY, OpportunityStage.PROPOSAL, OpportunityStage.NEGOTIATION]
        stage_data = {row.stage: row for row in rows}

        summaries = []
        for stage in stage_order:
            if stage in stage_data:
                row = stage_data[stage]
                summaries.append(HQPipelineSummary(
                    stage=stage.value,
                    count=row.count,
                    total_value=row.total_value or Decimal("0"),
                    weighted_value=row.weighted_value or Decimal("0"),
                ))
            else:
                summaries.append(HQPipelineSummary(
                    stage=stage.value,
                    count=0,
                    total_value=Decimal("0"),
                    weighted_value=Decimal("0"),
                ))

        return summaries

    async def convert_to_quote(
        self,
        opportunity_id: str,
        data: HQOpportunityConvert,
        converted_by_id: str
    ) -> Optional[HQQuoteResponse]:
        """Convert an opportunity to a quote."""
        result = await self.db.execute(
            select(HQOpportunity).where(HQOpportunity.id == opportunity_id)
        )
        opp = result.scalar_one_or_none()
        if not opp:
            return None

        if opp.converted_to_quote_id:
            raise ValueError("Opportunity has already been converted to a quote")

        # Generate quote number
        quote_count = await self.db.execute(select(func.count(HQQuote.id)))
        quote_number = f"QT-{(quote_count.scalar() or 0) + 1:06d}"

        # Calculate final rate after any discounts
        final_rate = data.base_monthly_rate

        # Create quote from opportunity
        quote = HQQuote(
            id=str(uuid.uuid4()),
            quote_number=quote_number,
            tenant_id=opp.tenant_id,
            contact_name=opp.contact_name,
            contact_email=opp.contact_email,
            contact_company=opp.company_name,
            contact_phone=opp.contact_phone,
            title=data.title,
            description=opp.description,
            tier=data.tier,
            status=QuoteStatus.DRAFT,
            base_monthly_rate=data.base_monthly_rate,
            discount_percent=Decimal("0"),
            discount_amount=Decimal("0"),
            final_monthly_rate=final_rate,
            setup_fee=data.setup_fee or Decimal("0"),
            valid_until=datetime.utcnow() + timedelta(days=data.valid_days),
            assigned_sales_rep_id=opp.assigned_sales_rep_id,
            created_by_id=converted_by_id,
        )

        self.db.add(quote)

        # Update opportunity
        opp.converted_to_quote_id = quote.id
        opp.converted_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(quote)

        # Return quote response
        return HQQuoteResponse(
            id=quote.id,
            tenant_id=quote.tenant_id,
            quote_number=quote.quote_number,
            title=quote.title,
            description=quote.description,
            tier=quote.tier,
            contact_name=quote.contact_name,
            contact_email=quote.contact_email,
            contact_company=quote.contact_company,
            contact_phone=quote.contact_phone,
            status=quote.status.value,
            base_monthly_rate=quote.base_monthly_rate,
            discount_percent=quote.discount_percent,
            discount_amount=quote.discount_amount,
            final_monthly_rate=quote.final_monthly_rate,
            setup_fee=quote.setup_fee,
            addons=quote.addons,
            valid_until=quote.valid_until,
            sent_at=quote.sent_at,
            viewed_at=quote.viewed_at,
            accepted_at=quote.accepted_at,
            rejected_at=quote.rejected_at,
            rejection_reason=quote.rejection_reason,
            created_by_id=quote.created_by_id,
            created_at=quote.created_at,
            updated_at=quote.updated_at,
        )

    def _to_response(self, opp: HQOpportunity) -> HQOpportunityResponse:
        """Convert opportunity model to response schema."""
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
            stage=opp.stage.value if opp.stage else "discovery",
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
