from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.config.db import SessionLocal
from app.models.userModels import Truck


def _serialize_truck(truck: Truck) -> Dict[str, Any]:
    return {
        "id": truck.id,
        "companyId": truck.companyId,
        "truckNumber": truck.truckNumber,
        "make": truck.make,
        "model": truck.model,
        "year": truck.year,
        "vin": truck.vin,
        "licensePlate": truck.licensePlate,
        "registrationState": truck.registrationState,
        "status": truck.status,
        "createdAt": truck.createdAt.isoformat() if truck.createdAt else None,
        "updatedAt": truck.updatedAt.isoformat() if truck.updatedAt else None,
        "fuelType": truck.fuelType,
        "fuelEfficiency": float(truck.fuelEfficiency) if truck.fuelEfficiency is not None else None,
        "maintenanceStatus": truck.maintenanceStatus,
        "lastMaintenanceDate": truck.lastMaintenanceDate.isoformat() if truck.lastMaintenanceDate else None,
        "nextMaintenanceDate": truck.nextMaintenanceDate.isoformat() if truck.nextMaintenanceDate else None,
        "insuranceProvider": truck.insuranceProvider,
        "insurancePolicyNumber": truck.insurancePolicyNumber,
        "insuranceExpiry": truck.insuranceExpiry.isoformat() if truck.insuranceExpiry else None,
        "isActive": bool(truck.isActive) if truck.isActive is not None else True,
    }


def _get_session() -> Session:
    return SessionLocal()


async def get_fleet_stats(tenant_id: str) -> Dict[str, Any]:
    db = _get_session()
    try:
        total = db.query(Truck).filter(Truck.companyId == tenant_id).count()
        active = (
            db.query(Truck)
            .filter(Truck.companyId == tenant_id, Truck.status == "active")
            .count()
        )
        inactive = max(total - active, 0)
        return {
            "totalVehicles": total,
            "activeVehicles": active,
            "inactiveVehicles": inactive,
            "lastUpdated": datetime.utcnow().isoformat(),
        }
    finally:
        db.close()


async def get_vehicles(tenant_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    page = int(params.get("page", 1))
    limit = int(params.get("limit", 20))
    search: Optional[str] = params.get("search")
    status: Optional[str] = params.get("status")
    sort_by: str = params.get("sortBy", "createdAt")
    sort_order: str = params.get("sortOrder", "desc").lower()

    db = _get_session()
    try:
        query = db.query(Truck).filter(Truck.companyId == tenant_id)

        if search:
            like = f"%{search}%"
            query = query.filter(Truck.truckNumber.ilike(like))

        if status:
            query = query.filter(Truck.status == status)

        total = query.count()

        sort_column = getattr(Truck, sort_by, Truck.createdAt)
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        items = query.offset((page - 1) * limit).limit(limit).all()
        return {
            "page": page,
            "limit": limit,
            "total": total,
            "items": [_serialize_truck(t) for t in items],
        }
    finally:
        db.close()


async def get_vehicle_by_id(vehicle_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
    db = _get_session()
    try:
        truck = (
            db.query(Truck)
            .filter(Truck.id == vehicle_id, Truck.companyId == tenant_id)
            .first()
        )
        return _serialize_truck(truck) if truck else None
    finally:
        db.close()


async def create_vehicle(tenant_id: str, vehicle_data: Dict[str, Any]) -> Dict[str, Any]:
    db = _get_session()
    try:
        print(f"Creating vehicle for tenant {tenant_id} with data: {vehicle_data}")
        
        # Validate required fields
        required_fields = ["truckNumber", "make", "model", "year", "vin", "licensePlate"]
        for field in required_fields:
            if not vehicle_data.get(field):
                raise ValueError(f"Missing required field: {field}")
        
        # Handle date fields properly
        last_maintenance_date = None
        next_maintenance_date = None
        insurance_expiry = None
        
        if vehicle_data.get("lastMaintenanceDate"):
            try:
                last_maintenance_date = datetime.fromisoformat(vehicle_data["lastMaintenanceDate"].replace('Z', '+00:00'))
            except:
                print(f"Warning: Could not parse lastMaintenanceDate: {vehicle_data.get('lastMaintenanceDate')}")
        
        if vehicle_data.get("nextMaintenanceDate"):
            try:
                next_maintenance_date = datetime.fromisoformat(vehicle_data["nextMaintenanceDate"].replace('Z', '+00:00'))
            except:
                print(f"Warning: Could not parse nextMaintenanceDate: {vehicle_data.get('nextMaintenanceDate')}")
        
        if vehicle_data.get("insuranceExpiry"):
            try:
                insurance_expiry = datetime.fromisoformat(vehicle_data["insuranceExpiry"].replace('Z', '+00:00'))
            except:
                print(f"Warning: Could not parse insuranceExpiry: {vehicle_data.get('insuranceExpiry')}")
        
        new_truck = Truck(
            id=str(uuid.uuid4()),
            companyId=tenant_id,
            truckNumber=vehicle_data.get("truckNumber"),
            make=vehicle_data.get("make"),
            model=vehicle_data.get("model"),
            year=vehicle_data.get("year"),
            vin=vehicle_data.get("vin"),
            licensePlate=vehicle_data.get("licensePlate"),
            registrationState=vehicle_data.get("registrationState"),
            status=vehicle_data.get("status", "active"),
            fuelType=vehicle_data.get("fuelType"),
            fuelEfficiency=vehicle_data.get("fuelEfficiency"),
            maintenanceStatus=vehicle_data.get("maintenanceStatus"),
            lastMaintenanceDate=last_maintenance_date,
            nextMaintenanceDate=next_maintenance_date,
            insuranceProvider=vehicle_data.get("insuranceProvider"),
            insurancePolicyNumber=vehicle_data.get("insurancePolicyNumber"),
            insuranceExpiry=insurance_expiry,
            isActive=vehicle_data.get("isActive", True),
        )

        print(f"Truck object created: {new_truck.truckNumber}")
        db.add(new_truck)
        db.commit()
        db.refresh(new_truck)
        print(f"Truck committed to database: {new_truck.id}")
        
        result = _serialize_truck(new_truck)
        print(f"Serialized truck: {result}")
        return result
    except Exception as e:
        print(f"Error in create_vehicle: {e}")
        db.rollback()
        raise
    finally:
        db.close()


async def update_vehicle(vehicle_id: str, tenant_id: str, vehicle_data: Dict[str, Any]) -> Dict[str, Any]:
    db = _get_session()
    try:
        truck = (
            db.query(Truck)
            .filter(Truck.id == vehicle_id, Truck.companyId == tenant_id)
            .first()
        )
        if not truck:
            raise ValueError("Vehicle not found")

        for key, value in vehicle_data.items():
            if hasattr(truck, key) and key not in {"id", "companyId", "createdAt"}:
                setattr(truck, key, value)

        db.commit()
        db.refresh(truck)
        return _serialize_truck(truck)
    finally:
        db.close()


async def delete_vehicle(vehicle_id: str, tenant_id: str) -> None:
    db = _get_session()
    try:
        truck = (
            db.query(Truck)
            .filter(Truck.id == vehicle_id, Truck.companyId == tenant_id)
            .first()
        )
        if truck:
            db.delete(truck)
            db.commit()
    finally:
        db.close()


