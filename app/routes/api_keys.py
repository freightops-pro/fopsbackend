"""
API Key Management Routes
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from app.config.db import get_db
from app.models.api_key import APIKey, APIKeyUsage, APIKeyRateLimit
from app.services.audit_service import AuditService
from app.config.logging_config import get_logger
# from app.middleware.advanced_rate_limiter import RATE_LIMITS  # Not available
from pydantic import BaseModel

logger = get_logger(__name__)

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

# Pydantic models for request/response
class APIKeyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: Optional[dict] = None
    expires_at: Optional[datetime] = None
    rate_limit_per_hour: Optional[int] = 1000
    rate_limit_per_day: Optional[int] = 10000

class APIKeyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[dict] = None
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None
    rate_limit_per_hour: Optional[int] = None
    rate_limit_per_day: Optional[int] = None

class APIKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    description: Optional[str]
    permissions: Optional[dict]
    is_active: bool
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    usage_count: str
    rate_limit_per_hour: str
    rate_limit_per_day: str
    created_at: datetime
    updated_at: datetime

class APIKeyWithSecret(BaseModel):
    id: str
    name: str
    key: str  # Only returned when creating a new key
    key_prefix: str
    description: Optional[str]
    permissions: Optional[dict]
    is_active: bool
    expires_at: Optional[datetime]
    rate_limit_per_hour: str
    rate_limit_per_day: str
    created_at: datetime

@router.post("/", response_model=APIKeyWithSecret)
async def create_api_key(
    api_key_data: APIKeyCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Create a new API key for the company
    """
    try:
        # Extract company_id from request (assuming it's set by auth middleware)
        company_id = getattr(request.state, 'company_id', None)
        user_id = getattr(request.state, 'user_id', None)
        
        if not company_id:
            raise HTTPException(status_code=401, detail="Company ID not found")
        
        # Generate new API key
        full_key, key_hash, key_prefix = APIKey.generate_key()
        
        # Create API key record
        api_key = APIKey(
            name=api_key_data.name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            company_id=company_id,
            created_by=user_id or "system",
            description=api_key_data.description,
            permissions=api_key_data.permissions,
            expires_at=api_key_data.expires_at,
            rate_limit_per_hour=str(api_key_data.rate_limit_per_hour),
            rate_limit_per_day=str(api_key_data.rate_limit_per_day)
        )
        
        db.add(api_key)
        db.commit()
        db.refresh(api_key)
        
        # Log the creation
        audit_service = AuditService(db)
        audit_service.log_data_access_event(
            action="CREATE",
            resource_type="api_key",
            resource_id=api_key.id,
            user_id=user_id,
            company_id=company_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            metadata={"key_name": api_key.name, "key_prefix": key_prefix}
        )
        
        logger.info(f"API key created: {api_key.name}", extra={
            "extra_fields": {
                "api_key_id": api_key.id,
                "company_id": company_id,
                "user_id": user_id,
                "key_prefix": key_prefix
            }
        })
        
        return APIKeyWithSecret(
            id=api_key.id,
            name=api_key.name,
            key=full_key,  # Only time the full key is returned
            key_prefix=api_key.key_prefix,
            description=api_key.description,
            permissions=api_key.permissions,
            is_active=api_key.is_active,
            expires_at=api_key.expires_at,
            rate_limit_per_hour=api_key.rate_limit_per_hour,
            rate_limit_per_day=api_key.rate_limit_per_day,
            created_at=api_key.created_at
        )
        
    except Exception as e:
        logger.error(f"Failed to create API key: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create API key")

@router.get("/", response_model=List[APIKeyResponse])
async def list_api_keys(
    request: Request,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    """
    List all API keys for the company
    """
    try:
        company_id = getattr(request.state, 'company_id', None)
        
        if not company_id:
            raise HTTPException(status_code=401, detail="Company ID not found")
        
        api_keys = db.query(APIKey).filter(
            APIKey.company_id == company_id
        ).offset(skip).limit(limit).all()
        
        return [
            APIKeyResponse(
                id=key.id,
                name=key.name,
                key_prefix=key.key_prefix,
                description=key.description,
                permissions=key.permissions,
                is_active=key.is_active,
                expires_at=key.expires_at,
                last_used_at=key.last_used_at,
                usage_count=key.usage_count,
                rate_limit_per_hour=key.rate_limit_per_hour,
                rate_limit_per_day=key.rate_limit_per_day,
                created_at=key.created_at,
                updated_at=key.updated_at
            )
            for key in api_keys
        ]
        
    except Exception as e:
        logger.error(f"Failed to list API keys: {e}")
        raise HTTPException(status_code=500, detail="Failed to list API keys")

@router.get("/{api_key_id}", response_model=APIKeyResponse)
async def get_api_key(
    api_key_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Get a specific API key
    """
    try:
        company_id = getattr(request.state, 'company_id', None)
        
        if not company_id:
            raise HTTPException(status_code=401, detail="Company ID not found")
        
        api_key = db.query(APIKey).filter(
            APIKey.id == api_key_id,
            APIKey.company_id == company_id
        ).first()
        
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        
        return APIKeyResponse(
            id=api_key.id,
            name=api_key.name,
            key_prefix=api_key.key_prefix,
            description=api_key.description,
            permissions=api_key.permissions,
            is_active=api_key.is_active,
            expires_at=api_key.expires_at,
            last_used_at=api_key.last_used_at,
            usage_count=api_key.usage_count,
            rate_limit_per_hour=api_key.rate_limit_per_hour,
            rate_limit_per_day=api_key.rate_limit_per_day,
            created_at=api_key.created_at,
            updated_at=api_key.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get API key: {e}")
        raise HTTPException(status_code=500, detail="Failed to get API key")

@router.put("/{api_key_id}", response_model=APIKeyResponse)
async def update_api_key(
    api_key_id: str,
    api_key_data: APIKeyUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Update an API key
    """
    try:
        company_id = getattr(request.state, 'company_id', None)
        user_id = getattr(request.state, 'user_id', None)
        
        if not company_id:
            raise HTTPException(status_code=401, detail="Company ID not found")
        
        api_key = db.query(APIKey).filter(
            APIKey.id == api_key_id,
            APIKey.company_id == company_id
        ).first()
        
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        
        # Update fields
        if api_key_data.name is not None:
            api_key.name = api_key_data.name
        if api_key_data.description is not None:
            api_key.description = api_key_data.description
        if api_key_data.permissions is not None:
            api_key.permissions = api_key_data.permissions
        if api_key_data.is_active is not None:
            api_key.is_active = api_key_data.is_active
        if api_key_data.expires_at is not None:
            api_key.expires_at = api_key_data.expires_at
        if api_key_data.rate_limit_per_hour is not None:
            api_key.rate_limit_per_hour = str(api_key_data.rate_limit_per_hour)
        if api_key_data.rate_limit_per_day is not None:
            api_key.rate_limit_per_day = str(api_key_data.rate_limit_per_day)
        
        db.commit()
        db.refresh(api_key)
        
        # Log the update
        audit_service = AuditService(db)
        audit_service.log_data_access_event(
            action="UPDATE",
            resource_type="api_key",
            resource_id=api_key.id,
            user_id=user_id,
            company_id=company_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            metadata={"key_name": api_key.name}
        )
        
        return APIKeyResponse(
            id=api_key.id,
            name=api_key.name,
            key_prefix=api_key.key_prefix,
            description=api_key.description,
            permissions=api_key.permissions,
            is_active=api_key.is_active,
            expires_at=api_key.expires_at,
            last_used_at=api_key.last_used_at,
            usage_count=api_key.usage_count,
            rate_limit_per_hour=api_key.rate_limit_per_hour,
            rate_limit_per_day=api_key.rate_limit_per_day,
            created_at=api_key.created_at,
            updated_at=api_key.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update API key: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update API key")

@router.delete("/{api_key_id}")
async def delete_api_key(
    api_key_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Delete an API key
    """
    try:
        company_id = getattr(request.state, 'company_id', None)
        user_id = getattr(request.state, 'user_id', None)
        
        if not company_id:
            raise HTTPException(status_code=401, detail="Company ID not found")
        
        api_key = db.query(APIKey).filter(
            APIKey.id == api_key_id,
            APIKey.company_id == company_id
        ).first()
        
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        
        # Log the deletion
        audit_service = AuditService(db)
        audit_service.log_data_access_event(
            action="DELETE",
            resource_type="api_key",
            resource_id=api_key.id,
            user_id=user_id,
            company_id=company_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            metadata={"key_name": api_key.name, "key_prefix": api_key.key_prefix}
        )
        
        # Delete the API key
        db.delete(api_key)
        db.commit()
        
        logger.info(f"API key deleted: {api_key.name}", extra={
            "extra_fields": {
                "api_key_id": api_key.id,
                "company_id": company_id,
                "user_id": user_id
            }
        })
        
        return {"message": "API key deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete API key: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete API key")

@router.get("/{api_key_id}/usage")
async def get_api_key_usage(
    api_key_id: str,
    request: Request,
    db: Session = Depends(get_db),
    days: int = 7
):
    """
    Get usage statistics for an API key
    """
    try:
        company_id = getattr(request.state, 'company_id', None)
        
        if not company_id:
            raise HTTPException(status_code=401, detail="Company ID not found")
        
        api_key = db.query(APIKey).filter(
            APIKey.id == api_key_id,
            APIKey.company_id == company_id
        ).first()
        
        if not api_key:
            raise HTTPException(status_code=404, detail="API key not found")
        
        # Get usage data for the specified period
        start_date = datetime.utcnow() - timedelta(days=days)
        
        usage_data = db.query(APIKeyUsage).filter(
            APIKeyUsage.api_key_id == api_key_id,
            APIKeyUsage.timestamp >= start_date
        ).all()
        
        # Aggregate usage statistics
        total_requests = len(usage_data)
        successful_requests = len([u for u in usage_data if u.status_code.startswith('2')])
        failed_requests = total_requests - successful_requests
        
        # Group by endpoint
        endpoint_usage = {}
        for usage in usage_data:
            endpoint = usage.endpoint
            if endpoint not in endpoint_usage:
                endpoint_usage[endpoint] = {"count": 0, "successful": 0, "failed": 0}
            endpoint_usage[endpoint]["count"] += 1
            if usage.status_code.startswith('2'):
                endpoint_usage[endpoint]["successful"] += 1
            else:
                endpoint_usage[endpoint]["failed"] += 1
        
        return {
            "api_key_id": api_key_id,
            "period_days": days,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": (successful_requests / total_requests * 100) if total_requests > 0 else 0,
            "endpoint_usage": endpoint_usage,
            "usage_data": [
                {
                    "timestamp": u.timestamp,
                    "endpoint": u.endpoint,
                    "method": u.method,
                    "status_code": u.status_code,
                    "response_time_ms": u.response_time_ms
                }
                for u in usage_data[-50:]  # Last 50 requests
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get API key usage: {e}")
        raise HTTPException(status_code=500, detail="Failed to get API key usage")
