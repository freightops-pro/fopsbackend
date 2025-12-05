"""Worker and payroll schemas."""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


# Worker schemas
class WorkerBase(BaseModel):
    type: str  # employee, contractor
    role: str  # driver, office, mechanic, dispatcher, other
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    hire_date: Optional[date] = None


class WorkerCreate(WorkerBase):
    tax_id: Optional[str] = None  # Will be encrypted
    bank_info: Optional[Dict[str, Any]] = None
    pay_default: Optional[Dict[str, Any]] = None


class WorkerUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    pay_default: Optional[Dict[str, Any]] = None
    bank_info: Optional[Dict[str, Any]] = None


class WorkerResponse(WorkerBase):
    id: str
    company_id: str
    status: str
    gusto_id: Optional[str] = None
    termination_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Pay Rule schemas
class PayRuleCreate(BaseModel):
    rule_type: str  # hourly, salary, mileage, percentage, piece
    rate: Decimal
    additional: Optional[Dict[str, Any]] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


class PayRuleResponse(PayRuleCreate):
    id: str
    worker_id: Optional[str]
    company_id: str
    created_at: datetime

    class Config:
        from_attributes = True


# Deduction schemas
class DeductionCreate(BaseModel):
    type: str  # tax, benefit, escrow, fuel_card, lease, garnishment, advance
    amount: Optional[Decimal] = None
    percentage: Optional[Decimal] = None
    frequency: str  # per_payroll, weekly, monthly, one_time
    meta: Optional[Dict[str, Any]] = None


class DeductionResponse(DeductionCreate):
    id: str
    worker_id: str
    is_active: str
    created_at: datetime

    class Config:
        from_attributes = True


# Payroll Run schemas
class PayrollPreviewRequest(BaseModel):
    company_id: str
    period_start: date
    period_end: date
    filters: Optional[Dict[str, Any]] = None


class PayItemDetail(BaseModel):
    type: str  # miles, hours, bonus, accessorial, reimbursement, deduction, percentage
    amount: Decimal
    meta: Optional[Dict[str, Any]] = None


class SettlementPreview(BaseModel):
    worker_id: str
    worker_name: str
    worker_type: str
    gross: Decimal
    total_deductions: Decimal
    net: Decimal
    details: List[PayItemDetail]
    owned_equipment_ids: Optional[List[str]] = None  # For owner-operators


class PayrollPreviewResponse(BaseModel):
    company_id: str
    period_start: date
    period_end: date
    settlements: List[SettlementPreview]
    totals: Dict[str, Any]


class PayrollRunCreate(BaseModel):
    pay_period_start: date
    pay_period_end: date


class PayrollRunResponse(BaseModel):
    id: str
    company_id: str
    pay_period_start: date
    pay_period_end: date
    status: str
    run_by: Optional[str]
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    totals: Optional[Dict[str, Any]]
    gusto_payroll_id: Optional[str]
    gusto_status: Optional[str]
    created_at: datetime
    submitted_at: Optional[datetime]

    class Config:
        from_attributes = True


# Settlement schemas
class SettlementResponse(BaseModel):
    id: str
    payroll_run_id: str
    worker_id: str
    gross: Decimal
    total_deductions: Decimal
    net: Decimal
    details: Optional[Dict[str, Any]]
    gusto_payment_id: Optional[str]
    gusto_status: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class SettlementDetailResponse(SettlementResponse):
    worker: WorkerResponse
    owned_equipment: Optional[List[Dict[str, Any]]] = None  # For owner-operators


# Worker Document schemas
class WorkerDocumentCreate(BaseModel):
    doc_type: str  # W4, W9, I9, CDL, MEDCARD, etc.
    file_url: str
    expires_at: Optional[date] = None


class WorkerDocumentResponse(WorkerDocumentCreate):
    id: str
    worker_id: str
    uploaded_by: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Worker Profile (detailed view)
class WorkerProfileResponse(WorkerResponse):
    documents: List[WorkerDocumentResponse] = []
    pay_rules: List[PayRuleResponse] = []
    deductions: List[DeductionResponse] = []
    owned_equipment_count: int = 0
    recent_settlements: List[SettlementResponse] = []
