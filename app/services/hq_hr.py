"""HQ HR and Payroll Service."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.hq_hr import (
    HQHREmployee,
    HQPayrollRun,
    HQPayrollItem,
    EmploymentType,
    HREmployeeStatus,
    PayFrequency,
    PayrollStatus,
)
from app.schemas.hq import (
    HQHREmployeeCreate,
    HQHREmployeeUpdate,
    HQPayrollRunCreate,
)


class HQHREmployeeService:
    """Service for managing HQ HR employees (payroll employees)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_employees(
        self,
        status: Optional[str] = None,
        department: Optional[str] = None,
        employment_type: Optional[str] = None,
    ) -> List[HQHREmployee]:
        """List all HR employees with optional filters."""
        query = select(HQHREmployee).order_by(HQHREmployee.last_name)

        if status:
            try:
                status_enum = HREmployeeStatus(status)
                query = query.where(HQHREmployee.status == status_enum)
            except ValueError:
                pass

        if department:
            query = query.where(HQHREmployee.department == department)

        if employment_type:
            try:
                type_enum = EmploymentType(employment_type)
                query = query.where(HQHREmployee.employment_type == type_enum)
            except ValueError:
                pass

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_employee(self, employee_id: str) -> Optional[HQHREmployee]:
        """Get a single HR employee by ID."""
        return await self.db.get(HQHREmployee, employee_id)

    async def get_employee_by_number(self, employee_number: str) -> Optional[HQHREmployee]:
        """Get HR employee by employee number."""
        result = await self.db.execute(
            select(HQHREmployee).where(HQHREmployee.employee_number == employee_number)
        )
        return result.scalar_one_or_none()

    async def create_employee(self, payload: HQHREmployeeCreate) -> HQHREmployee:
        """Create a new HR employee."""
        # Generate employee number
        result = await self.db.execute(
            select(func.count(HQHREmployee.id))
        )
        count = result.scalar() or 0
        employee_number = f"HR{str(count + 1).zfill(5)}"

        employee = HQHREmployee(
            id=str(uuid.uuid4()),
            employee_number=employee_number,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone=payload.phone,
            employment_type=EmploymentType(payload.employment_type) if payload.employment_type else EmploymentType.FULL_TIME,
            status=HREmployeeStatus.ONBOARDING,
            department=payload.department,
            job_title=payload.job_title,
            manager_id=payload.manager_id,
            hire_date=payload.hire_date,
            pay_frequency=PayFrequency(payload.pay_frequency) if payload.pay_frequency else PayFrequency.BIWEEKLY,
            annual_salary=payload.annual_salary,
            hourly_rate=payload.hourly_rate,
            address_line1=payload.address_line1,
            address_line2=payload.address_line2,
            city=payload.city,
            state=payload.state,
            zip_code=payload.zip_code,
            ssn_last_four=payload.ssn_last_four,
            date_of_birth=payload.date_of_birth,
        )

        self.db.add(employee)
        await self.db.commit()
        await self.db.refresh(employee)
        return employee

    async def update_employee(
        self, employee_id: str, payload: HQHREmployeeUpdate
    ) -> HQHREmployee:
        """Update an HR employee."""
        employee = await self.get_employee(employee_id)
        if not employee:
            raise ValueError("Employee not found")

        update_data = payload.model_dump(exclude_unset=True)

        # Handle enum conversions
        if "employment_type" in update_data and update_data["employment_type"]:
            update_data["employment_type"] = EmploymentType(update_data["employment_type"])
        if "status" in update_data and update_data["status"]:
            update_data["status"] = HREmployeeStatus(update_data["status"])
        if "pay_frequency" in update_data and update_data["pay_frequency"]:
            update_data["pay_frequency"] = PayFrequency(update_data["pay_frequency"])

        for key, value in update_data.items():
            if hasattr(employee, key):
                setattr(employee, key, value)

        await self.db.commit()
        await self.db.refresh(employee)
        return employee

    async def terminate_employee(
        self, employee_id: str, termination_date: Optional[datetime] = None
    ) -> HQHREmployee:
        """Terminate an HR employee."""
        employee = await self.get_employee(employee_id)
        if not employee:
            raise ValueError("Employee not found")

        employee.status = HREmployeeStatus.TERMINATED
        employee.termination_date = termination_date or datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(employee)
        return employee

    async def get_hr_stats(self) -> dict:
        """Get HR statistics."""
        total_result = await self.db.execute(select(func.count(HQHREmployee.id)))
        total = total_result.scalar() or 0

        active_result = await self.db.execute(
            select(func.count(HQHREmployee.id)).where(
                HQHREmployee.status == HREmployeeStatus.ACTIVE
            )
        )
        active = active_result.scalar() or 0

        onboarding_result = await self.db.execute(
            select(func.count(HQHREmployee.id)).where(
                HQHREmployee.status == HREmployeeStatus.ONBOARDING
            )
        )
        onboarding = onboarding_result.scalar() or 0

        salary_result = await self.db.execute(
            select(func.sum(HQHREmployee.annual_salary)).where(
                HQHREmployee.status == HREmployeeStatus.ACTIVE
            )
        )
        total_salary = salary_result.scalar() or Decimal("0")

        return {
            "total_employees": total,
            "active_employees": active,
            "onboarding": onboarding,
            "total_annual_salary": float(total_salary),
        }


class HQPayrollService:
    """Service for managing HQ payroll runs."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_payroll_runs(
        self, status: Optional[str] = None, limit: int = 50
    ) -> List[HQPayrollRun]:
        """List all payroll runs."""
        query = select(HQPayrollRun).order_by(HQPayrollRun.pay_date.desc()).limit(limit)

        if status:
            try:
                status_enum = PayrollStatus(status)
                query = query.where(HQPayrollRun.status == status_enum)
            except ValueError:
                pass

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_payroll_run(self, payroll_id: str) -> Optional[HQPayrollRun]:
        """Get a single payroll run by ID."""
        result = await self.db.execute(
            select(HQPayrollRun)
            .options(selectinload(HQPayrollRun.items))
            .where(HQPayrollRun.id == payroll_id)
        )
        return result.scalar_one_or_none()

    async def create_payroll_run(
        self, payload: HQPayrollRunCreate, created_by_id: str
    ) -> HQPayrollRun:
        """Create a new payroll run with items for all active employees."""
        # Generate payroll number
        result = await self.db.execute(
            select(func.count(HQPayrollRun.id))
        )
        count = result.scalar() or 0
        payroll_number = f"PR{datetime.utcnow().strftime('%Y%m')}-{str(count + 1).zfill(4)}"

        payroll = HQPayrollRun(
            id=str(uuid.uuid4()),
            payroll_number=payroll_number,
            status=PayrollStatus.DRAFT,
            pay_period_start=payload.pay_period_start,
            pay_period_end=payload.pay_period_end,
            pay_date=payload.pay_date,
            description=payload.description,
            created_by_id=created_by_id,
        )

        self.db.add(payroll)

        # Get employees to include
        if payload.employee_ids:
            employees_result = await self.db.execute(
                select(HQHREmployee).where(
                    HQHREmployee.id.in_(payload.employee_ids),
                    HQHREmployee.status == HREmployeeStatus.ACTIVE,
                )
            )
        else:
            employees_result = await self.db.execute(
                select(HQHREmployee).where(
                    HQHREmployee.status == HREmployeeStatus.ACTIVE
                )
            )
        employees = list(employees_result.scalars().all())

        total_gross = Decimal("0")
        total_taxes = Decimal("0")
        total_deductions = Decimal("0")
        total_net = Decimal("0")

        for emp in employees:
            # Calculate pay for this period
            if emp.annual_salary:
                # Salaried employee
                if emp.pay_frequency == PayFrequency.WEEKLY:
                    gross_pay = emp.annual_salary / 52
                elif emp.pay_frequency == PayFrequency.BIWEEKLY:
                    gross_pay = emp.annual_salary / 26
                elif emp.pay_frequency == PayFrequency.SEMIMONTHLY:
                    gross_pay = emp.annual_salary / 24
                else:  # Monthly
                    gross_pay = emp.annual_salary / 12
            elif emp.hourly_rate:
                # Hourly - assume 80 hours for biweekly
                gross_pay = emp.hourly_rate * Decimal("80")
            else:
                gross_pay = Decimal("0")

            # Calculate taxes (simplified)
            federal_tax = gross_pay * Decimal("0.22")
            state_tax = gross_pay * Decimal("0.05")
            social_security = gross_pay * Decimal("0.062")
            medicare = gross_pay * Decimal("0.0145")

            # Benefits deductions (placeholder)
            health_insurance = Decimal("250")
            dental_insurance = Decimal("25")
            vision_insurance = Decimal("10")
            retirement_401k = gross_pay * Decimal("0.05")

            taxes = federal_tax + state_tax + social_security + medicare
            deductions = health_insurance + dental_insurance + vision_insurance + retirement_401k
            net_pay = gross_pay - taxes - deductions

            item = HQPayrollItem(
                id=str(uuid.uuid4()),
                payroll_run_id=payroll.id,
                employee_id=emp.id,
                gross_pay=gross_pay,
                regular_pay=gross_pay,
                overtime_pay=Decimal("0"),
                bonus=Decimal("0"),
                federal_tax=federal_tax,
                state_tax=state_tax,
                social_security=social_security,
                medicare=medicare,
                local_tax=Decimal("0"),
                health_insurance=health_insurance,
                dental_insurance=dental_insurance,
                vision_insurance=vision_insurance,
                retirement_401k=retirement_401k,
                other_deductions=Decimal("0"),
                net_pay=net_pay,
            )

            self.db.add(item)

            total_gross += gross_pay
            total_taxes += taxes
            total_deductions += deductions
            total_net += net_pay

        payroll.total_gross = total_gross
        payroll.total_taxes = total_taxes
        payroll.total_deductions = total_deductions
        payroll.total_net = total_net
        payroll.employee_count = len(employees)

        await self.db.commit()
        await self.db.refresh(payroll)
        return payroll

    async def submit_for_approval(self, payroll_id: str) -> HQPayrollRun:
        """Submit a payroll run for approval."""
        payroll = await self.get_payroll_run(payroll_id)
        if not payroll:
            raise ValueError("Payroll run not found")

        if payroll.status != PayrollStatus.DRAFT:
            raise ValueError("Only draft payroll runs can be submitted for approval")

        payroll.status = PayrollStatus.PENDING_APPROVAL
        await self.db.commit()
        await self.db.refresh(payroll)
        return payroll

    async def approve_payroll(self, payroll_id: str, approved_by_id: str) -> HQPayrollRun:
        """Approve a payroll run."""
        payroll = await self.get_payroll_run(payroll_id)
        if not payroll:
            raise ValueError("Payroll run not found")

        if payroll.status != PayrollStatus.PENDING_APPROVAL:
            raise ValueError("Only pending payroll runs can be approved")

        payroll.status = PayrollStatus.APPROVED
        payroll.approved_by_id = approved_by_id
        payroll.approved_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(payroll)
        return payroll

    async def process_payroll(self, payroll_id: str) -> HQPayrollRun:
        """Process an approved payroll run."""
        payroll = await self.get_payroll_run(payroll_id)
        if not payroll:
            raise ValueError("Payroll run not found")

        if payroll.status != PayrollStatus.APPROVED:
            raise ValueError("Only approved payroll runs can be processed")

        payroll.status = PayrollStatus.PROCESSING
        await self.db.commit()

        # Here you would integrate with Check or another payroll provider
        # For now, we'll mark it as completed

        payroll.status = PayrollStatus.COMPLETED
        payroll.processed_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(payroll)
        return payroll

    async def cancel_payroll(self, payroll_id: str) -> HQPayrollRun:
        """Cancel a payroll run."""
        payroll = await self.get_payroll_run(payroll_id)
        if not payroll:
            raise ValueError("Payroll run not found")

        if payroll.status in [PayrollStatus.COMPLETED, PayrollStatus.PROCESSING]:
            raise ValueError("Cannot cancel a completed or processing payroll run")

        payroll.status = PayrollStatus.CANCELLED
        await self.db.commit()
        await self.db.refresh(payroll)
        return payroll

    async def get_payroll_items(self, payroll_id: str) -> List[HQPayrollItem]:
        """Get all items for a payroll run."""
        result = await self.db.execute(
            select(HQPayrollItem)
            .options(selectinload(HQPayrollItem.employee))
            .where(HQPayrollItem.payroll_run_id == payroll_id)
        )
        return list(result.scalars().all())

    async def get_payroll_stats(self) -> dict:
        """Get payroll statistics."""
        # Total payrolls
        total_result = await self.db.execute(select(func.count(HQPayrollRun.id)))
        total = total_result.scalar() or 0

        # Pending payrolls
        pending_result = await self.db.execute(
            select(func.count(HQPayrollRun.id)).where(
                HQPayrollRun.status == PayrollStatus.PENDING_APPROVAL
            )
        )
        pending = pending_result.scalar() or 0

        # YTD totals
        year_start = datetime(datetime.utcnow().year, 1, 1)
        ytd_result = await self.db.execute(
            select(
                func.sum(HQPayrollRun.total_gross),
                func.sum(HQPayrollRun.total_taxes),
                func.sum(HQPayrollRun.total_net),
            ).where(
                HQPayrollRun.status == PayrollStatus.COMPLETED,
                HQPayrollRun.pay_date >= year_start,
            )
        )
        ytd = ytd_result.one()

        # Last payroll
        last_result = await self.db.execute(
            select(HQPayrollRun)
            .where(HQPayrollRun.status == PayrollStatus.COMPLETED)
            .order_by(HQPayrollRun.pay_date.desc())
            .limit(1)
        )
        last_payroll = last_result.scalar_one_or_none()

        return {
            "total_payrolls": total,
            "pending_approval": pending,
            "ytd_gross": float(ytd[0] or 0),
            "ytd_taxes": float(ytd[1] or 0),
            "ytd_net": float(ytd[2] or 0),
            "last_payroll_date": last_payroll.pay_date.isoformat() if last_payroll else None,
            "last_payroll_amount": float(last_payroll.total_net) if last_payroll else 0,
        }
