from sqlalchemy.orm import Session
from sqlalchemy import func, inspect, text
from datetime import datetime
import json
from typing import List, Optional, Dict, Any
from app.models.payroll import (
    PayrollRun, PayrollEntry, OvertimeApproval, BonusPayment, DriverSettlement
)
from app.models.employee import Employee
from app.models.userModels import Driver
from app.models.simple_load import SimpleLoad
from app.schema.payrollSchema import PayrollRunCreate, SettlementRequestData


def ensure_payroll_schema(db: Session):
    """Ad-hoc lightweight migration to add recently introduced columns if missing.
    This avoids crashes when the table was created before new fields (no Alembic yet)."""
    inspector = inspect(db.bind)
    existing_cols = {c['name'] for c in inspector.get_columns('payroll_entries')}
    # column name -> SQL snippet
    add_columns = []
    if 'hourly_rate' not in existing_cols:
        add_columns.append("ADD COLUMN hourly_rate DOUBLE PRECISION DEFAULT 25.0")
    if 'bonus_amount' not in existing_cols:
        add_columns.append("ADD COLUMN bonus_amount DOUBLE PRECISION DEFAULT 0")
    if 'mileage' not in existing_cols:
        add_columns.append("ADD COLUMN mileage DOUBLE PRECISION DEFAULT 0")
    if 'per_diem' not in existing_cols:
        add_columns.append("ADD COLUMN per_diem DOUBLE PRECISION DEFAULT 0")
    if 'federal_tax' not in existing_cols:
        add_columns.append("ADD COLUMN federal_tax DOUBLE PRECISION DEFAULT 0")
    if 'state_tax' not in existing_cols:
        add_columns.append("ADD COLUMN state_tax DOUBLE PRECISION DEFAULT 0")
    if 'fica_tax' not in existing_cols:
        add_columns.append("ADD COLUMN fica_tax DOUBLE PRECISION DEFAULT 0")
    if 'health_insurance' not in existing_cols:
        add_columns.append("ADD COLUMN health_insurance DOUBLE PRECISION DEFAULT 0")
    if 'retirement_401k' not in existing_cols:
        add_columns.append("ADD COLUMN retirement_401k DOUBLE PRECISION DEFAULT 0")
    if 'other_deductions' not in existing_cols:
        add_columns.append("ADD COLUMN other_deductions DOUBLE PRECISION DEFAULT 0")
    if 'total_deductions' not in existing_cols:
        add_columns.append("ADD COLUMN total_deductions DOUBLE PRECISION DEFAULT 0")
    if 'net_pay' not in existing_cols:
        add_columns.append("ADD COLUMN net_pay DOUBLE PRECISION DEFAULT 0")
    if 'pay_period' not in existing_cols:
        add_columns.append("ADD COLUMN pay_period VARCHAR(255)")
    if 'has_w2' not in existing_cols:
        add_columns.append("ADD COLUMN has_w2 INTEGER DEFAULT 1")
    if 'has_1099' not in existing_cols:
        add_columns.append("ADD COLUMN has_1099 INTEGER DEFAULT 0")
    if add_columns:
        alter_sql = "ALTER TABLE payroll_entries " + ", ".join(add_columns) + ";"
        db.execute(text(alter_sql))
        db.commit()


def create_payroll_run(db: Session, payload: PayrollRunCreate) -> PayrollRun:
    # Ensure table has all required columns (for existing deployments without migrations)
    ensure_payroll_schema(db)
    run = PayrollRun(
        pay_period_start=payload.payPeriodStart,
        pay_period_end=payload.payPeriodEnd,
        pay_date=payload.payDate,
        payroll_type=payload.payrollType,
        departments=",".join(payload.departments),
        notes=payload.notes,
        status="Draft" if payload.draft else "Processed",
    )
    db.add(run)
    db.flush()

    # Create an entry row for every employee
    employees: List[Employee] = db.query(Employee).order_by(Employee.createdAt.desc()).all()
    for emp in employees:
        hourly = 25.0
        regular_hours = 80.0
        overtime_hours = 0.0
        gross = hourly * regular_hours
        federal = gross * 0.12
        state = gross * 0.04
        fica = gross * 0.0765
        benefits = 150.0
        deductions = federal + state + fica + benefits
        entry = PayrollEntry(
            run_id=run.id,
            employee_id=emp.id,
            employee_name=emp.name,
            position=emp.position,
            department=emp.department,
            hourly_rate=hourly,
            regular_hours=regular_hours,
            overtime_hours=overtime_hours,
            bonus_amount=0,
            mileage=0,
            per_diem=0,
            gross_pay=gross,
            federal_tax=federal,
            state_tax=state,
            fica_tax=fica,
            health_insurance=benefits,
            total_deductions=deductions,
            net_pay=gross - deductions,
            status="Pending" if run.status == "Draft" else "Approved",
            pay_period=f"{payload.payPeriodStart} - {payload.payPeriodEnd}",
            has_w2=1,
            has_1099=0,
        )
        db.add(entry)

    db.commit()
    db.refresh(run)
    return run


def list_payroll_runs(db: Session):
    return db.query(PayrollRun).order_by(PayrollRun.created_at.desc()).all()


def get_payroll_run(db: Session, run_id: int):
    return db.query(PayrollRun).filter(PayrollRun.id == run_id).first()


def payroll_summary(db: Session):
    # Compute simple aggregates
    total_net = db.query(func.coalesce(func.sum(PayrollEntry.net_pay), 0)).scalar() or 0
    total_gross = db.query(func.coalesce(func.sum(PayrollEntry.gross_pay), 0)).scalar() or 0
    total_employees = db.query(func.count(func.distinct(PayrollEntry.employee_id))).scalar() or 0
    if total_employees == 0:
        # fallback to employees table so UI shows count even before first run
        total_employees = db.query(func.count(Employee.id)).scalar() or 0
    taxes_withheld = db.query(func.coalesce(func.sum(PayrollEntry.federal_tax + PayrollEntry.state_tax + PayrollEntry.fica_tax), 0)).scalar() or 0
    benefits_cost = db.query(func.coalesce(func.sum(PayrollEntry.health_insurance), 0)).scalar() or 0
    w2s_generated = total_employees
    quarterly_taxes = taxes_withheld * 0.25  # placeholder

    # Upcoming and last processed (stub logic)
    last_run = db.query(PayrollRun).order_by(PayrollRun.pay_date.desc()).first()
    last_processed = last_run.pay_date.isoformat() if last_run else None
    upcoming = None
    if last_run and last_run.status == "Draft":
        upcoming = last_run.pay_date.isoformat()

    return {
        "totalPayroll": round(total_net, 2),
        "totalEmployees": total_employees,
        "taxesWithheld": round(taxes_withheld, 2),
        "benefitsCost": round(benefits_cost, 2),
        "w2sGenerated": w2s_generated,
        "quarterlyTaxes": round(quarterly_taxes, 2),
        "upcomingPayroll": upcoming,
        "lastProcessed": last_processed,
    }


def record_overtime(db: Session, employee_id: str, hours: float, rate: float, reason: str, week_ending):
    approval = OvertimeApproval(
        employee_id=employee_id,
        overtime_hours=hours,
        overtime_rate=rate,
        approval_reason=reason,
        week_ending=week_ending,
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return approval


def record_bonus(db: Session, employee_ids: List[str], bonus_type: str, amount: float, tax_withholding: str, reason: str, effective_date):
    bonus = BonusPayment(
        employee_ids_json=json.dumps(employee_ids),
        bonus_type=bonus_type,
        bonus_amount=amount,
        tax_withholding=tax_withholding,
        bonus_reason=reason,
        effective_date=effective_date,
    )
    db.add(bonus)
    db.commit()
    db.refresh(bonus)
    return bonus


def create_settlement(db: Session, driver_id: str, settlement_period: str, total_miles: float, mileage_rate: float, detention_hours, detention_rate, fuel_surcharge, other_deductions, notes):
    settlement = DriverSettlement(
        driver_id=driver_id,
        settlement_period=settlement_period,
        total_miles=total_miles,
        mileage_rate=mileage_rate,
        detention_hours=detention_hours,
        detention_rate=detention_rate,
        fuel_surcharge=fuel_surcharge,
        other_deductions=other_deductions,
        notes=notes,
    )
    db.add(settlement)
    db.commit()
    db.refresh(settlement)
    return settlement

def paginate_entries(db: Session, run_id: int, page: int, page_size: int):
    q = db.query(PayrollEntry).filter(PayrollEntry.run_id == run_id)
    total = q.count()
    items = (
        q.order_by(PayrollEntry.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, items

def update_entry(db: Session, entry_id: int, data: dict):
    entry = db.query(PayrollEntry).filter(PayrollEntry.id == entry_id).first()
    if not entry:
        return None
    for k, v in data.items():
        if v is not None and hasattr(entry, k):
            setattr(entry, k, v)
    # Recalculate amounts
    gross = (entry.hourly_rate * entry.regular_hours) + (1.5 * entry.hourly_rate * entry.overtime_hours) + entry.bonus_amount + (entry.per_diem or 0)
    federal = gross * 0.12
    state = gross * 0.04
    fica = gross * 0.0765
    benefits = entry.health_insurance or 150.0
    deductions = federal + state + fica + benefits + (entry.other_deductions or 0)
    entry.gross_pay = gross
    entry.federal_tax = federal
    entry.state_tax = state
    entry.fica_tax = fica
    entry.total_deductions = deductions
    entry.net_pay = gross - deductions
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

def finalize_run(db: Session, run_id: int):
    run = db.query(PayrollRun).filter(PayrollRun.id == run_id).first()
    if not run:
        return None
    run.status = "Processed"
    for e in run.entries:
        e.status = "Approved"
        db.add(e)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


# Settlement Request Functions
def get_settlement_request_data(db: Session, load_id: str) -> Optional[Dict[str, Any]]:
    """Get settlement request data for a specific load"""
    # Get load details
    load = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not load:
        return None
    
    # Get driver details
    driver = db.query(Driver).filter(Driver.id == load.assignedDriverId).first()
    if not driver:
        return None
    
    # Calculate estimated miles and duration from load data
    # For now, using placeholder values - in real implementation, 
    # you'd calculate these from pickup/delivery locations
    estimated_miles = 380  # Default value
    estimated_duration = 6.5  # Default value
    
    # Company standard rates
    mileage_rate = 0.50  # $0.50 per mile
    hourly_rate = float(driver.payRate) if driver.payType == "hourly" else 25.0
    detention_rate = hourly_rate  # Same as hourly rate
    
    return {
        "loadId": load_id,
        "driverId": driver.id,
        "driverInfo": {
            "firstName": driver.firstName,
            "lastName": driver.lastName,
            "payRate": float(driver.payRate),
            "payType": driver.payType
        },
        "loadDetails": {
            "loadNumber": load.loadNumber,
            "pickupLocation": load.pickupLocation,
            "deliveryLocation": load.deliveryLocation,
            "estimatedMiles": estimated_miles,
            "estimatedDuration": estimated_duration
        },
        "rates": {
            "mileageRate": mileage_rate,
            "hourlyRate": hourly_rate,
            "detentionRate": detention_rate
        }
    }


def calculate_settlement(
    actual_miles: float,
    actual_hours: float,
    detention_hours: float,
    fuel_surcharge: float,
    other_deductions: float,
    mileage_rate: float,
    hourly_rate: float,
    detention_rate: float
) -> Dict[str, Any]:
    """Calculate settlement breakdown"""
    mileage_pay = actual_miles * mileage_rate
    hourly_pay = actual_hours * hourly_rate
    detention_pay = detention_hours * detention_rate
    total_settlement = mileage_pay + hourly_pay + detention_pay + fuel_surcharge - other_deductions
    
    return {
        "mileagePay": round(mileage_pay, 2),
        "hourlyPay": round(hourly_pay, 2),
        "detentionPay": round(detention_pay, 2),
        "fuelSurcharge": round(fuel_surcharge, 2),
        "totalSettlement": round(total_settlement, 2)
    }


def submit_settlement_request(
    db: Session, 
    load_id: str, 
    settlement_data: SettlementRequestData
) -> Dict[str, Any]:
    """Submit settlement request for a load"""
    # Get load and driver info
    load = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not load:
        raise ValueError("Load not found")
    
    driver = db.query(Driver).filter(Driver.id == load.assignedDriverId).first()
    if not driver:
        raise ValueError("Driver not found")
    
    # Get rates
    mileage_rate = 0.50  # Company standard
    hourly_rate = float(driver.payRate) if driver.payType == "hourly" else 25.0
    detention_rate = hourly_rate
    
    # Calculate settlement
    calculation = calculate_settlement(
        settlement_data.actualMiles,
        settlement_data.actualHours,
        settlement_data.detentionHours or 0,
        settlement_data.fuelSurcharge or 0,
        settlement_data.otherDeductions or 0,
        mileage_rate,
        hourly_rate,
        detention_rate
    )
    
    # Create settlement period (current month)
    current_date = datetime.now()
    settlement_period = f"{current_date.year}-{current_date.month:02d}"
    
    # Create settlement record
    settlement = create_settlement(
        db=db,
        driver_id=driver.id,
        settlement_period=settlement_period,
        total_miles=settlement_data.actualMiles,
        mileage_rate=mileage_rate,
        detention_hours=settlement_data.detentionHours,
        detention_rate=detention_rate,
        fuel_surcharge=settlement_data.fuelSurcharge,
        other_deductions=settlement_data.otherDeductions,
        notes=settlement_data.notes
    )
    
    return {
        "settlementId": str(settlement.id),
        "status": "pending_approval",
        "totalSettlement": calculation["totalSettlement"],
        "breakdown": calculation
    }
