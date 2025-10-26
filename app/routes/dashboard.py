from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from app.config.db import get_db
from app.models.simple_load import SimpleLoad
from app.models.userModels import Driver, Equipment, Companies
from app.models.invoice import Invoice
from app.models.bill import Bill
from app.routes.user import verify_token, get_tenant_id

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/metrics")
async def get_dashboard_metrics(
    timeRange: Optional[str] = 'today',
    tenant_id: str = Depends(get_tenant_id),
    _: None = Depends(verify_token),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get comprehensive dashboard metrics for the logged-in company"""
    try:
        # Calculate date range
        now = datetime.utcnow()
        if timeRange == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif timeRange == 'week':
            start_date = now - timedelta(days=7)
        elif timeRange == 'month':
            start_date = now - timedelta(days=30)
        else:
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Get company info
        company = db.query(Companies).filter(Companies.id == tenant_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        # Calculate revenue (from invoices)
        total_revenue = db.query(func.sum(Invoice.amount)).filter(
            and_(
                Invoice.companyId == tenant_id,
                Invoice.createdAt >= start_date,
                Invoice.status.in_(['paid', 'partially_paid'])
            )
        ).scalar() or 0

        # Get loads statistics
        active_loads = db.query(func.count(SimpleLoad.id)).filter(
            and_(
                SimpleLoad.companyId == tenant_id,
                SimpleLoad.status.in_(['assigned', 'in_progress', 'picked_up'])
            )
        ).scalar() or 0

        completed_loads = db.query(func.count(SimpleLoad.id)).filter(
            and_(
                SimpleLoad.companyId == tenant_id,
                SimpleLoad.status == 'delivered',
                SimpleLoad.deliveredAt >= start_date
            )
        ).scalar() or 0

        # Get driver statistics
        total_drivers = db.query(func.count(Driver.id)).filter(
            and_(
                Driver.companyId == tenant_id,
                Driver.isActive == True
            )
        ).scalar() or 0

        available_drivers = db.query(func.count(Driver.id)).filter(
            and_(
                Driver.companyId == tenant_id,
                Driver.isActive == True,
                Driver.status == 'available'
            )
        ).scalar() or 0

        # Get truck statistics
        total_trucks = db.query(func.count(Equipment.id)).filter(
            and_(
                Equipment.companyId == tenant_id,
                Equipment.isActive == True,
                Equipment.equipmentType == 'truck'
            )
        ).scalar() or 0

        active_trucks = db.query(func.count(Equipment.id)).filter(
            and_(
                Equipment.companyId == tenant_id,
                Equipment.isActive == True,
                Equipment.equipmentType == 'truck',
                Equipment.status == 'active'
            )
        ).scalar() or 0

        # Calculate fleet utilization
        fleet_utilization = (active_trucks / total_trucks * 100) if total_trucks > 0 else 0

        # Calculate on-time delivery rate
        total_delivered = db.query(func.count(SimpleLoad.id)).filter(
            and_(
                SimpleLoad.companyId == tenant_id,
                SimpleLoad.status == 'delivered',
                SimpleLoad.deliveredAt >= start_date
            )
        ).scalar() or 0

        # For now, we'll estimate on-time delivery (in real app, you'd check against promised delivery time)
        on_time_delivery = 94.7  # Default percentage, should be calculated from actual data

        # Get pending bills (expenses)
        pending_expenses = db.query(func.sum(Bill.amount)).filter(
            and_(
                Bill.companyId == tenant_id,
                Bill.status == 'pending'
            )
        ).scalar() or 0

        # Calculate fuel efficiency (placeholder - would need actual fuel data)
        fuel_efficiency = 6.5  # MPG average

        # Safety score (placeholder - would need incident data)
        safety_score = 98.5

        # Get recent alerts count (loads that need attention)
        alerts_count = db.query(func.count(SimpleLoad.id)).filter(
            and_(
                SimpleLoad.companyId == tenant_id,
                or_(
                    SimpleLoad.status == 'delayed',
                    and_(
                        SimpleLoad.status == 'in_progress',
                        SimpleLoad.estimatedDelivery < now
                    )
                )
            )
        ).scalar() or 0

        return {
            "totalRevenue": float(total_revenue),
            "activeLoads": active_loads,
            "totalDrivers": total_drivers,
            "totalTrucks": total_trucks,
            "completedLoads": completed_loads,
            "activeTrucks": active_trucks,
            "availableDrivers": available_drivers,
            "fleetUtilization": round(fleet_utilization, 2),
            "onTimeDelivery": on_time_delivery,
            "fuelEfficiency": fuel_efficiency,
            "safetyScore": safety_score,
            "alertsCount": alerts_count,
            "pendingExpenses": float(pending_expenses),
            "companyInfo": {
                "name": company.name,
                "walletBalance": float(company.walletBalance or 0),
                "subscriptionStatus": company.subscriptionStatus,
                "subscriptionPlan": company.subscriptionPlan
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Dashboard metrics error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard metrics")

@router.get("/recent-activities")
async def get_recent_activities(
    limit: int = 10,
    tenant_id: str = Depends(get_tenant_id),
    _: None = Depends(verify_token),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get recent activities for the dashboard"""
    try:
        # Get recent loads
        recent_loads = db.query(SimpleLoad).filter(
            SimpleLoad.companyId == tenant_id
        ).order_by(SimpleLoad.createdAt.desc()).limit(limit).all()

        activities = []
        for load in recent_loads:
            activities.append({
                "id": load.id,
                "type": "load",
                "action": f"Load #{load.loadNumber} - {load.status}",
                "timestamp": load.createdAt.isoformat() if load.createdAt else None,
                "status": load.status,
                "details": {
                    "from": load.pickupLocation,
                    "to": load.deliveryLocation,
                    "driver": load.driverId
                }
            })

        return {
            "activities": activities,
            "total": len(activities)
        }

    except Exception as e:
        print(f"Recent activities error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch recent activities")

@router.get("/quick-stats")
async def get_quick_stats(
    tenant_id: str = Depends(get_tenant_id),
    _: None = Depends(verify_token),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get quick statistics for dashboard widgets"""
    try:
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Today's loads
        todays_loads = db.query(func.count(SimpleLoad.id)).filter(
            and_(
                SimpleLoad.companyId == tenant_id,
                SimpleLoad.createdAt >= today_start
            )
        ).scalar() or 0

        # Loads in transit
        in_transit = db.query(func.count(SimpleLoad.id)).filter(
            and_(
                SimpleLoad.companyId == tenant_id,
                SimpleLoad.status.in_(['in_progress', 'picked_up'])
            )
        ).scalar() or 0

        # Pending approvals (bills/invoices)
        pending_bills = db.query(func.count(Bill.id)).filter(
            and_(
                Bill.companyId == tenant_id,
                Bill.status == 'pending'
            )
        ).scalar() or 0

        # Available capacity
        total_capacity = db.query(func.count(Equipment.id)).filter(
            and_(
                Equipment.companyId == tenant_id,
                Equipment.isActive == True,
                Equipment.equipmentType == 'truck'
            )
        ).scalar() or 0

        used_capacity = db.query(func.count(Equipment.id)).filter(
            and_(
                Equipment.companyId == tenant_id,
                Equipment.isActive == True,
                Equipment.equipmentType == 'truck',
                Equipment.status == 'in_use'
            )
        ).scalar() or 0

        available_capacity = total_capacity - used_capacity

        return {
            "todaysLoads": todays_loads,
            "loadsInTransit": in_transit,
            "pendingApprovals": pending_bills,
            "availableCapacity": available_capacity,
            "capacityPercentage": round((available_capacity / total_capacity * 100) if total_capacity > 0 else 0, 2)
        }

    except Exception as e:
        print(f"Quick stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch quick stats")
