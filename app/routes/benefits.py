from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any, Dict
import json
import uuid
from app.config.db import get_db
from app.models.employee import Employee
from app.models.benefits import EmployeeBenefits

router = APIRouter(prefix="/api/hr/benefits", tags=["HR - Benefits"])


@router.get("/plans")
def get_benefit_plans() -> Dict[str, Any]:
    # Mock plans for now; can be sourced from DB later
    plans = [
        {"id": "health_basic", "name": "Basic Health Plan", "type": "health"},
        {"id": "health_premium", "name": "Premium Health Plan", "type": "health"},
        {"id": "dental_basic", "name": "Basic Dental", "type": "dental"},
        {"id": "vision_standard", "name": "Vision Standard", "type": "vision"},
    ]
    return {"plans": plans}


@router.get("/enrollment/{employee_id}")
def get_enrollment(employee_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    rec = db.query(EmployeeBenefits).filter(EmployeeBenefits.employeeId == employee_id).order_by(EmployeeBenefits.createdAt.desc()).first()
    if not rec:
        return {"enrollment": None}
    data = {
        "employeeId": rec.employeeId,
        "effectiveDate": rec.effectiveDate,
        "enrollmentType": rec.enrollmentType,
        "healthPlan": rec.healthPlan,
        "healthCoverageLevel": rec.healthCoverageLevel,
        "dentalPlan": rec.dentalPlan,
        "dentalCoverageLevel": rec.dentalCoverageLevel,
        "visionPlan": rec.visionPlan,
        "visionCoverageLevel": rec.visionCoverageLevel,
        "lifeInsuranceAmount": rec.lifeInsuranceAmount,
        "adAndDInsurance": bool(rec.adAndDInsurance or 0),
        "retirement401kContribution": rec.retirement401kContribution,
        "rothContribution": rec.rothContribution,
        "healthSavingsAccount": rec.healthSavingsAccount,
        "dependentCareAccount": rec.dependentCareAccount,
        "voluntaryBenefits": json.loads(rec.voluntaryBenefits or "[]"),
        "lifeEventReason": rec.lifeEventReason,
    }
    return {"enrollment": data}


@router.post("/enroll")
def enroll(payload: Dict[str, Any], db: Session = Depends(get_db)) -> Dict[str, Any]:
    employee_id = payload.get("employeeId")
    if not employee_id:
        raise HTTPException(status_code=400, detail="employeeId required")
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    # Prevent duplicate enrollment for the same employee
    existing = db.query(EmployeeBenefits).filter(EmployeeBenefits.employeeId == employee_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Employee already enrolled")

    # Upsert: simple approach -> insert new record; optional enhancement: mark previous inactive
    rec = EmployeeBenefits(
        id=str(uuid.uuid4()),
        employeeId=employee_id,
        effectiveDate=payload.get("effectiveDate"),
        enrollmentType=payload.get("enrollmentType"),
        healthPlan=payload.get("healthPlan"),
        healthCoverageLevel=payload.get("healthCoverageLevel"),
        dentalPlan=payload.get("dentalPlan"),
        dentalCoverageLevel=payload.get("dentalCoverageLevel"),
        visionPlan=payload.get("visionPlan"),
        visionCoverageLevel=payload.get("visionCoverageLevel"),
        lifeInsuranceAmount=payload.get("lifeInsuranceAmount"),
        adAndDInsurance=1 if payload.get("adAndDInsurance") else 0,
        retirement401kContribution=payload.get("retirement401kContribution"),
        rothContribution=payload.get("rothContribution"),
        healthSavingsAccount=payload.get("healthSavingsAccount"),
        dependentCareAccount=payload.get("dependentCareAccount"),
        voluntaryBenefits=json.dumps(payload.get("voluntaryBenefits") or []),
        lifeEventReason=payload.get("lifeEventReason"),
    )
    db.add(rec)
    db.commit()
    return {"ok": True, "id": rec.id}


@router.get("/overview")
def benefits_overview(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Aggregate benefits enrollment and estimate costs using default premium table and 75% company contribution."""
    # Premium table aligned with UI mock
    premium = {
        "health_basic": {"employee": 150, "employee_spouse": 300, "employee_children": 225, "family": 450},
        "health_premium": {"employee": 275, "employee_spouse": 550, "employee_children": 400, "family": 750},
        "dental_basic": {"employee": 25, "employee_spouse": 50, "employee_children": 35, "family": 75},
        "vision_standard": {"employee": 8, "employee_spouse": 16, "employee_children": 12, "family": 24},
    }
    contribution_rate = 75

    # Load enrollments
    enrollments = db.query(EmployeeBenefits, Employee).join(Employee, Employee.id == EmployeeBenefits.employeeId).all()

    # Group and compute totals
    plans = {}
    retirement_enrolled = 0
    for rec, emp in enrollments:
        # Health
        if rec.healthPlan:
            key = rec.healthPlan
            cov = (rec.healthCoverageLevel or "employee").lower()
            monthly = premium.get(key, {}).get(cov, 0)
            item = plans.setdefault(key, {
                "policyName": key,
                "carrier": "",
                "enrolledEmployees": 0,
                "monthlyPremium": 0.0,
                "companyContribution": 0.0,
                "employeeContribution": 0.0,
                "contributionRate": contribution_rate,
            })
            item["enrolledEmployees"] += 1
            item["monthlyPremium"] += monthly
            item["companyContribution"] += monthly * (contribution_rate/100.0)
            item["employeeContribution"] += monthly * (1 - contribution_rate/100.0)

        # Retirement
        if rec.retirement401kContribution and str(rec.retirement401kContribution).strip() not in ("", "0", "0.0"):
            retirement_enrolled += 1

    # Shape healthPlans array
    health_plans = []
    for key, v in plans.items():
        health_plans.append({
            "id": key,
            "policyName": key.replace("_", " ").title(),
            "carrier": "Company Plan",
            **v,
        })

    total_employees = db.query(Employee).count()
    overview = {
        "healthPlans": health_plans,
        "retirement": {
            "plan": "401(k)",
            "enrolledEmployees": retirement_enrolled,
            "companyMatch": "100% up to 4%",
            "vestingSchedule": "Immediate",
            "participation": int((retirement_enrolled / total_employees) * 100) if total_employees else 0,
        },
        "perks": {
            "commuter": {"enrolled": 0, "monthlyAllowance": 0, "participation": 0},
            "wellness": {"enrolled": 0, "monthlyAllowance": 0, "participation": 0},
            "professionalDevelopment": {"enrolled": 0, "yearlyAllowance": 0, "participation": 0},
        }
    }
    return overview
