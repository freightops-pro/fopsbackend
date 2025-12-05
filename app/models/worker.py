"""Worker and payroll-related models."""
from sqlalchemy import Column, Date, DateTime, Enum, Float, ForeignKey, JSON, Numeric, String, Text, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class WorkerType(str, enum.Enum):
    """Worker employment type."""
    EMPLOYEE = "employee"
    CONTRACTOR = "contractor"


class WorkerRole(str, enum.Enum):
    """Worker role in the company."""
    DRIVER = "driver"
    OFFICE = "office"
    MECHANIC = "mechanic"
    DISPATCHER = "dispatcher"
    OTHER = "other"


class WorkerStatus(str, enum.Enum):
    """Worker status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    TERMINATED = "terminated"


class DocumentType(str, enum.Enum):
    """Document types."""
    W4 = "W4"
    W9 = "W9"
    I9 = "I9"
    CDL = "CDL"
    MEDCARD = "MEDCARD"
    SSN = "SSN"
    LICENSE = "LICENSE"
    OTHER = "OTHER"


class PayRuleType(str, enum.Enum):
    """Pay rule calculation type."""
    HOURLY = "hourly"
    SALARY = "salary"
    MILEAGE = "mileage"
    PERCENTAGE = "percentage"
    PIECE = "piece"


class PayItemType(str, enum.Enum):
    """Pay item type."""
    MILES = "miles"
    HOURS = "hours"
    BONUS = "bonus"
    ACCESSORIAL = "accessorial"
    REIMBURSEMENT = "reimbursement"
    DEDUCTION = "deduction"
    PERCENTAGE = "percentage"


class DeductionType(str, enum.Enum):
    """Deduction type."""
    TAX = "tax"
    BENEFIT = "benefit"
    ESCROW = "escrow"
    FUEL_CARD = "fuel_card"
    LEASE = "lease"
    GARNISHMENT = "garnishment"
    ADVANCE = "advance"


class DeductionFrequency(str, enum.Enum):
    """Deduction frequency."""
    PER_PAYROLL = "per_payroll"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ONE_TIME = "one_time"


class PayrollRunStatus(str, enum.Enum):
    """Payroll run status."""
    DRAFT = "draft"
    PREVIEW = "preview"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    FAILED = "failed"


class Worker(Base):
    """Worker model - supports both employees and contractors."""
    __tablename__ = "worker"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    type = Column(Enum(WorkerType, values_callable=lambda x: [e.value for e in x], native_enum=True, create_constraint=False), nullable=False, default=WorkerType.EMPLOYEE)
    role = Column(Enum(WorkerRole, values_callable=lambda x: [e.value for e in x], native_enum=True, create_constraint=False), nullable=False, default=WorkerRole.OTHER)

    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    # Tax information (encrypted in application layer)
    tax_id = Column(Text, nullable=True)  # SSN or EIN
    tax_form_status = Column(JSON, nullable=True)  # W4/W9/I9 statuses

    # Pay settings
    pay_default = Column(JSON, nullable=True)  # Default pay rule, rates

    # Bank info reference (if stored separately)
    bank_info = Column(JSON, nullable=True)  # Direct deposit info

    # Gusto integration
    gusto_id = Column(String, nullable=True, unique=True)
    gusto_employee_id = Column(String, nullable=True)
    gusto_contractor_id = Column(String, nullable=True)

    status = Column(Enum(WorkerStatus, values_callable=lambda x: [e.value for e in x], native_enum=True, create_constraint=False), nullable=False, default=WorkerStatus.ACTIVE)

    # Dates
    hire_date = Column(Date, nullable=True)
    termination_date = Column(Date, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Company", back_populates="workers")
    documents = relationship("WorkerDocument", back_populates="worker", cascade="all, delete-orphan")
    pay_rules = relationship("PayRule", back_populates="worker", cascade="all, delete-orphan")
    deductions = relationship("Deduction", back_populates="worker", cascade="all, delete-orphan")
    settlements = relationship("PayrollSettlement", back_populates="worker", cascade="all, delete-orphan")
    owned_equipment = relationship("Equipment", foreign_keys="Equipment.owner_id", backref="owner")


class WorkerDocument(Base):
    """Worker documents (W4, CDL, etc.)."""
    __tablename__ = "worker_document"

    id = Column(String, primary_key=True)
    worker_id = Column(String, ForeignKey("worker.id"), nullable=False, index=True)

    doc_type = Column(Enum(DocumentType), nullable=False)
    file_url = Column(String, nullable=False)

    expires_at = Column(Date, nullable=True)
    uploaded_by = Column(String, ForeignKey("user.id"), nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    worker = relationship("Worker", back_populates="documents")


class PayRule(Base):
    """Pay rules for workers."""
    __tablename__ = "pay_rule"

    id = Column(String, primary_key=True)
    worker_id = Column(String, ForeignKey("worker.id"), nullable=True, index=True)  # Null = company default
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    rule_type = Column(Enum(PayRuleType), nullable=False)
    rate = Column(Numeric(10, 4), nullable=False)

    # Additional configuration (e.g., percentage of load revenue)
    additional = Column(JSON, nullable=True)

    effective_from = Column(Date, nullable=True)
    effective_to = Column(Date, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    worker = relationship("Worker", back_populates="pay_rules")


class PayrollRun(Base):
    """Payroll run."""
    __tablename__ = "payroll_run"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    pay_period_start = Column(Date, nullable=False)
    pay_period_end = Column(Date, nullable=False)

    run_by = Column(String, ForeignKey("user.id"), nullable=True)
    approved_by = Column(String, ForeignKey("user.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    status = Column(Enum(PayrollRunStatus), nullable=False, default=PayrollRunStatus.DRAFT)

    # Aggregated totals
    totals = Column(JSON, nullable=True)

    # Gusto integration
    gusto_payroll_id = Column(String, nullable=True)
    gusto_status = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    submitted_at = Column(DateTime, nullable=True)

    # Relationships
    settlements = relationship("PayrollSettlement", back_populates="payroll_run", cascade="all, delete-orphan")
    pay_items = relationship("PayItem", back_populates="payroll_run", cascade="all, delete-orphan")


class PayItem(Base):
    """Individual pay items (miles, hours, bonuses, deductions)."""
    __tablename__ = "pay_item"

    id = Column(String, primary_key=True)
    payroll_run_id = Column(String, ForeignKey("payroll_run.id"), nullable=False, index=True)
    worker_id = Column(String, ForeignKey("worker.id"), nullable=False, index=True)

    type = Column(Enum(PayItemType), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)

    # Metadata (e.g., miles, rate, load_id)
    meta = Column(JSON, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    payroll_run = relationship("PayrollRun", back_populates="pay_items")


class PayrollSettlement(Base):
    """Worker settlement (per payroll run)."""
    __tablename__ = "settlement"

    id = Column(String, primary_key=True)
    payroll_run_id = Column(String, ForeignKey("payroll_run.id"), nullable=False, index=True)
    worker_id = Column(String, ForeignKey("worker.id"), nullable=False, index=True)

    gross = Column(Numeric(10, 2), nullable=False, default=0)
    total_deductions = Column(Numeric(10, 2), nullable=False, default=0)
    net = Column(Numeric(10, 2), nullable=False, default=0)

    # Detailed breakdown
    details = Column(JSON, nullable=True)

    # Gusto integration
    gusto_payment_id = Column(String, nullable=True)
    gusto_status = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    payroll_run = relationship("PayrollRun", back_populates="settlements")
    worker = relationship("Worker", back_populates="settlements")


class Deduction(Base):
    """Worker deductions."""
    __tablename__ = "deduction"

    id = Column(String, primary_key=True)
    worker_id = Column(String, ForeignKey("worker.id"), nullable=False, index=True)

    type = Column(Enum(DeductionType), nullable=False)
    amount = Column(Numeric(10, 2), nullable=True)  # Fixed amount
    percentage = Column(Numeric(5, 4), nullable=True)  # Percentage (e.g., 0.05 = 5%)

    frequency = Column(Enum(DeductionFrequency), nullable=False, default=DeductionFrequency.PER_PAYROLL)

    # Additional metadata
    meta = Column(JSON, nullable=True)

    is_active = Column(String, nullable=False, default="true")

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    worker = relationship("Worker", back_populates="deductions")


class GustoSync(Base):
    """Gusto API sync audit log."""
    __tablename__ = "gusto_sync"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    entity_type = Column(String, nullable=False)  # employee, contractor, payroll, payment
    entity_id = Column(String, nullable=True)

    request_payload = Column(JSON, nullable=True)
    response_payload = Column(JSON, nullable=True)

    status = Column(String, nullable=False)
    error_message = Column(Text, nullable=True)

    run_at = Column(DateTime, nullable=False, server_default=func.now())
