from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from app.config.db import get_db
from app.models.userModels import (
    MaintenanceSchedule, MaintenanceScheduleCreate, MaintenanceScheduleUpdate, MaintenanceScheduleResponse,
    ELDAlert, ELDAlertCreate, ELDAlertUpdate, ELDAlertResponse,
    RoadService, RoadServiceCreate, RoadServiceUpdate, RoadServiceResponse,
    Equipment, Companies, Users
)
from app.routes.user import get_current_user
import uuid

router = APIRouter(prefix="/api/maintenance", tags=["Maintenance"])

def get_company_id_from_user(current_user: Users) -> str:
    """Extract company ID from authenticated user"""
    if not current_user.companyid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company"
        )
    return current_user.companyid

# ==================== MAINTENANCE SCHEDULE ENDPOINTS ====================

@router.post("/maintenance/schedule", response_model=MaintenanceScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_maintenance_schedule(
    maintenance: MaintenanceScheduleCreate, 
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Create new maintenance schedule"""
    try:
        # Verify equipment exists
        equipment = db.query(Equipment).filter(
            Equipment.id == maintenance.equipmentId,
            Equipment.isActive == True
        ).first()
        
        if not equipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Equipment not found"
            )
        
        # Calculate next occurrence for recurring maintenance
        next_occurrence = None
        if maintenance.isRecurring and maintenance.recurrenceType and maintenance.recurrenceInterval:
            if maintenance.recurrenceType == "daily":
                next_occurrence = maintenance.scheduledDate + timedelta(days=maintenance.recurrenceInterval)
            elif maintenance.recurrenceType == "weekly":
                next_occurrence = maintenance.scheduledDate + timedelta(weeks=maintenance.recurrenceInterval)
            elif maintenance.recurrenceType == "monthly":
                next_occurrence = maintenance.scheduledDate + timedelta(days=maintenance.recurrenceInterval * 30)
            elif maintenance.recurrenceType == "yearly":
                next_occurrence = maintenance.scheduledDate + timedelta(days=maintenance.recurrenceInterval * 365)
        
        # Create maintenance schedule
        company_id = get_company_id_from_user(current_user)
        db_maintenance = MaintenanceSchedule(
            id=str(uuid.uuid4()),
            companyId=company_id,
            equipmentId=maintenance.equipmentId,
            title=maintenance.title,
            description=maintenance.description,
            maintenanceType=maintenance.maintenanceType,
            priority=maintenance.priority,
            scheduledDate=maintenance.scheduledDate,
            estimatedDuration=maintenance.estimatedDuration,
            estimatedCost=maintenance.estimatedCost,
            isRecurring=maintenance.isRecurring,
            recurrenceType=maintenance.recurrenceType,
            recurrenceInterval=maintenance.recurrenceInterval,
            nextOccurrence=next_occurrence,
            assignedTechnician=maintenance.assignedTechnician,
            assignedVendor=maintenance.assignedVendor,
            vendorContact=maintenance.vendorContact,
            vendorPhone=maintenance.vendorPhone,
            location=maintenance.location,
            notes=maintenance.notes,
            createdAt=datetime.utcnow(),
            updatedAt=datetime.utcnow(),
            isActive=True
        )
        
        db.add(db_maintenance)
        db.commit()
        db.refresh(db_maintenance)
        
        return db_maintenance
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create maintenance schedule: {str(e)}"
        )

@router.get("/maintenance/schedule", response_model=List[MaintenanceScheduleResponse])
def get_maintenance_schedules(
    equipment_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Get maintenance schedules with optional filters"""
    try:
        company_id = get_company_id_from_user(current_user)
        query = db.query(MaintenanceSchedule).filter(
            MaintenanceSchedule.companyId == company_id,
            MaintenanceSchedule.isActive == True
        )
        
        if equipment_id:
            query = query.filter(MaintenanceSchedule.equipmentId == equipment_id)
        
        if status_filter:
            query = query.filter(MaintenanceSchedule.status == status_filter)
        
        if start_date:
            query = query.filter(MaintenanceSchedule.scheduledDate >= start_date)
        
        if end_date:
            query = query.filter(MaintenanceSchedule.scheduledDate <= end_date)
        
        schedules = query.order_by(MaintenanceSchedule.scheduledDate).all()
        return schedules
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch maintenance schedules: {str(e)}"
        )

@router.get("/maintenance/schedule/{schedule_id}", response_model=MaintenanceScheduleResponse)
def get_maintenance_schedule(
    schedule_id: str, 
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Get specific maintenance schedule"""
    try:
        company_id = get_company_id_from_user(current_user)
        schedule = db.query(MaintenanceSchedule).filter(
            MaintenanceSchedule.id == schedule_id,
            MaintenanceSchedule.companyId == company_id,
            MaintenanceSchedule.isActive == True
        ).first()
        
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Maintenance schedule not found"
            )
        
        return schedule
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch maintenance schedule: {str(e)}"
        )

@router.put("/maintenance/schedule/{schedule_id}", response_model=MaintenanceScheduleResponse)
def update_maintenance_schedule(
    schedule_id: str, 
    maintenance_update: MaintenanceScheduleUpdate, 
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Update maintenance schedule"""
    try:
        company_id = get_company_id_from_user(current_user)
        db_schedule = db.query(MaintenanceSchedule).filter(
            MaintenanceSchedule.id == schedule_id,
            MaintenanceSchedule.companyId == company_id,
            MaintenanceSchedule.isActive == True
        ).first()
        
        if not db_schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Maintenance schedule not found"
            )
        
        # Update fields if provided
        update_data = maintenance_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_schedule, field, value)
        
        db_schedule.updatedAt = datetime.utcnow()
        
        db.commit()
        db.refresh(db_schedule)
        
        return db_schedule
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update maintenance schedule: {str(e)}"
        )

@router.delete("/maintenance/schedule/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_maintenance_schedule(
    schedule_id: str, 
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Soft delete maintenance schedule"""
    try:
        company_id = get_company_id_from_user(current_user)
        db_schedule = db.query(MaintenanceSchedule).filter(
            MaintenanceSchedule.id == schedule_id,
            MaintenanceSchedule.companyId == company_id,
            MaintenanceSchedule.isActive == True
        ).first()
        
        if not db_schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Maintenance schedule not found"
            )
        
        # Soft delete
        db_schedule.isActive = False
        db_schedule.updatedAt = datetime.utcnow()
        
        db.commit()
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete maintenance schedule: {str(e)}"
        )

# ==================== ELD ALERTS ENDPOINTS ====================

@router.post("/eld/alerts", response_model=ELDAlertResponse, status_code=status.HTTP_201_CREATED)
def create_eld_alert(alert: ELDAlertCreate, db: Session = Depends(get_db)):
    """Create new ELD alert"""
    try:
        # Verify equipment exists
        equipment = db.query(Equipment).filter(
            Equipment.id == alert.equipmentId,
            Equipment.isActive == True
        ).first()
        
        if not equipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Equipment not found"
            )
        
        # Create ELD alert
        db_alert = ELDAlert(
            id=str(uuid.uuid4()),
            companyId=get_current_user(db)["companyId"],
            equipmentId=alert.equipmentId,
            driverId=alert.driverId,
            alertType=alert.alertType,
            severity=alert.severity,
            title=alert.title,
            description=alert.description,
            alertData=alert.alertData,
            location=alert.location,
            createdAt=datetime.utcnow(),
            updatedAt=datetime.utcnow(),
            isActive=True
        )
        
        db.add(db_alert)
        db.commit()
        db.refresh(db_alert)
        
        return db_alert
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create ELD alert: {str(e)}"
        )

@router.get("/eld/alerts", response_model=List[ELDAlertResponse])
def get_eld_alerts(
    equipment_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get ELD alerts with optional filters"""
    try:
        company_id = get_current_user(db)["companyId"]
        query = db.query(ELDAlert).filter(
            ELDAlert.companyId == company_id,
            ELDAlert.isActive == True
        )
        
        if equipment_id:
            query = query.filter(ELDAlert.equipmentId == equipment_id)
        
        if status_filter:
            query = query.filter(ELDAlert.status == status_filter)
        
        if alert_type:
            query = query.filter(ELDAlert.alertType == alert_type)
        
        alerts = query.order_by(ELDAlert.createdAt.desc()).all()
        return alerts
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch ELD alerts: {str(e)}"
        )

@router.put("/eld/alerts/{alert_id}", response_model=ELDAlertResponse)
def update_eld_alert(alert_id: str, alert_update: ELDAlertUpdate, db: Session = Depends(get_db)):
    """Update ELD alert status"""
    try:
        company_id = get_current_user(db)["companyId"]
        db_alert = db.query(ELDAlert).filter(
            ELDAlert.id == alert_id,
            ELDAlert.companyId == company_id,
            ELDAlert.isActive == True
        ).first()
        
        if not db_alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ELD alert not found"
            )
        
        # Update fields if provided
        update_data = alert_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            if field in ["acknowledgedBy", "resolvedBy"] and value:
                if field == "acknowledgedBy":
                    db_alert.acknowledgedAt = datetime.utcnow()
                elif field == "resolvedBy":
                    db_alert.resolvedAt = datetime.utcnow()
            setattr(db_alert, field, value)
        
        db_alert.updatedAt = datetime.utcnow()
        
        db.commit()
        db.refresh(db_alert)
        
        return db_alert
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update ELD alert: {str(e)}"
        )

# ==================== ROAD SERVICES ENDPOINTS ====================

@router.post("/road-services", response_model=RoadServiceResponse, status_code=status.HTTP_201_CREATED)
def create_road_service(service: RoadServiceCreate, db: Session = Depends(get_db)):
    """Create new road service request"""
    try:
        # Verify equipment exists
        equipment = db.query(Equipment).filter(
            Equipment.id == service.equipmentId,
            Equipment.isActive == True
        ).first()
        
        if not equipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Equipment not found"
            )
        
        # Create road service
        db_service = RoadService(
            id=str(uuid.uuid4()),
            companyId=get_current_user(db)["companyId"],
            equipmentId=service.equipmentId,
            driverId=service.driverId,
            serviceType=service.serviceType,
            priority=service.priority,
            title=service.title,
            description=service.description,
            location=service.location,
            latitude=service.latitude,
            longitude=service.longitude,
            contactName=service.contactName,
            contactPhone=service.contactPhone,
            serviceProvider=service.serviceProvider,
            providerPhone=service.providerPhone,
            estimatedArrival=service.estimatedArrival,
            estimatedCost=service.estimatedCost,
            notes=service.notes,
            requestedAt=datetime.utcnow(),
            createdAt=datetime.utcnow(),
            updatedAt=datetime.utcnow(),
            isActive=True
        )
        
        db.add(db_service)
        db.commit()
        db.refresh(db_service)
        
        return db_service
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create road service: {str(e)}"
        )

@router.get("/road-services", response_model=List[RoadServiceResponse])
def get_road_services(
    equipment_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    service_type: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get road services with optional filters"""
    try:
        company_id = get_current_user(db)["companyId"]
        query = db.query(RoadService).filter(
            RoadService.companyId == company_id,
            RoadService.isActive == True
        )
        
        if equipment_id:
            query = query.filter(RoadService.equipmentId == equipment_id)
        
        if status_filter:
            query = query.filter(RoadService.status == status_filter)
        
        if service_type:
            query = query.filter(RoadService.serviceType == service_type)
        
        services = query.order_by(RoadService.requestedAt.desc()).all()
        return services
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch road services: {str(e)}"
        )

@router.put("/road-services/{service_id}", response_model=RoadServiceResponse)
def update_road_service(service_id: str, service_update: RoadServiceUpdate, db: Session = Depends(get_db)):
    """Update road service status"""
    try:
        company_id = get_current_user(db)["companyId"]
        db_service = db.query(RoadService).filter(
            RoadService.id == service_id,
            RoadService.companyId == company_id,
            RoadService.isActive == True
        ).first()
        
        if not db_service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Road service not found"
            )
        
        # Update fields if provided
        update_data = service_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            if field == "status" and value:
                if value == "dispatched":
                    db_service.dispatchedAt = datetime.utcnow()
                elif value == "on_site":
                    db_service.arrivedAt = datetime.utcnow()
                elif value == "completed":
                    db_service.completedAt = datetime.utcnow()
            setattr(db_service, field, value)
        
        db_service.updatedAt = datetime.utcnow()
        
        db.commit()
        db.refresh(db_service)
        
        return db_service
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update road service: {str(e)}"
        )

# ==================== CALENDAR ENDPOINTS ====================

@router.get("/maintenance/calendar")
def get_maintenance_calendar(
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    equipment_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get maintenance calendar events for a date range"""
    try:
        company_id = get_current_user(db)["companyId"]
        query = db.query(MaintenanceSchedule).filter(
            MaintenanceSchedule.companyId == company_id,
            MaintenanceSchedule.isActive == True,
            MaintenanceSchedule.scheduledDate >= start_date,
            MaintenanceSchedule.scheduledDate <= end_date
        )
        
        if equipment_id:
            query = query.filter(MaintenanceSchedule.equipmentId == equipment_id)
        
        schedules = query.all()
        
        # Format for calendar
        calendar_events = []
        for schedule in schedules:
            # Get equipment details
            equipment = db.query(Equipment).filter(Equipment.id == schedule.equipmentId).first()
            
            event = {
                "id": schedule.id,
                "title": schedule.title,
                "start": schedule.scheduledDate.isoformat(),
                "end": (schedule.scheduledDate + timedelta(hours=schedule.estimatedDuration or 1)).isoformat(),
                "equipmentNumber": equipment.equipmentNumber if equipment else "Unknown",
                "maintenanceType": schedule.maintenanceType,
                "priority": schedule.priority,
                "status": schedule.status,
                "color": get_priority_color(schedule.priority),
                "extendedProps": {
                    "description": schedule.description,
                    "location": schedule.location,
                    "assignedTechnician": schedule.assignedTechnician,
                    "estimatedCost": schedule.estimatedCost
                }
            }
            calendar_events.append(event)
        
        return calendar_events
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch calendar events: {str(e)}"
        )

def get_priority_color(priority: str) -> str:
    """Get color for priority level"""
    colors = {
        "low": "#10B981",      # Green
        "medium": "#F59E0B",   # Yellow
        "high": "#EF4444",     # Red
        "critical": "#7C3AED"  # Purple
    }
    return colors.get(priority, "#6B7280")  # Default gray
