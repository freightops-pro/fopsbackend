from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from fastapi import Query, Path
from app.config.db import get_db
from app.schema.payrollSchema import (
    PayrollRunCreate, PayrollRunOut, PayrollSummary,
    OvertimeApprovalCreate, BonusProcessingCreate, DriverSettlementCreate,
    PaginatedPayrollEntries, PayrollEntryUpdate, PayrollEntryOut
)
from app.services.payroll_service import (
    create_payroll_run, list_payroll_runs, get_payroll_run, payroll_summary,
    record_overtime, record_bonus, create_settlement, paginate_entries, update_entry, finalize_run
)

router = APIRouter(prefix="/api/hr/payroll", tags=["HR - Payroll"])

@router.post("/run", response_model=PayrollRunOut, status_code=201)
def run_payroll(payload: PayrollRunCreate, db: Session = Depends(get_db)):
    run = create_payroll_run(db, payload)
    return PayrollRunOut(
        id=run.id,
        pay_period_start=run.pay_period_start,
        pay_period_end=run.pay_period_end,
        pay_date=run.pay_date,
        payroll_type=run.payroll_type,
        departments=run.departments.split(",") if run.departments else [],
        notes=run.notes,
        status=run.status,
        created_at=run.created_at,
        entries=run.entries,
    )

@router.get("", response_model=List[PayrollRunOut])
def list_runs(db: Session = Depends(get_db)):
    runs = list_payroll_runs(db)
    result = []
    for run in runs:
        result.append(PayrollRunOut(
            id=run.id,
            pay_period_start=run.pay_period_start,
            pay_period_end=run.pay_period_end,
            pay_date=run.pay_date,
            payroll_type=run.payroll_type,
            departments=run.departments.split(",") if run.departments else [],
            notes=run.notes,
            status=run.status,
            created_at=run.created_at,
            entries=run.entries,
        ))
    return result

@router.get("/summary", response_model=PayrollSummary)
def summary(db: Session = Depends(get_db)):
    """Placed before /{run_id} so the literal path '/summary' is not treated as an int run_id (avoids 422)."""
    data = payroll_summary(db)
    return data

@router.get("/{run_id}", response_model=PayrollRunOut)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = get_payroll_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    return PayrollRunOut(
        id=run.id,
        pay_period_start=run.pay_period_start,
        pay_period_end=run.pay_period_end,
        pay_date=run.pay_date,
        payroll_type=run.payroll_type,
        departments=run.departments.split(",") if run.departments else [],
        notes=run.notes,
        status=run.status,
        created_at=run.created_at,
        entries=run.entries,
    )

@router.get("/{run_id}/entries", response_model=PaginatedPayrollEntries)
def list_entries(
    run_id: int,
    page: int = Query(1, ge=1),
    pageSize: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db)
):
    run = get_payroll_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    total, items = paginate_entries(db, run_id, page, pageSize)
    # Pydantic will convert
    return {
        "total": total,
        "page": page,
        "pageSize": pageSize,
        "entries": items
    }

@router.patch("/entry/{entry_id}", response_model=PayrollEntryOut)
def update_payroll_entry(entry_id: int, payload: PayrollEntryUpdate, db: Session = Depends(get_db)):
    entry = update_entry(db, entry_id, payload.dict(exclude_unset=True))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry

@router.post("/{run_id}/finalize", response_model=PayrollRunOut)
def finalize_payroll(run_id: int = Path(...), db: Session = Depends(get_db)):
    run = finalize_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    return PayrollRunOut(
        id=run.id,
        pay_period_start=run.pay_period_start,
        pay_period_end=run.pay_period_end,
        pay_date=run.pay_date,
        payroll_type=run.payroll_type,
        departments=run.departments.split(",") if run.departments else [],
        notes=run.notes,
        status=run.status,
        created_at=run.created_at,
        entries=run.entries,
    )

# Additional endpoints expected by forms
misc_router = APIRouter(prefix="/api/hr")

@misc_router.post("/overtime/approve")
def approve_overtime(payload: OvertimeApprovalCreate, db: Session = Depends(get_db)):
    approval = record_overtime(db, payload.employeeId, payload.overtimeHours, payload.overtimeRate, payload.approvalReason, payload.weekEnding)
    return {"id": approval.id}

@misc_router.post("/bonus/process")
def process_bonus(payload: BonusProcessingCreate, db: Session = Depends(get_db)):
    bonus = record_bonus(db, payload.employeeIds, payload.bonusType, payload.bonusAmount, payload.taxWithholding, payload.bonusReason, payload.effectiveDate)
    return {"id": bonus.id}

@misc_router.post("/settlements/create")
def create_driver_settlement(payload: DriverSettlementCreate, db: Session = Depends(get_db)):
    settlement = create_settlement(db, payload.driverId, payload.settlementPeriod, payload.totalMiles, payload.mileageRate, payload.detentionHours, payload.detentionRate, payload.fuelSurcharge, payload.otherDeductions, payload.notes)
    return {"id": settlement.id}
