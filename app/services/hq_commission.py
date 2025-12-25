"""HQ Commission service for tracking sales rep commissions."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select, func, and_, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.hq_sales_rep_commission import HQSalesRepCommission, CommissionTier
from app.models.hq_commission_record import HQCommissionRecord, CommissionRecordStatus
from app.models.hq_commission_payment import HQCommissionPayment, CommissionPaymentStatus
from app.models.hq_contract import HQContract, ContractStatus
from app.models.hq_tenant import HQTenant
from app.models.hq_lead import HQLead
from app.models.hq_opportunity import HQOpportunity, OpportunityStage
from app.models.hq_employee import HQEmployee, HQRole
from app.schemas.hq import (
    HQSalesRepCommissionCreate, HQSalesRepCommissionUpdate, HQSalesRepCommissionResponse,
    HQCommissionRecordResponse, HQCommissionPaymentResponse, HQCommissionPaymentApprove,
    HQSalesRepEarnings, HQSalesRepAccountSummary
)


class HQCommissionService:
    """Service for managing sales rep commissions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Commission Configuration
    # =========================================================================

    async def get_all_commission_configs(self) -> List[HQSalesRepCommissionResponse]:
        """Get all sales rep commission configurations."""
        result = await self.db.execute(
            select(HQSalesRepCommission)
            .options(selectinload(HQSalesRepCommission.sales_rep))
            .order_by(HQSalesRepCommission.created_at.desc())
        )
        configs = result.scalars().all()
        return [self._config_to_response(c) for c in configs]

    async def get_commission_config(self, sales_rep_id: str) -> Optional[HQSalesRepCommissionResponse]:
        """Get commission config for a specific sales rep."""
        result = await self.db.execute(
            select(HQSalesRepCommission)
            .options(selectinload(HQSalesRepCommission.sales_rep))
            .where(HQSalesRepCommission.sales_rep_id == sales_rep_id)
        )
        config = result.scalar_one_or_none()
        if not config:
            return None
        return self._config_to_response(config)

    async def create_commission_config(
        self,
        data: HQSalesRepCommissionCreate,
        created_by_id: str
    ) -> HQSalesRepCommissionResponse:
        """Create or update commission config for a sales rep."""
        # Check if config already exists
        existing = await self.db.execute(
            select(HQSalesRepCommission)
            .where(HQSalesRepCommission.sales_rep_id == data.sales_rep_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Commission config already exists for this sales rep. Use update instead.")

        config = HQSalesRepCommission(
            id=str(uuid.uuid4()),
            sales_rep_id=data.sales_rep_id,
            commission_rate=data.commission_rate,
            tier_level=CommissionTier(data.tier_level) if data.tier_level else CommissionTier.JUNIOR,
            effective_from=data.effective_from or datetime.utcnow(),
            effective_until=data.effective_until,
            notes=data.notes,
            created_by_id=created_by_id,
        )

        self.db.add(config)
        await self.db.commit()
        await self.db.refresh(config)

        return await self.get_commission_config(data.sales_rep_id)

    async def update_commission_config(
        self,
        sales_rep_id: str,
        data: HQSalesRepCommissionUpdate,
        updated_by_id: str
    ) -> Optional[HQSalesRepCommissionResponse]:
        """Update commission config for a sales rep."""
        result = await self.db.execute(
            select(HQSalesRepCommission)
            .where(HQSalesRepCommission.sales_rep_id == sales_rep_id)
        )
        config = result.scalar_one_or_none()
        if not config:
            return None

        update_data = data.model_dump(exclude_unset=True, by_alias=False)
        for field, value in update_data.items():
            if field == "tier_level" and value:
                setattr(config, field, CommissionTier(value))
            else:
                setattr(config, field, value)

        config.updated_by_id = updated_by_id

        await self.db.commit()
        return await self.get_commission_config(sales_rep_id)

    # =========================================================================
    # Commission Records (per deal)
    # =========================================================================

    async def create_commission_record_for_contract(
        self,
        contract: HQContract,
        sales_rep_id: str
    ) -> Optional[HQCommissionRecord]:
        """Create a commission record when a contract becomes active."""
        # Get sales rep's commission rate
        config_result = await self.db.execute(
            select(HQSalesRepCommission)
            .where(HQSalesRepCommission.sales_rep_id == sales_rep_id)
        )
        config = config_result.scalar_one_or_none()
        if not config:
            return None  # No commission config, no commission

        now = datetime.utcnow()
        eligible_at = now + timedelta(days=30)

        record = HQCommissionRecord(
            id=str(uuid.uuid4()),
            sales_rep_id=sales_rep_id,
            contract_id=contract.id,
            tenant_id=contract.tenant_id,
            commission_rate=config.commission_rate,
            base_mrr=contract.monthly_value,
            status=CommissionRecordStatus.PENDING,
            deal_closed_at=now,
            eligible_at=eligible_at,
            is_active=True,
        )

        self.db.add(record)
        await self.db.commit()
        return record

    async def get_commission_records(
        self,
        sales_rep_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[HQCommissionRecordResponse]:
        """Get commission records with optional filtering."""
        query = select(HQCommissionRecord).options(
            selectinload(HQCommissionRecord.sales_rep),
            selectinload(HQCommissionRecord.tenant).selectinload(HQTenant.company)
        )

        if sales_rep_id:
            query = query.where(HQCommissionRecord.sales_rep_id == sales_rep_id)
        if status:
            query = query.where(HQCommissionRecord.status == status)

        query = query.order_by(HQCommissionRecord.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        records = result.scalars().all()

        return [self._record_to_response(r) for r in records]

    # =========================================================================
    # Commission Payments
    # =========================================================================

    async def get_commission_payments(
        self,
        sales_rep_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[HQCommissionPaymentResponse]:
        """Get commission payments with optional filtering."""
        query = select(HQCommissionPayment).options(
            selectinload(HQCommissionPayment.sales_rep),
            selectinload(HQCommissionPayment.commission_record).selectinload(HQCommissionRecord.tenant).selectinload(HQTenant.company)
        )

        if sales_rep_id:
            query = query.where(HQCommissionPayment.sales_rep_id == sales_rep_id)
        if status:
            query = query.where(HQCommissionPayment.status == status)

        query = query.order_by(HQCommissionPayment.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        payments = result.scalars().all()

        return [self._payment_to_response(p) for p in payments]

    async def approve_commission_payment(
        self,
        payment_id: str,
        data: HQCommissionPaymentApprove,
        approved_by_id: str
    ) -> Optional[HQCommissionPaymentResponse]:
        """Approve a commission payment."""
        result = await self.db.execute(
            select(HQCommissionPayment).where(HQCommissionPayment.id == payment_id)
        )
        payment = result.scalar_one_or_none()
        if not payment:
            return None

        payment.status = CommissionPaymentStatus.APPROVED
        payment.approved_by_id = approved_by_id
        payment.approved_at = datetime.utcnow()
        if data.payment_method:
            payment.payment_method = data.payment_method
        if data.payment_reference:
            payment.payment_reference = data.payment_reference
        if data.notes:
            payment.notes = data.notes

        await self.db.commit()

        # Reload with relationships
        result = await self.db.execute(
            select(HQCommissionPayment)
            .options(
                selectinload(HQCommissionPayment.sales_rep),
                selectinload(HQCommissionPayment.commission_record).selectinload(HQCommissionRecord.tenant).selectinload(HQTenant.company)
            )
            .where(HQCommissionPayment.id == payment_id)
        )
        return self._payment_to_response(result.scalar_one())

    async def mark_payment_paid(
        self,
        payment_id: str,
        payment_reference: Optional[str] = None
    ) -> Optional[HQCommissionPaymentResponse]:
        """Mark a commission payment as paid."""
        result = await self.db.execute(
            select(HQCommissionPayment).where(HQCommissionPayment.id == payment_id)
        )
        payment = result.scalar_one_or_none()
        if not payment:
            return None

        payment.status = CommissionPaymentStatus.PAID
        payment.payment_date = datetime.utcnow()
        if payment_reference:
            payment.payment_reference = payment_reference

        # Update the commission record's total paid amount
        record_result = await self.db.execute(
            select(HQCommissionRecord).where(HQCommissionRecord.id == payment.commission_record_id)
        )
        record = record_result.scalar_one()
        record.total_paid_amount = (record.total_paid_amount or Decimal("0")) + payment.commission_amount
        record.payment_count = str(int(record.payment_count or "0") + 1)

        await self.db.commit()

        result = await self.db.execute(
            select(HQCommissionPayment)
            .options(
                selectinload(HQCommissionPayment.sales_rep),
                selectinload(HQCommissionPayment.commission_record).selectinload(HQCommissionRecord.tenant).selectinload(HQTenant.company)
            )
            .where(HQCommissionPayment.id == payment_id)
        )
        return self._payment_to_response(result.scalar_one())

    # =========================================================================
    # Sales Rep Earnings Dashboard
    # =========================================================================

    async def get_sales_rep_earnings(self, sales_rep_id: str) -> Optional[HQSalesRepEarnings]:
        """Get comprehensive earnings data for a sales rep."""
        # Get sales rep info
        rep_result = await self.db.execute(
            select(HQEmployee).where(HQEmployee.id == sales_rep_id)
        )
        rep = rep_result.scalar_one_or_none()
        if not rep:
            return None

        # Get commission config
        config_result = await self.db.execute(
            select(HQSalesRepCommission).where(HQSalesRepCommission.sales_rep_id == sales_rep_id)
        )
        config = config_result.scalar_one_or_none()
        commission_rate = config.commission_rate if config else Decimal("0")
        tier_level = config.tier_level.value if config else "junior"

        now = datetime.utcnow()
        year_start = datetime(now.year, 1, 1)
        month_start = datetime(now.year, now.month, 1)

        # Lifetime earnings (paid payments)
        lifetime_result = await self.db.execute(
            select(func.sum(HQCommissionPayment.commission_amount))
            .where(
                and_(
                    HQCommissionPayment.sales_rep_id == sales_rep_id,
                    HQCommissionPayment.status == CommissionPaymentStatus.PAID
                )
            )
        )
        lifetime_earnings = lifetime_result.scalar() or Decimal("0")

        # YTD earnings
        ytd_result = await self.db.execute(
            select(func.sum(HQCommissionPayment.commission_amount))
            .where(
                and_(
                    HQCommissionPayment.sales_rep_id == sales_rep_id,
                    HQCommissionPayment.status == CommissionPaymentStatus.PAID,
                    HQCommissionPayment.payment_date >= year_start
                )
            )
        )
        ytd_earnings = ytd_result.scalar() or Decimal("0")

        # MTD earnings
        mtd_result = await self.db.execute(
            select(func.sum(HQCommissionPayment.commission_amount))
            .where(
                and_(
                    HQCommissionPayment.sales_rep_id == sales_rep_id,
                    HQCommissionPayment.status == CommissionPaymentStatus.PAID,
                    HQCommissionPayment.payment_date >= month_start
                )
            )
        )
        mtd_earnings = mtd_result.scalar() or Decimal("0")

        # Pending amount (in 30-day waiting period)
        pending_result = await self.db.execute(
            select(func.sum(HQCommissionRecord.base_mrr * HQCommissionRecord.commission_rate / 100))
            .where(
                and_(
                    HQCommissionRecord.sales_rep_id == sales_rep_id,
                    HQCommissionRecord.status == CommissionRecordStatus.PENDING,
                    HQCommissionRecord.is_active == True
                )
            )
        )
        pending_amount = pending_result.scalar() or Decimal("0")

        # Eligible but unpaid
        eligible_result = await self.db.execute(
            select(func.sum(HQCommissionPayment.commission_amount))
            .where(
                and_(
                    HQCommissionPayment.sales_rep_id == sales_rep_id,
                    HQCommissionPayment.status.in_([CommissionPaymentStatus.PENDING, CommissionPaymentStatus.APPROVED])
                )
            )
        )
        eligible_unpaid = eligible_result.scalar() or Decimal("0")

        # Active accounts count and MRR
        active_result = await self.db.execute(
            select(
                func.count(HQCommissionRecord.id),
                func.sum(HQCommissionRecord.base_mrr)
            )
            .where(
                and_(
                    HQCommissionRecord.sales_rep_id == sales_rep_id,
                    HQCommissionRecord.is_active == True
                )
            )
        )
        active_row = active_result.one()
        active_accounts = active_row[0] or 0
        active_mrr = active_row[1] or Decimal("0")

        # Pipeline value (open opportunities)
        pipeline_result = await self.db.execute(
            select(
                func.count(HQOpportunity.id),
                func.sum(HQOpportunity.estimated_mrr)
            )
            .where(
                and_(
                    HQOpportunity.assigned_sales_rep_id == sales_rep_id,
                    HQOpportunity.stage.notin_([OpportunityStage.CLOSED_WON, OpportunityStage.CLOSED_LOST])
                )
            )
        )
        pipeline_row = pipeline_result.one()
        pipeline_count = pipeline_row[0] or 0
        pipeline_value = pipeline_row[1] or Decimal("0")

        # Leads count
        leads_result = await self.db.execute(
            select(func.count(HQLead.id))
            .where(
                and_(
                    HQLead.assigned_sales_rep_id == sales_rep_id,
                    HQLead.status != "converted"
                )
            )
        )
        leads_count = leads_result.scalar() or 0

        return HQSalesRepEarnings(
            sales_rep_id=sales_rep_id,
            sales_rep_name=f"{rep.first_name} {rep.last_name}",
            commission_rate=commission_rate,
            tier_level=tier_level,
            lifetime_earnings=lifetime_earnings,
            ytd_earnings=ytd_earnings,
            mtd_earnings=mtd_earnings,
            pending_amount=pending_amount,
            eligible_unpaid=eligible_unpaid,
            active_accounts=active_accounts,
            active_mrr=active_mrr,
            pipeline_value=pipeline_value,
            pipeline_count=pipeline_count,
            leads_count=leads_count,
        )

    async def get_sales_rep_accounts(self, sales_rep_id: str) -> List[HQSalesRepAccountSummary]:
        """Get all accounts assigned to a sales rep with MRR breakdown."""
        result = await self.db.execute(
            select(HQCommissionRecord)
            .options(
                selectinload(HQCommissionRecord.tenant).selectinload(HQTenant.company),
                selectinload(HQCommissionRecord.contract)
            )
            .where(HQCommissionRecord.sales_rep_id == sales_rep_id)
            .order_by(HQCommissionRecord.deal_closed_at.desc())
        )
        records = result.scalars().all()

        return [
            HQSalesRepAccountSummary(
                tenant_id=r.tenant_id,
                tenant_name=r.tenant.company.name if r.tenant and r.tenant.company else "Unknown",
                mrr=r.base_mrr,
                contract_start_date=r.deal_closed_at,
                commission_earned=r.total_paid_amount or Decimal("0"),
                status="active" if r.is_active else "inactive",
            )
            for r in records
        ]

    async def deactivate_sales_rep_commissions(
        self,
        sales_rep_id: str,
        reason: str
    ) -> int:
        """Deactivate all commission records for a sales rep (when they leave)."""
        result = await self.db.execute(
            select(HQCommissionRecord)
            .where(
                and_(
                    HQCommissionRecord.sales_rep_id == sales_rep_id,
                    HQCommissionRecord.is_active == True
                )
            )
        )
        records = result.scalars().all()

        now = datetime.utcnow()
        for record in records:
            record.is_active = False
            record.deactivated_at = now
            record.deactivated_reason = reason
            record.status = CommissionRecordStatus.CANCELLED

        await self.db.commit()
        return len(records)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _config_to_response(self, config: HQSalesRepCommission) -> HQSalesRepCommissionResponse:
        """Convert commission config model to response schema."""
        return HQSalesRepCommissionResponse(
            id=config.id,
            sales_rep_id=config.sales_rep_id,
            sales_rep_name=f"{config.sales_rep.first_name} {config.sales_rep.last_name}" if config.sales_rep else None,
            sales_rep_email=config.sales_rep.email if config.sales_rep else None,
            commission_rate=config.commission_rate,
            tier_level=config.tier_level.value if config.tier_level else "junior",
            effective_from=config.effective_from,
            effective_until=config.effective_until,
            notes=config.notes,
            created_by_id=config.created_by_id,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )

    def _record_to_response(self, record: HQCommissionRecord) -> HQCommissionRecordResponse:
        """Convert commission record model to response schema."""
        tenant_name = None
        if record.tenant and record.tenant.company:
            tenant_name = record.tenant.company.name

        return HQCommissionRecordResponse(
            id=record.id,
            sales_rep_id=record.sales_rep_id,
            sales_rep_name=f"{record.sales_rep.first_name} {record.sales_rep.last_name}" if record.sales_rep else None,
            contract_id=record.contract_id,
            tenant_id=record.tenant_id,
            tenant_name=tenant_name,
            commission_rate=record.commission_rate,
            base_mrr=record.base_mrr,
            status=record.status.value if record.status else "pending",
            deal_closed_at=record.deal_closed_at,
            eligible_at=record.eligible_at,
            total_paid_amount=record.total_paid_amount or Decimal("0"),
            is_active=record.is_active,
            deactivated_at=record.deactivated_at,
            deactivated_reason=record.deactivated_reason,
            created_at=record.created_at,
        )

    def _payment_to_response(self, payment: HQCommissionPayment) -> HQCommissionPaymentResponse:
        """Convert commission payment model to response schema."""
        tenant_name = None
        if payment.commission_record and payment.commission_record.tenant and payment.commission_record.tenant.company:
            tenant_name = payment.commission_record.tenant.company.name

        return HQCommissionPaymentResponse(
            id=payment.id,
            commission_record_id=payment.commission_record_id,
            sales_rep_id=payment.sales_rep_id,
            sales_rep_name=f"{payment.sales_rep.first_name} {payment.sales_rep.last_name}" if payment.sales_rep else None,
            tenant_name=tenant_name,
            period_start=payment.period_start,
            period_end=payment.period_end,
            mrr_amount=payment.mrr_amount,
            commission_rate=payment.commission_rate,
            commission_amount=payment.commission_amount,
            status=payment.status.value if payment.status else "pending",
            payment_date=payment.payment_date,
            payment_reference=payment.payment_reference,
            payment_method=payment.payment_method,
            approved_by_id=payment.approved_by_id,
            approved_at=payment.approved_at,
            created_at=payment.created_at,
        )
