from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from typing import Optional, List
from uuid import uuid4
from datetime import datetime

from sqlalchemy.orm import Session

from app.config.db import get_db
from app.routes.user import verify_token, get_tenant_id
from app.models.simple_load import SimpleLoad
from app.models.userModels import LoadBilling, LoadAccessorial, Driver
from app.models.load_stop import LoadStop
from app.models.load_leg import LoadLeg
from app.services.ocr_service import extract_bol_data, validate_image_file
from app.services.maps_service import autocomplete_address, geocode_address, get_place_details
from app.services.leg_service import generate_legs, get_leg_summary
from app.schema.load_schema import (
    LoadCreateWithLegs, LoadWithLegsResponse, BOLUploadResponse,
    AddressSuggestion, DriverPaySummary, LoadSummary
)


router = APIRouter(prefix="/api/loads", tags=["Loads"])


def parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        # accept yyyy-mm-dd or ISO
        if len(value) == 10 and value[4] == "-":
            return datetime.fromisoformat(value)
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None


@router.get("/")
def list_loads(
    request: Request,
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token),
    page: int = Query(1),
    limit: int = Query(100),
):
    q = db.query(SimpleLoad)
    total = q.count()
    items = q.order_by(SimpleLoad.createdAt.desc()).offset((page - 1) * limit).limit(limit).all()
    return {
        "page": page,
        "limit": limit,
        "total": total,
        "items": [
            {
                "id": l.id,
                "loadNumber": l.loadNumber,
                "customerName": l.customerName,
                "pickupLocation": l.pickupLocation,
                "deliveryLocation": l.deliveryLocation,
                "pickupDate": l.pickupDate.isoformat() if l.pickupDate else None,
                "deliveryDate": l.deliveryDate.isoformat() if l.deliveryDate else None,
                "pickuptime": l.pickuptime.isoformat() if l.pickuptime else None,
                "deliverytime": l.deliverytime.isoformat() if l.deliverytime else None,
                "rate": float(l.rate or 0),
                "notes": l.notes,
                "status": l.status,
                "priority": l.priority,
                "assigned_driver_id": l.assignedDriverId,
                "assigned_truck_id": l.assignedTruckId,
                **(l.meta or {}),
            }
            for l in items
        ],
    }

@router.get("/{load_id}")
def get_load(load_id: str, db: Session = Depends(get_db), _: dict = Depends(verify_token)):
    l: Optional[SimpleLoad] = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not l:
        raise HTTPException(status_code=404, detail="Load not found")
    return {
        "id": l.id,
        "loadNumber": l.loadNumber,
        "customerName": l.customerName,
        "pickupLocation": l.pickupLocation,
        "deliveryLocation": l.deliveryLocation,
        "pickupDate": l.pickupDate.isoformat() if l.pickupDate else None,
        "deliveryDate": l.deliveryDate.isoformat() if l.deliveryDate else None,
        "pickuptime": l.pickuptime.isoformat() if l.pickuptime else None,
        "deliverytime": l.deliverytime.isoformat() if l.deliverytime else None,
        "rate": float(l.rate or 0),
        "notes": l.notes,
        "status": l.status,
        "priority": l.priority,
        "assigned_driver_id": l.assignedDriverId,
        "assigned_truck_id": l.assignedTruckId,
        **(l.meta or {}),
    }


@router.get("/scheduled")
def list_scheduled_loads(
    date: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD) to match by pickup or delivery date"),
    db: Session = Depends(get_db),
    _: dict = Depends(verify_token),
):
    if not date:
        return []
    try:
        # Accept YYYY-MM-DD and compare against pickuptime/deliverytime dates
        day = datetime.fromisoformat(date)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD")

    start = datetime(day.year, day.month, day.day)
    end = datetime(day.year, day.month, day.day, 23, 59, 59, 999999)

    q = (
        db.query(SimpleLoad)
        .filter(
            (
                (SimpleLoad.pickupDate != None) &  # noqa: E711
                (SimpleLoad.pickupDate >= start) &
                (SimpleLoad.pickupDate <= end)
            ) | (
                (SimpleLoad.deliveryDate != None) &  # noqa: E711
                (SimpleLoad.deliveryDate >= start) &
                (SimpleLoad.deliveryDate <= end)
            )
        )
        .order_by(SimpleLoad.pickupDate.asc().nulls_last())
    )

    items = q.all()
    return [
        {
            "id": l.id,
            "loadNumber": l.loadNumber,
            "customerName": l.customerName,
            "pickupLocation": l.pickupLocation,
            "deliveryLocation": l.deliveryLocation,
            "pickuptime": l.pickuptime.isoformat() if l.pickuptime else None,
            "deliverytime": l.deliverytime.isoformat() if l.deliverytime else None,
            "status": l.status,
            "assignedDriverId": l.assignedDriverId,
            "assignedTruckId": l.assignedTruckId,
            "rate": float(l.rate or 0),
            "priority": getattr(l, 'priority', 'normal'),
        }
        for l in items
    ]

@router.post("/", status_code=201)
def create_load(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token),
):
    company_id = token.get("companyId") or token.get("companyid")
    if not company_id:
        raise HTTPException(status_code=400, detail="Missing company context")

    # Map current UI form fields
    load_number = payload.get("loadNumber") or payload.get("loadnumber") or f"LD-{str(uuid4())[:8]}"
    customer = payload.get("customerName") or payload.get("customer") or "Customer"
    pickup_loc = payload.get("pickupLocation") or payload.get("pickuplocation")
    delivery_loc = payload.get("deliveryLocation") or payload.get("deliverylocation")
    pickup_date = parse_dt(payload.get("pickupDate"))
    delivery_date = parse_dt(payload.get("deliveryDate"))
    pickuptime = parse_dt(payload.get("pickuptime"))
    deliverytime = parse_dt(payload.get("deliverytime"))
    rate = payload.get("rate") or 0
    notes = payload.get("notes")
    priority = payload.get("priority") or "normal"

    if not pickup_loc or not delivery_loc:
        raise HTTPException(status_code=400, detail="pickupLocation and deliveryLocation are required")

    # capture any extra fields from the form (commodity, trailerType, special flags, etc.)
    passthrough = dict(payload)
    for k in [
        "loadNumber","loadnumber","customerName","customer","pickupLocation","pickuplocation",
        "deliveryLocation","deliverylocation","pickupDate","deliveryDate","pickuptime","deliverytime",
        "rate","notes","priority","status","assigned_driver_id","assignedDriverId","assigned_truck_id","assignedTruckId"
    ]:
        passthrough.pop(k, None)

    l = SimpleLoad(
        id=str(uuid4()),
        companyId=company_id,
        loadNumber=load_number,
        customerName=customer,
        pickupLocation=pickup_loc,
        deliveryLocation=delivery_loc,
        pickupDate=pickup_date,
        deliveryDate=delivery_date,
        pickuptime=pickuptime,
        deliverytime=deliverytime,
        rate=rate,
        notes=notes,
        priority=priority,
        status=payload.get("status") or "pending",
        assignedDriverId=payload.get("assigned_driver_id") or payload.get("assignedDriverId"),
        assignedTruckId=payload.get("assigned_truck_id") or payload.get("assignedTruckId"),
        meta=passthrough,
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return {"id": l.id}


# New enhanced endpoints for advanced load creation

@router.post("/upload-bol", response_model=BOLUploadResponse)
async def upload_bol(
    file: UploadFile = File(...),
    token: dict = Depends(verify_token)
):
    """Upload BOL/POD and extract data via OCR"""
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Read file content
        file_content = await file.read()
        
        # Validate image file
        if not await validate_image_file(file_content):
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        # Extract data using OCR
        result = await extract_bol_data(file_content)
        
        return BOLUploadResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"BOL upload failed: {str(e)}")

@router.get("/autocomplete-address", response_model=List[AddressSuggestion])
async def address_autocomplete(
    query: str = Query(..., min_length=3),
    token: dict = Depends(verify_token)
):
    """Get address suggestions using Google Places API"""
    try:
        suggestions = await autocomplete_address(query)
        return [AddressSuggestion(**suggestion) for suggestion in suggestions]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Address autocomplete failed: {str(e)}")

@router.get("/place-details")
async def get_place_details_endpoint(
    place_id: str = Query(...),
    token: dict = Depends(verify_token)
):
    """Get detailed information about a place using place_id"""
    try:
        details = await get_place_details(place_id)
        return details
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Place details lookup failed: {str(e)}")

@router.get("/available-drivers", response_model=List[DriverPaySummary])
async def get_available_drivers(
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """Get active drivers for leg assignment"""
    try:
        company_id = token.get("companyId") or token.get("companyid")
        if not company_id:
            raise HTTPException(status_code=400, detail="Missing company context")
        
        drivers = db.query(Driver).filter(
            Driver.companyId == company_id,
            Driver.status == "available",
            Driver.isActive == True
        ).all()
        
        driver_summaries = []
        for driver in drivers:
            driver_summaries.append(DriverPaySummary(
                id=driver.id,
                name=f"{driver.firstName} {driver.lastName}",
                pay_type=driver.payType or "percentage",
                pay_rate=float(driver.payRate or 0),
                status=driver.status,
                current_location=driver.currentLocation
            ))
        
        return driver_summaries
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get drivers: {str(e)}")

@router.post("/create-with-legs", response_model=LoadWithLegsResponse)
async def create_load_with_legs(
    payload: LoadCreateWithLegs,
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """Create load with automatic multi-leg generation"""
    try:
        company_id = token.get("companyId") or token.get("companyid")
        if not company_id:
            raise HTTPException(status_code=400, detail="Missing company context")
        
        # 1. Create load
        load_id = str(uuid4())
        load_number = f"LD-{str(uuid4())[:8].upper()}"
        
        # Calculate total rate
        accessorial_total = sum(a.amount for a in payload.accessorials)
        total_rate = payload.base_rate + accessorial_total
        
        # Create SimpleLoad entry
        simple_load = SimpleLoad(
            id=load_id,
            companyId=company_id,
            loadNumber=load_number,
            customerName=payload.customer_name,
            commodity=payload.commodity,
            baseRate=payload.base_rate,
            totalRate=total_rate,
            status="pending",
            notes=payload.notes,
            accessorials=[a.dict() for a in payload.accessorials] if payload.accessorials else None
        )
        db.add(simple_load)
        db.commit()
        db.refresh(simple_load)
        
        # 2. Create stops
        stops = []
        for i, stop_data in enumerate(payload.stops):
            stop_id = str(uuid4())
            
            # Geocode address if lat/long not provided
            latitude = stop_data.latitude
            longitude = stop_data.longitude
            
            if not latitude or not longitude:
                try:
                    geocode_result = await geocode_address(stop_data.address)
                    latitude = geocode_result["latitude"]
                    longitude = geocode_result["longitude"]
                except:
                    pass  # Continue without coordinates
            
            stop = LoadStop(
                id=stop_id,
                load_id=load_id,
                stop_type=stop_data.stop_type,
                business_name=stop_data.business_name,
                address=stop_data.address,
                city=stop_data.city,
                state=stop_data.state,
                zip=stop_data.zip,
                latitude=latitude,
                longitude=longitude,
                appointment_start=stop_data.appointment_start,
                appointment_end=stop_data.appointment_end,
                driver_assist=stop_data.driver_assist,
                sequence_number=stop_data.sequence_number,
                special_instructions=stop_data.special_instructions
            )
            db.add(stop)
            db.commit()
            db.refresh(stop)
            stops.append(stop)
        
        # 3. Generate legs with driver assignments
        stops_data = [
            {
                "id": stop.id,
                "address": stop.address,
                "appointment_start": stop.appointment_start,
                "appointment_end": stop.appointment_end,
                "sequence_number": stop.sequence_number
            }
            for stop in stops
        ]
        
        legs_data = await generate_legs(
            db, load_id, stops_data, company_id, payload.base_rate,
            [a.dict() for a in payload.accessorials]
        )
        
        # Create leg records
        legs = []
        for leg_data in legs_data:
            leg = LoadLeg(
                company_id=company_id,
                load_id=load_id,
                leg_number=leg_data["leg_number"],
                driver_id=leg_data["driver_id"],
                start_stop_id=leg_data["start_stop_id"],
                end_stop_id=leg_data["end_stop_id"],
                miles=leg_data["miles"],
                driver_pay=leg_data["driver_pay"],
                origin=leg_data["origin"],
                destination=leg_data["destination"],
                pickup_time=leg_data["pickup_time"],
                delivery_time=leg_data["delivery_time"],
                status="pending"
            )
            db.add(leg)
            db.commit()
            db.refresh(leg)
            legs.append(leg)
        
        # 4. Return complete load with legs
        return LoadWithLegsResponse(
            id=simple_load.id,
            load_number=simple_load.loadNumber,
            customer_name=simple_load.customerName,
            load_type=payload.load_type,
            commodity=simple_load.commodity,
            base_rate=float(simple_load.baseRate),
            total_rate=float(simple_load.totalRate),
            status=simple_load.status,
            notes=simple_load.notes,
            stops=[
                LoadStopResponse(
                    id=stop.id,
                    stop_type=stop.stop_type,
                    business_name=stop.business_name,
                    address=stop.address,
                    city=stop.city,
                    state=stop.state,
                    zip=stop.zip,
                    latitude=stop.latitude,
                    longitude=stop.longitude,
                    appointment_start=stop.appointment_start,
                    appointment_end=stop.appointment_end,
                    driver_assist=stop.driver_assist,
                    sequence_number=stop.sequence_number,
                    special_instructions=stop.special_instructions,
                    created_at=stop.created_at,
                    updated_at=stop.updated_at
                )
                for stop in stops
            ],
            legs=[
                LoadLegResponse(
                    id=leg.id,
                    leg_number=leg.leg_number,
                    driver_id=leg.driver_id,
                    driver_name=f"{leg.driver.firstName} {leg.driver.lastName}" if leg.driver else None,
                    start_stop_id=leg.start_stop_id,
                    end_stop_id=leg.end_stop_id,
                    miles=leg.miles,
                    driver_pay=float(leg.driver_pay) if leg.driver_pay else None,
                    origin=leg.origin,
                    destination=leg.destination,
                    pickup_time=leg.pickup_time,
                    delivery_time=leg.delivery_time,
                    status=leg.status,
                    dispatched=leg.dispatched,
                    dispatched_at=leg.dispatched_at,
                    notes=leg.notes,
                    created_at=leg.created_at,
                    updated_at=leg.updated_at
                )
                for leg in legs
            ],
            accessorials=payload.accessorials,
            created_at=simple_load.createdAt,
            updated_at=simple_load.updatedAt
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Load creation failed: {str(e)}")

@router.get("/{load_id}/legs")
async def get_load_legs(
    load_id: str,
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """Get all legs for a specific load"""
    try:
        company_id = token.get("companyId") or token.get("companyid")
        if not company_id:
            raise HTTPException(status_code=400, detail="Missing company context")
        
        legs_summary = await get_leg_summary(db, load_id, company_id)
        return legs_summary
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get load legs: {str(e)}")

@router.patch("/legs/{leg_id}/dispatch")
async def dispatch_leg(
    leg_id: int,
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """Dispatch a specific leg"""
    try:
        company_id = token.get("companyId") or token.get("companyid")
        if not company_id:
            raise HTTPException(status_code=400, detail="Missing company context")
        
        from app.services.leg_service import update_leg_status
        
        success = await update_leg_status(db, leg_id, "dispatched", company_id)
        if not success:
            raise HTTPException(status_code=404, detail="Leg not found")
        
        return {"success": True, "message": "Leg dispatched successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to dispatch leg: {str(e)}")


@router.post("/{load_id}/assign")
def assign_load(load_id: str, body: dict, db: Session = Depends(get_db), _: dict = Depends(verify_token)):
    l: Optional[SimpleLoad] = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not l:
        raise HTTPException(status_code=404, detail="Load not found")
    
    # Handle driver assignment
    if body.get("driverId"):
        l.assignedDriverId = body.get("driverId")
    elif body.get("assigned_driver_id"):
        l.assignedDriverId = body.get("assigned_driver_id")
    
    # Handle truck assignment
    if body.get("assigned_truck_id"):
        l.assignedTruckId = body.get("assigned_truck_id")
    
    # Handle appointment time (for scheduling)
    if body.get("appointmentTime"):
        pt = parse_dt(body.get("appointmentTime"))
        if pt:
            l.pickuptime = pt
    elif body.get("pickuptime"):
        pt = parse_dt(body.get("pickuptime"))
        if pt:
            l.pickuptime = pt
    
    l.notes = body.get("dispatch_notes") or l.notes
    l.status = body.get("status") or l.status or "scheduled"
    db.commit()
    db.refresh(l)
    return {"success": True}


@router.put("/{load_id}")
def update_load(load_id: str, updates: dict, db: Session = Depends(get_db), _: dict = Depends(verify_token)):
    l: Optional[SimpleLoad] = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not l:
        raise HTTPException(status_code=404, detail="Load not found")

    # Direct fields
    for src, attr in [
        ("loadNumber", "loadNumber"),
        ("customerName", "customerName"),
        ("pickupLocation", "pickupLocation"),
        ("deliveryLocation", "deliveryLocation"),
        ("rate", "rate"),
        ("notes", "notes"),
        ("priority", "priority"),
        ("status", "status"),
    ]:
        if src in updates and updates[src] is not None:
            setattr(l, attr, updates[src])

    # Times/dates
    pt = parse_dt(updates.get("pickuptime")) if updates.get("pickuptime") else None
    if pt:
        l.pickuptime = pt
    dt = parse_dt(updates.get("deliverytime")) if updates.get("deliverytime") else None
    if dt:
        l.deliverytime = dt
    pd = parse_dt(updates.get("pickupDate")) if updates.get("pickupDate") else None
    if pd:
        l.pickupDate = pd
    dd = parse_dt(updates.get("deliveryDate")) if updates.get("deliveryDate") else None
    if dd:
        l.deliveryDate = dd

    # Assignment
    if updates.get("assigned_driver_id"):
        l.assignedDriverId = updates.get("assigned_driver_id")
    if updates.get("assigned_truck_id"):
        l.assignedTruckId = updates.get("assigned_truck_id")

    # Merge any extra fields into meta
    passthrough = dict(updates)
    for k in [
        "loadNumber","customerName","pickupLocation","deliveryLocation",
        "pickupDate","deliveryDate","pickuptime","deliverytime","rate","notes","priority","status",
        "assigned_driver_id","assigned_truck_id"
    ]:
        passthrough.pop(k, None)
    l.meta = {**(l.meta or {}), **passthrough} if passthrough else (l.meta or None)

    db.commit()
    db.refresh(l)
    return {"success": True}


@router.delete("/{load_id}")
def delete_load(load_id: str, db: Session = Depends(get_db), _: dict = Depends(verify_token)):
    l: Optional[SimpleLoad] = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not l:
        raise HTTPException(status_code=404, detail="Load not found")
    db.delete(l)
    db.commit()
    return {"success": True}


# Load Billing Endpoints
@router.get("/load-billing/{load_id}")
def get_load_billing(load_id: str, db: Session = Depends(get_db), _: dict = Depends(verify_token)):
    """Get billing information for a specific load"""
    billing = db.query(LoadBilling).filter(LoadBilling.load_id == load_id).first()
    if not billing:
        return []
    
    return [{
        "id": str(billing.id),
        "loadId": billing.load_id,
        "baseRate": float(billing.base_rate or 0),
        "totalAmount": float(billing.total_amount or 0),
        "billingStatus": billing.billing_status,
        "invoiceNumber": billing.invoice_number,
        "customerName": billing.customer_name,
        "dueDate": billing.due_date.isoformat() if billing.due_date else None,
        "paidDate": billing.paid_date.isoformat() if billing.paid_date else None,
    }]


@router.post("/load-billing/{load_id}")
def create_load_billing(load_id: str, billing_data: dict, db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    """Create billing information for a load"""
    company_id = token.get("companyId") or token.get("companyid")
    if not company_id:
        raise HTTPException(status_code=400, detail="Missing company context")
    
    # Check if load exists
    load = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not load:
        raise HTTPException(status_code=404, detail="Load not found")
    
    # Check if billing already exists
    existing_billing = db.query(LoadBilling).filter(LoadBilling.load_id == load_id).first()
    if existing_billing:
        raise HTTPException(status_code=400, detail="Billing already exists for this load")
    
    billing = LoadBilling(
        id=uuid4(),
        load_id=load_id,
        company_id=company_id,
        base_rate=billing_data.get("baseRate", load.rate or 0),
        rate_type=billing_data.get("rateType", "flat"),
        billing_status=billing_data.get("billingStatus", "pending"),
        customer_name=billing_data.get("customerName", load.customerName),
        total_amount=billing_data.get("totalAmount", load.rate or 0),
        created_by=token.get("userId"),
    )
    
    db.add(billing)
    db.commit()
    db.refresh(billing)
    
    return {"id": str(billing.id), "success": True}


@router.put("/load-billing/{billing_id}")
def update_load_billing(billing_id: str, updates: dict, db: Session = Depends(get_db), _: dict = Depends(verify_token)):
    """Update billing information"""
    billing = db.query(LoadBilling).filter(LoadBilling.id == billing_id).first()
    if not billing:
        raise HTTPException(status_code=404, detail="Billing not found")
    
    # Update fields
    if "baseRate" in updates:
        billing.base_rate = updates["baseRate"]
    if "totalAmount" in updates:
        billing.total_amount = updates["totalAmount"]
    if "billingStatus" in updates:
        billing.billing_status = updates["billingStatus"]
    if "invoiceNumber" in updates:
        billing.invoice_number = updates["invoiceNumber"]
    if "dueDate" in updates:
        billing.due_date = parse_dt(updates["dueDate"])
    if "paidDate" in updates:
        billing.paid_date = parse_dt(updates["paidDate"])
    
    db.commit()
    db.refresh(billing)
    return {"success": True}


# Load Accessorials Endpoints
@router.get("/load-accessorials/{load_id}")
def get_load_accessorials(load_id: str, db: Session = Depends(get_db), _: dict = Depends(verify_token)):
    """Get accessorial charges for a load"""
    accessorials = db.query(LoadAccessorial).filter(LoadAccessorial.load_id == load_id).all()
    return [
        {
            "id": str(acc.id),
            "loadId": acc.load_id,
            "type": acc.type,
            "description": acc.description,
            "amount": float(acc.amount or 0),
            "quantity": float(acc.quantity or 1),
            "rate": float(acc.rate or 0),
            "isBillable": acc.is_billable,
            "customerApproved": acc.customer_approved,
            "notes": acc.notes,
        }
        for acc in accessorials
    ]


@router.post("/load-accessorials/{load_id}")
def create_load_accessorial(load_id: str, accessorial_data: dict, db: Session = Depends(get_db), token: dict = Depends(verify_token)):
    """Create an accessorial charge for a load"""
    company_id = token.get("companyId") or token.get("companyid")
    if not company_id:
        raise HTTPException(status_code=400, detail="Missing company context")
    
    # Check if load exists
    load = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not load:
        raise HTTPException(status_code=404, detail="Load not found")
    
    # Get or create billing record
    billing = db.query(LoadBilling).filter(LoadBilling.load_id == load_id).first()
    if not billing:
        # Create default billing
        billing = LoadBilling(
            id=uuid4(),
            load_id=load_id,
            company_id=company_id,
            base_rate=load.rate or 0,
            billing_status="pending",
            customer_name=load.customerName,
            total_amount=load.rate or 0,
            created_by=token.get("userId"),
        )
        db.add(billing)
        db.commit()
        db.refresh(billing)
    
    accessorial = LoadAccessorial(
        id=uuid4(),
        load_id=load_id,
        billing_id=billing.id,
        company_id=company_id,
        type=accessorial_data.get("type", "detention"),
        description=accessorial_data.get("description", ""),
        amount=accessorial_data.get("amount", 0),
        quantity=accessorial_data.get("quantity", 1),
        rate=accessorial_data.get("rate", 0),
        is_billable=accessorial_data.get("isBillable", True),
        notes=accessorial_data.get("notes"),
        created_by=token.get("userId"),
    )
    
    db.add(accessorial)
    db.commit()
    db.refresh(accessorial)
    
    return {"id": str(accessorial.id), "success": True}


# OCR Processing Endpoints
@router.post("/ocr/extract-from-rate-confirmation")
async def extract_from_rate_confirmation(
    rateConfirmation: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    _: dict = Depends(verify_token)
):
    """
    Extract load data from uploaded rate confirmation using OCR
    """
    try:
        # Validate file type
        allowed_types = ['image/', 'application/pdf']
        if not rateConfirmation.content_type or not any(rateConfirmation.content_type.startswith(t) for t in allowed_types):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Please upload an image file (PNG, JPG) or PDF."
            )

        # Read file content
        file_content = await rateConfirmation.read()

        # Use real OCR service to extract data
        extracted_data = ocr_service.extract_load_data(file_content, rateConfirmation.filename)
        
        # Add multi-tenant isolation
        extracted_data["company_id"] = tenant_id
        extracted_data["created_by"] = tenant_id  # Will be updated with actual user ID from token

        return {
            "success": True,
            "message": "Rate confirmation processed successfully using OCR",
            "loadData": extracted_data,
            "confidence": extracted_data.get("confidence_score", 0.8),
            "extractedFields": [k for k, v in extracted_data.items() if v and k not in ["source", "extraction_date", "original_filename", "confidence_score", "company_id", "created_by"]]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "detail": f"OCR processing failed: {str(e)}"}
        )


@router.post("/ocr/extract-from-bol")
async def extract_from_bol(
    bol: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    _: dict = Depends(verify_token)
):
    """
    Extract load data from uploaded Bill of Lading using OCR
    """
    try:
        # Validate file type
        allowed_types = ['image/', 'application/pdf']
        if not bol.content_type or not any(bol.content_type.startswith(t) for t in allowed_types):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Please upload an image file (PNG, JPG) or PDF."
            )

        # Read file content
        file_content = await bol.read()

        # Use real OCR service to extract data
        extracted_data = ocr_service.extract_load_data(file_content, bol.filename)
        
        # Add multi-tenant isolation
        extracted_data["company_id"] = tenant_id
        extracted_data["created_by"] = tenant_id  # Will be updated with actual user ID from token

        return {
            "success": True,
            "message": "Bill of Lading processed successfully using OCR",
            "loadData": extracted_data,
            "confidence": extracted_data.get("confidence_score", 0.8),
            "extractedFields": [k for k, v in extracted_data.items() if v and k not in ["source", "extraction_date", "original_filename", "confidence_score", "company_id", "created_by"]]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "detail": f"BOL OCR processing failed: {str(e)}"}
        )

