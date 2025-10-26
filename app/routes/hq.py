from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime

from app.config.db import get_db
from app.models.userModels import Companies, Users, Driver, Equipment, Loads

router = APIRouter(prefix="/api/hq", tags=["HQ Admin"])


@router.get("/metrics")
def get_hq_metrics(db: Session = Depends(get_db)):
    total_tenants = db.query(func.count(Companies.id)).filter(Companies.isActive == True).scalar() or 0
    total_users = db.query(func.count(Users.id)).scalar() or 0
    total_drivers = db.query(func.count(Driver.id)).scalar() or 0
    total_vehicles = db.query(func.count(Equipment.id)).scalar() or 0
    total_loads = db.query(func.count(Loads.id)).scalar() or 0

    # Placeholder financial/system metrics until real sources exist
    total_revenue = 0
    monthly_growth = 0
    system_health = 100  # percent uptime placeholder
    support_tickets = 0

    return {
        "totalTenants": int(total_tenants),
        "totalUsers": int(total_users),
        "totalDrivers": int(total_drivers),
        "totalVehicles": int(total_vehicles),
        "totalLoads": int(total_loads),
        "totalRevenue": float(total_revenue),
        "monthlyGrowth": float(monthly_growth),
        "systemHealth": float(system_health),
        "supportTickets": int(support_tickets),
    }


@router.get("/tenants")
def list_tenants(db: Session = Depends(get_db)) -> List[dict]:
    companies = db.query(Companies).filter(Companies.isActive == True).all()

    results: List[dict] = []
    for c in companies:
        user_count = db.query(func.count(Users.id)).filter(Users.companyid == c.id).scalar() or 0
        results.append({
            "id": c.id,
            "companyId": c.id,
            "tenantName": c.name,
            "subscriptionTier": c.subscriptionPlan or "starter",
            "monthlyRevenue": 0,
            "userCount": int(user_count),
            "lastActivity": (c.updatedAt or c.createdAt or datetime.utcnow()).isoformat(),
            "healthScore": 95,
            "riskLevel": "low" if (c.subscriptionStatus or "trial") != "cancelled" else "high",
            "supportTier": "standard",
        })

    return results


@router.post("/tenants/{company_id}/deletion-code")
def generate_deletion_code(company_id: str = Path(...)):
    # Simple deterministic code to confirm deletion action
    suffix = company_id.replace("-", "")[-6:].upper() if company_id else "000000"
    return {"confirmationCode": f"DELETE-{suffix}"}


@router.get("/revenue")
def get_revenue_overview(db: Session = Depends(get_db)):
    # Aggregate subscription distribution by plan from Companies
    rows = db.query(Companies.subscriptionPlan, func.count(Companies.id)).group_by(Companies.subscriptionPlan).all()
    distribution = {}
    for plan, count in rows:
        key = (plan or "starter").lower()
        distribution[key] = int(count or 0)

    return {
        "totalMRR": 0,
        "newMRR": 0,
        "churnedMRR": 0,
        "expansionMRR": 0,
        "cac": 0,
        "ltv": 0,
        "paymentVolume": 0,
        "subscriptionDistribution": distribution,
    }


