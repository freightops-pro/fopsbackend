"""
Response serialization utilities for consistent API responses.

This module provides helper functions to convert SQLAlchemy models
to consistent dictionary responses.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime


def serialize_load(load) -> dict:
    """
    Convert SimpleLoad model to response dictionary.
    
    Args:
        load: SimpleLoad model instance
        
    Returns:
        Dictionary with load data in consistent format
    """
    return {
        "id": load.id,
        "load_number": load.loadNumber,
        "customer_name": load.customerName,
        "pickup_location": load.pickupLocation,
        "delivery_location": load.deliveryLocation,
        "pickup_date": load.pickupDate.isoformat() if load.pickupDate else None,
        "delivery_date": load.deliveryDate.isoformat() if load.deliveryDate else None,
        "pickup_time": load.pickuptime.isoformat() if load.pickuptime else None,
        "delivery_time": load.deliverytime.isoformat() if load.deliverytime else None,
        "rate": float(load.rate or 0),
        "notes": load.notes,
        "status": load.status,
        "priority": getattr(load, 'priority', 'normal'),
        "assigned_driver_id": load.assignedDriverId,
        "assigned_truck_id": load.assignedTruckId,
        "company_id": load.companyId,
        "created_at": load.createdAt.isoformat() if hasattr(load, 'createdAt') and load.createdAt else None,
        "updated_at": load.updatedAt.isoformat() if hasattr(load, 'updatedAt') and load.updatedAt else None,
        **(load.meta or {})
    }


def serialize_load_list(loads: List) -> List[dict]:
    """
    Convert list of SimpleLoad models to response list.
    
    Args:
        loads: List of SimpleLoad model instances
        
    Returns:
        List of dictionaries with load data
    """
    return [serialize_load(load) for load in loads]


def serialize_load_billing(billing) -> dict:
    """
    Convert LoadBilling model to response dictionary.
    
    Args:
        billing: LoadBilling model instance
        
    Returns:
        Dictionary with billing data
    """
    return {
        "id": str(billing.id),
        "load_id": billing.load_id,
        "base_rate": float(billing.base_rate or 0),
        "total_amount": float(billing.total_amount or 0),
        "billing_status": billing.billing_status,
        "invoice_number": billing.invoice_number,
        "customer_name": billing.customer_name,
        "rate_type": billing.rate_type,
        "due_date": billing.due_date.isoformat() if billing.due_date else None,
        "paid_date": billing.paid_date.isoformat() if billing.paid_date else None,
        "created_at": billing.created_at.isoformat() if hasattr(billing, 'created_at') and billing.created_at else None,
        "company_id": billing.company_id
    }


def serialize_load_accessorial(accessorial) -> dict:
    """
    Convert LoadAccessorial model to response dictionary.
    
    Args:
        accessorial: LoadAccessorial model instance
        
    Returns:
        Dictionary with accessorial data
    """
    return {
        "id": str(accessorial.id),
        "load_id": accessorial.load_id,
        "type": accessorial.type,
        "description": accessorial.description,
        "amount": float(accessorial.amount or 0),
        "quantity": float(accessorial.quantity or 1),
        "rate": float(accessorial.rate or 0),
        "is_billable": accessorial.is_billable,
        "customer_approved": accessorial.customer_approved,
        "notes": accessorial.notes,
        "created_at": accessorial.created_at.isoformat() if hasattr(accessorial, 'created_at') and accessorial.created_at else None,
        "company_id": accessorial.company_id
    }


def serialize_load_accessorial_list(accessorials: List) -> List[dict]:
    """
    Convert list of LoadAccessorial models to response list.
    
    Args:
        accessorials: List of LoadAccessorial model instances
        
    Returns:
        List of dictionaries with accessorial data
    """
    return [serialize_load_accessorial(acc) for acc in accessorials]


def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """
    Format datetime to ISO string.
    
    Args:
        dt: datetime object or None
        
    Returns:
        ISO format string or None
    """
    return dt.isoformat() if dt else None


def serialize_paginated_response(
    items: List[dict],
    page: int,
    limit: int,
    total: int
) -> dict:
    """
    Create standardized paginated response.
    
    Args:
        items: List of items for current page
        page: Current page number
        limit: Items per page
        total: Total number of items
        
    Returns:
        Dictionary with pagination metadata and items
    """
    return {
        "items": items,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit if limit > 0 else 0,
            "has_next": (page * limit) < total,
            "has_prev": page > 1
        }
    }

