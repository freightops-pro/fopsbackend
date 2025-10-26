from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Any, Dict, List
from datetime import datetime
from app.config.db import get_db
from app.models.employee import Employee
from app.routes.benefits import benefits_overview
from app.models.payroll import PayrollRun
from app.models.onboarding import OnboardingFlow
from app.models.benefits import EmployeeBenefits
from app.services.onboarding_service import get_onboarding_stats

router = APIRouter(prefix="/api/hr/dashboard", tags=["HR - Dashboard"])


@router.get("/stats")
def hr_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    total = db.query(Employee).count()
    active = db.query(Employee).filter(Employee.status == "Active").count()
    on_leave = db.query(Employee).filter(Employee.status == "On Leave").count()
    # New hires in last 30 days
    thirty_days_ago = datetime.utcnow().timestamp() - (30 * 24 * 3600)
    # hireDate is DateTime or None; count recent if available
    recent = 0
    for e in db.query(Employee).all():
        if e.hireDate and e.hireDate.timestamp() >= thirty_days_ago:
            recent += 1
    return {
        "totalEmployees": total,
        "activeEmployees": active,
        "onLeave": on_leave,
        "newHires": recent,
        "openPositions": 0,
        "pendingReviews": 0,
        "upcomingRenewal": None,
    }


@router.get("/benefits-overview")
def benefits(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return benefits_overview(db)


@router.get("/recent-activity")
def recent_activity(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    # Latest payroll runs
    for r in db.query(PayrollRun).order_by(PayrollRun.created_at.desc()).limit(5).all():
        items.append({
            "type": "payroll",
            "employee": "All Employees",
            "action": f"Payroll run {r.id} status: {r.status}",
            "time": r.created_at.isoformat() if r.created_at else None,
        })
    # Latest onboarding flows
    for f in db.query(OnboardingFlow).order_by(OnboardingFlow.started_at.desc()).limit(5).all():
        items.append({
            "type": "onboarding",
            "employee": f.employee_name,
            "action": f"Onboarding {f.status}",
            "time": f.started_at.isoformat() if f.started_at else None,
        })
    # Latest benefits enrollments
    for b in db.query(EmployeeBenefits).order_by(EmployeeBenefits.createdAt.desc()).limit(5).all():
        items.append({
            "type": "benefits",
            "employee": b.employeeId,
            "action": "Benefits enrollment submitted",
            "time": b.createdAt.isoformat() if b.createdAt else None,
        })
    # Sort by time desc, keep top 10
    items.sort(key=lambda x: x.get("time") or "", reverse=True)
    return items[:10]


@router.get("/todos")
def todos(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    # Suggest actions based on onboarding stats
    stats = get_onboarding_stats(db)
    items: List[Dict[str, Any]] = []
    if stats.get("overdue", 0) > 0:
        items.append({"task": f"Follow up on {stats['overdue']} overdue onboarding flows", "priority": "high", "dueDate": "Today"})
    if stats.get("active", 0) > 0:
        items.append({"task": f"Review {stats['active']} active onboarding flows", "priority": "medium", "dueDate": "This week"})
    items.append({"task": "Process pending benefits enrollments", "priority": "medium", "dueDate": "This week"})
    return items
