from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel

class PayrollEntryOut(BaseModel):
    id: int
    employee_id: str
    employee_name: str
    position: Optional[str]
    department: Optional[str]
    hourly_rate: Optional[float] = 0
    regular_hours: float
    overtime_hours: float
    bonus_amount: float = 0
    mileage: float
    per_diem: float
    gross_pay: float
    health_insurance: Optional[float] = 0
    total_deductions: float
    net_pay: float
    status: str
    pay_period: Optional[str]
    has_w2: bool
    has_1099: bool
    class Config:
        from_attributes = True

class PayrollRunOut(BaseModel):
    id: int
    pay_period_start: date
    pay_period_end: date
    pay_date: date
    payroll_type: str
    departments: List[str]
    notes: Optional[str]
    status: str
    created_at: datetime
    entries: List[PayrollEntryOut]
    class Config:
        from_attributes = True

class PayrollRunCreate(BaseModel):
    payPeriodStart: date
    payPeriodEnd: date
    payDate: date
    payrollType: str
    departments: List[str]
    notes: Optional[str] = None
    draft: bool = True

class PayrollEntryUpdate(BaseModel):
    regular_hours: Optional[float] = None
    overtime_hours: Optional[float] = None
    bonus_amount: Optional[float] = None
    mileage: Optional[float] = None
    per_diem: Optional[float] = None

class PaginatedPayrollEntries(BaseModel):
    total: int
    page: int
    pageSize: int
    entries: List[PayrollEntryOut]

class PayrollSummary(BaseModel):
    totalPayroll: float
    totalEmployees: int
    taxesWithheld: float
    benefitsCost: float
    w2sGenerated: int
    quarterlyTaxes: float
    upcomingPayroll: Optional[str]
    lastProcessed: Optional[str]

class OvertimeApprovalCreate(BaseModel):
    employeeId: str
    overtimeHours: float
    overtimeRate: float
    approvalReason: str
    weekEnding: date

class BonusProcessingCreate(BaseModel):
    employeeIds: List[str]
    bonusType: str
    bonusAmount: float
    taxWithholding: str
    bonusReason: str
    effectiveDate: date

class DriverSettlementCreate(BaseModel):
    driverId: str
    settlementPeriod: str
    totalMiles: float
    mileageRate: float
    detentionHours: Optional[float] = None
    detentionRate: Optional[float] = None
    fuelSurcharge: Optional[float] = None
    otherDeductions: Optional[float] = None
    notes: Optional[str] = None

# Settlement Request Schemas
class SettlementRequestData(BaseModel):
    actualMiles: float
    actualHours: float
    detentionHours: Optional[float] = 0
    fuelSurcharge: Optional[float] = 0
    otherDeductions: Optional[float] = 0
    notes: Optional[str] = None

class DriverInfo(BaseModel):
    firstName: str
    lastName: str
    payRate: float
    payType: str

class LoadDetails(BaseModel):
    loadNumber: str
    pickupLocation: str
    deliveryLocation: str
    estimatedMiles: int
    estimatedDuration: float

class CompletedData(BaseModel):
    actualMiles: float
    actualHours: float
    detentionHours: float
    fuelSurcharge: float

class SettlementCalculation(BaseModel):
    mileagePay: float
    hourlyPay: float
    detentionPay: float
    fuelSurcharge: float
    totalSettlement: float

class SettlementRates(BaseModel):
    mileageRate: float
    hourlyRate: float
    detentionRate: float

class SettlementRequestResponse(BaseModel):
    loadId: str
    driverId: str
    driverInfo: DriverInfo
    loadDetails: LoadDetails
    completedData: Optional[CompletedData] = None
    settlementCalculation: Optional[SettlementCalculation] = None
    rates: SettlementRates

class SettlementSubmissionResponse(BaseModel):
    settlementId: str
    status: str
    totalSettlement: float
    breakdown: SettlementCalculation
