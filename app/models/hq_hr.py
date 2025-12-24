"""HQ HR and Payroll models (Check integration)."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    JSON,
    func,
)
from sqlalchemy.orm import relationship

from app.core.db import Base


# ============================================================================
# Enums
# ============================================================================

class EmploymentType(enum.Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACTOR = "contractor"
    INTERN = "intern"


class HREmployeeStatus(enum.Enum):
    ACTIVE = "active"
    TERMINATED = "terminated"
    ON_LEAVE = "on_leave"
    ONBOARDING = "onboarding"


class PayFrequency(enum.Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    SEMIMONTHLY = "semimonthly"
    MONTHLY = "monthly"


class PayrollStatus(enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============================================================================
# HR Employee Model
# ============================================================================

class HQHREmployee(Base):
    """HR employee for payroll (distinct from HQEmployee admin users)."""

    __tablename__ = "hq_hr_employee"

    id = Column(String(36), primary_key=True)
    employee_number = Column(String(20), unique=True, nullable=False)

    # Personal info
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)

    # Employment details
    employment_type = Column(Enum(EmploymentType), default=EmploymentType.FULL_TIME, nullable=False)
    status = Column(Enum(HREmployeeStatus), default=HREmployeeStatus.ONBOARDING, nullable=False)
    department = Column(String(100), nullable=True)
    job_title = Column(String(100), nullable=True)
    manager_id = Column(String(36), ForeignKey("hq_hr_employee.id"), nullable=True)

    hire_date = Column(DateTime, nullable=True)
    termination_date = Column(DateTime, nullable=True)

    # Compensation
    pay_frequency = Column(Enum(PayFrequency), default=PayFrequency.BIWEEKLY, nullable=False)
    annual_salary = Column(Numeric(12, 2), nullable=True)
    hourly_rate = Column(Numeric(8, 2), nullable=True)

    # Address
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(20), nullable=True)

    # Check integration
    check_employee_id = Column(String(100), nullable=True, unique=True)

    # Sensitive data - would be encrypted in production
    ssn_last_four = Column(String(4), nullable=True)
    date_of_birth = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    manager = relationship("HQHREmployee", remote_side=[id], backref="direct_reports")
    payroll_items = relationship("HQPayrollItem", back_populates="employee")


# ============================================================================
# Payroll Run Model
# ============================================================================

class HQPayrollRun(Base):
    """Payroll run for processing employee payments."""

    __tablename__ = "hq_payroll_run"

    id = Column(String(36), primary_key=True)
    payroll_number = Column(String(20), unique=True, nullable=False)

    status = Column(Enum(PayrollStatus), default=PayrollStatus.DRAFT, nullable=False)

    pay_period_start = Column(DateTime, nullable=False)
    pay_period_end = Column(DateTime, nullable=False)
    pay_date = Column(DateTime, nullable=False)

    description = Column(Text, nullable=True)

    # Totals
    total_gross = Column(Numeric(14, 2), default=0, nullable=False)
    total_taxes = Column(Numeric(14, 2), default=0, nullable=False)
    total_deductions = Column(Numeric(14, 2), default=0, nullable=False)
    total_net = Column(Numeric(14, 2), default=0, nullable=False)
    employee_count = Column(Integer, default=0, nullable=False)

    # Check integration
    check_payroll_id = Column(String(100), nullable=True, unique=True)

    # Approval workflow
    approved_by_id = Column(String(36), ForeignKey("hq_employee.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    processed_at = Column(DateTime, nullable=True)

    created_by_id = Column(String(36), ForeignKey("hq_employee.id"), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    approved_by = relationship("HQEmployee", foreign_keys=[approved_by_id])
    created_by = relationship("HQEmployee", foreign_keys=[created_by_id])
    items = relationship("HQPayrollItem", back_populates="payroll_run")


# ============================================================================
# Payroll Item Model
# ============================================================================

class HQPayrollItem(Base):
    """Individual employee payroll line within a payroll run."""

    __tablename__ = "hq_payroll_item"

    id = Column(String(36), primary_key=True)
    payroll_run_id = Column(String(36), ForeignKey("hq_payroll_run.id"), nullable=False)
    employee_id = Column(String(36), ForeignKey("hq_hr_employee.id"), nullable=False)

    # Earnings
    gross_pay = Column(Numeric(12, 2), default=0, nullable=False)
    regular_hours = Column(Numeric(6, 2), nullable=True)
    overtime_hours = Column(Numeric(6, 2), nullable=True)
    regular_pay = Column(Numeric(12, 2), default=0, nullable=False)
    overtime_pay = Column(Numeric(12, 2), default=0, nullable=False)
    bonus = Column(Numeric(12, 2), default=0, nullable=False)

    # Taxes
    federal_tax = Column(Numeric(10, 2), default=0, nullable=False)
    state_tax = Column(Numeric(10, 2), default=0, nullable=False)
    social_security = Column(Numeric(10, 2), default=0, nullable=False)
    medicare = Column(Numeric(10, 2), default=0, nullable=False)
    local_tax = Column(Numeric(10, 2), default=0, nullable=False)

    # Deductions
    health_insurance = Column(Numeric(10, 2), default=0, nullable=False)
    dental_insurance = Column(Numeric(10, 2), default=0, nullable=False)
    vision_insurance = Column(Numeric(10, 2), default=0, nullable=False)
    retirement_401k = Column(Numeric(10, 2), default=0, nullable=False)
    other_deductions = Column(Numeric(10, 2), default=0, nullable=False)

    # Net
    net_pay = Column(Numeric(12, 2), default=0, nullable=False)

    # Check integration
    check_paystub_id = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    payroll_run = relationship("HQPayrollRun", back_populates="items")
    employee = relationship("HQHREmployee", back_populates="payroll_items")
