"""Payroll service - handles pay calculation engine and payroll runs."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.load import Load
from app.models.worker import (
    Deduction,
    PayItem,
    PayItemType,
    PayrollRun,
    PayrollRunStatus,
    PayRule,
    PayRuleType,
    PayrollSettlement,
    Worker,
)
from app.models.equipment import Equipment
from app.schemas.worker import (
    PayItemDetail,
    PayrollPreviewRequest,
    PayrollPreviewResponse,
    PayrollRunCreate,
    PayrollRunResponse,
    SettlementPreview,
)


class PayrollService:
    """Service for payroll calculation and management."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def preview_payroll(
        self,
        company_id: str,
        request: PayrollPreviewRequest,
    ) -> PayrollPreviewResponse:
        """
        Generate payroll preview for a pay period.
        Calculates gross, deductions, and net for each worker.
        """
        # Get all active workers
        filters = request.filters or {}
        worker_types = filters.get("types", ["employee", "contractor"])
        worker_roles = filters.get("include", None)

        query = select(Worker).where(
            and_(
                Worker.company_id == company_id,
                Worker.status == "active",
                Worker.type.in_(worker_types) if worker_types else True,
            )
        )

        if worker_roles:
            query = query.where(Worker.role.in_(worker_roles))

        result = await self.db.execute(query)
        workers = result.scalars().all()

        settlements: List[SettlementPreview] = []
        total_gross = Decimal("0")
        total_deductions = Decimal("0")
        total_net = Decimal("0")

        for worker in workers:
            settlement = await self._calculate_worker_settlement(
                worker,
                request.period_start,
                request.period_end,
            )
            settlements.append(settlement)
            total_gross += settlement.gross
            total_deductions += settlement.total_deductions
            total_net += settlement.net

        return PayrollPreviewResponse(
            company_id=company_id,
            period_start=request.period_start,
            period_end=request.period_end,
            settlements=settlements,
            totals={
                "gross": float(total_gross),
                "deductions": float(total_deductions),
                "net": float(total_net),
                "worker_count": len(settlements),
            },
        )

    async def _calculate_worker_settlement(
        self,
        worker: Worker,
        period_start: date,
        period_end: date,
    ) -> SettlementPreview:
        """Calculate settlement for a single worker."""
        pay_items: List[PayItemDetail] = []

        # Get pay rules for this worker (or company defaults)
        pay_rules = await self._get_effective_pay_rules(worker.id, worker.company_id, period_start)

        if worker.role == "driver":
            # Get loads for driver in period
            loads = await self._get_driver_loads(worker.id, period_start, period_end)

            # Calculate mileage pay
            mileage_rule = next((r for r in pay_rules if r.rule_type == PayRuleType.MILEAGE), None)
            if mileage_rule:
                total_miles = sum(load.miles or 0 for load in loads)
                if total_miles > 0:
                    pay_items.append(
                        PayItemDetail(
                            type="miles",
                            amount=Decimal(str(total_miles)) * mileage_rule.rate,
                            meta={"miles": total_miles, "rate": float(mileage_rule.rate)},
                        )
                    )

            # Calculate percentage of load pay
            pct_rule = next((r for r in pay_rules if r.rule_type == PayRuleType.PERCENTAGE), None)
            if pct_rule:
                total_revenue = sum(load.revenue or 0 for load in loads)
                if total_revenue > 0:
                    percentage = pct_rule.additional.get("percent", 0.70) if pct_rule.additional else 0.70
                    pay_items.append(
                        PayItemDetail(
                            type="percentage",
                            amount=Decimal(str(total_revenue)) * Decimal(str(percentage)),
                            meta={
                                "revenue": float(total_revenue),
                                "percent": percentage,
                                "load_ids": [load.id for load in loads],
                            },
                        )
                    )

        # Calculate hourly/salary pay
        hourly_rule = next((r for r in pay_rules if r.rule_type == PayRuleType.HOURLY), None)
        if hourly_rule and worker.pay_default:
            hours = worker.pay_default.get("hours_worked", 0)
            if hours > 0:
                pay_items.append(
                    PayItemDetail(
                        type="hours",
                        amount=Decimal(str(hours)) * hourly_rule.rate,
                        meta={"hours": hours, "rate": float(hourly_rule.rate)},
                    )
                )

        salary_rule = next((r for r in pay_rules if r.rule_type == PayRuleType.SALARY), None)
        if salary_rule:
            # Calculate pay based on pay frequency (assume biweekly for now)
            pay_items.append(
                PayItemDetail(
                    type="salary",
                    amount=salary_rule.rate,
                    meta={"rate": float(salary_rule.rate), "frequency": "biweekly"},
                )
            )

        # Calculate gross
        gross = sum(item.amount for item in pay_items)

        # Get deductions
        deductions = await self._get_active_deductions(worker.id)
        deduction_items: List[PayItemDetail] = []

        for deduction in deductions:
            if deduction.amount:
                # Fixed amount deduction
                deduction_items.append(
                    PayItemDetail(
                        type="deduction",
                        amount=deduction.amount,
                        meta={"deduction_type": deduction.type, "frequency": deduction.frequency},
                    )
                )
            elif deduction.percentage:
                # Percentage deduction
                deduction_amount = gross * deduction.percentage
                deduction_items.append(
                    PayItemDetail(
                        type="deduction",
                        amount=deduction_amount,
                        meta={
                            "deduction_type": deduction.type,
                            "percentage": float(deduction.percentage),
                        },
                    )
                )

        total_deductions = sum(item.amount for item in deduction_items)
        net = gross - total_deductions

        # Ensure net is not negative
        if net < 0:
            net = Decimal("0")

        # Get owned equipment for owner-operators
        owned_equipment_ids = None
        if worker.type == "contractor":
            equipment = await self._get_owned_equipment(worker.id)
            owned_equipment_ids = [eq.id for eq in equipment] if equipment else None

        return SettlementPreview(
            worker_id=worker.id,
            worker_name=f"{worker.first_name} {worker.last_name}",
            worker_type=worker.type,
            gross=gross,
            total_deductions=total_deductions,
            net=net,
            details=pay_items + deduction_items,
            owned_equipment_ids=owned_equipment_ids,
        )

    async def _get_effective_pay_rules(
        self,
        worker_id: str,
        company_id: str,
        effective_date: date,
    ) -> List[PayRule]:
        """Get effective pay rules for worker (worker-specific or company defaults)."""
        result = await self.db.execute(
            select(PayRule).where(
                and_(
                    PayRule.worker_id == worker_id,
                    (PayRule.effective_from.is_(None)) | (PayRule.effective_from <= effective_date),
                    (PayRule.effective_to.is_(None)) | (PayRule.effective_to >= effective_date),
                )
            )
        )
        rules = result.scalars().all()

        # If no worker-specific rules, get company defaults
        if not rules:
            result = await self.db.execute(
                select(PayRule).where(
                    and_(
                        PayRule.company_id == company_id,
                        PayRule.worker_id.is_(None),
                        (PayRule.effective_from.is_(None)) | (PayRule.effective_from <= effective_date),
                        (PayRule.effective_to.is_(None)) | (PayRule.effective_to >= effective_date),
                    )
                )
            )
            rules = result.scalars().all()

        return list(rules)

    async def _get_driver_loads(
        self,
        driver_id: str,
        period_start: date,
        period_end: date,
    ) -> List[Load]:
        """Get loads for driver in pay period."""
        result = await self.db.execute(
            select(Load).where(
                and_(
                    Load.driver_id == driver_id,
                    Load.pickup_date >= period_start,
                    Load.pickup_date <= period_end,
                    Load.status.in_(["COMPLETED", "INVOICED", "PAID"]),
                )
            )
        )
        return result.scalars().all()

    async def _get_active_deductions(self, worker_id: str) -> List[Deduction]:
        """Get active deductions for worker."""
        result = await self.db.execute(
            select(Deduction).where(
                and_(
                    Deduction.worker_id == worker_id,
                    Deduction.is_active == "true",
                )
            )
        )
        return result.scalars().all()

    async def _get_owned_equipment(self, worker_id: str) -> List[Equipment]:
        """Get equipment owned by worker (owner-operator)."""
        result = await self.db.execute(
            select(Equipment).where(Equipment.owner_id == worker_id)
        )
        return result.scalars().all()

    async def create_payroll_run(
        self,
        company_id: str,
        user_id: str,
        request: PayrollRunCreate,
    ) -> PayrollRunResponse:
        """Create a new payroll run in draft status."""
        payroll_run = PayrollRun(
            id=str(uuid.uuid4()),
            company_id=company_id,
            pay_period_start=request.pay_period_start,
            pay_period_end=request.pay_period_end,
            run_by=user_id,
            status=PayrollRunStatus.DRAFT,
        )

        self.db.add(payroll_run)
        await self.db.commit()
        await self.db.refresh(payroll_run)

        return PayrollRunResponse.model_validate(payroll_run)

    async def approve_payroll(
        self,
        payroll_id: str,
        approver_id: str,
    ) -> PayrollRunResponse:
        """Approve a payroll run."""
        result = await self.db.execute(
            select(PayrollRun).where(PayrollRun.id == payroll_id)
        )
        payroll_run = result.scalar_one_or_none()

        if not payroll_run:
            raise ValueError("Payroll run not found")

        if payroll_run.status != PayrollRunStatus.PREVIEW:
            raise ValueError(f"Can only approve payroll in preview status, current: {payroll_run.status}")

        payroll_run.status = PayrollRunStatus.APPROVED
        payroll_run.approved_by = approver_id
        payroll_run.approved_at = datetime.now()

        await self.db.commit()
        await self.db.refresh(payroll_run)

        return PayrollRunResponse.model_validate(payroll_run)
