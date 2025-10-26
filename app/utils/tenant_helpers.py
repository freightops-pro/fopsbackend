"""
Multi-tenant helper utilities for ensuring data isolation.

This module provides reusable functions for filtering queries by company_id
to prevent cross-tenant data leakage.
"""
from typing import TypeVar, Optional, Any, Dict
from fastapi import HTTPException
from sqlalchemy.orm import Session, Query
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


def get_company_id_from_token(token: dict) -> str:
    """
    Extract and validate company_id from JWT token.
    
    Args:
        token: JWT token dictionary containing user claims
        
    Returns:
        str: Company ID from token
        
    Raises:
        HTTPException: If company_id is missing from token (400)
    """
    company_id = token.get("companyId") or token.get("companyid") or token.get("company_id")
    if not company_id:
        logger.error("Missing company context in JWT token")
        raise HTTPException(status_code=400, detail="Missing company context")
    return str(company_id)


def get_tenant_filtered_query(
    db: Session,
    model: T,
    token: dict,
    **filters
) -> Query:
    """
    Get a query filtered by company_id for multi-tenant isolation.
    
    This function automatically adds company_id filtering to prevent
    cross-tenant data access.
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        token: JWT token dict
        **filters: Additional filters to apply (key=value pairs)
        
    Returns:
        Query object with company_id filter applied
        
    Raises:
        HTTPException: If company_id missing from token
        
    Example:
        >>> query = get_tenant_filtered_query(db, SimpleLoad, token, status="pending")
        >>> loads = query.all()
    """
    company_id = get_company_id_from_token(token)
    
    # Start with company filter
    query = db.query(model).filter(model.companyId == company_id)
    
    # Apply additional filters
    for key, value in filters.items():
        if value is not None:
            query = query.filter(getattr(model, key) == value)
    
    return query


def verify_resource_ownership(
    db: Session,
    model: T,
    resource_id: str,
    company_id: str,
    id_field: str = "id"
) -> T:
    """
    Verify that a resource belongs to the specified company.
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        resource_id: ID of the resource to verify
        company_id: Company ID that should own the resource
        id_field: Name of the ID field (default: "id")
        
    Returns:
        The resource object if ownership verified
        
    Raises:
        HTTPException: 404 if resource not found or doesn't belong to company
        
    Example:
        >>> load = verify_resource_ownership(db, SimpleLoad, load_id, company_id)
    """
    resource = db.query(model).filter(
        getattr(model, id_field) == resource_id,
        model.companyId == company_id
    ).first()
    
    if not resource:
        logger.warning(
            f"Resource not found or unauthorized access attempt: "
            f"model={model.__name__}, id={resource_id}, company={company_id}"
        )
        raise HTTPException(
            status_code=404,
            detail=f"{model.__name__} not found"
        )
    
    return resource


def verify_multi_resource_ownership(
    db: Session,
    resources: Dict[str, tuple],
    company_id: str
) -> Dict[str, Any]:
    """
    Verify that multiple resources belong to the specified company.
    
    Args:
        db: Database session
        resources: Dict of {name: (model, resource_id, id_field)} tuples
        company_id: Company ID that should own all resources
        
    Returns:
        Dict of {name: resource_object} for verified resources
        
    Raises:
        HTTPException: 404 if any resource not found or unauthorized
        
    Example:
        >>> resources = verify_multi_resource_ownership(
        ...     db,
        ...     {
        ...         "load": (SimpleLoad, load_id, "id"),
        ...         "driver": (Driver, driver_id, "id")
        ...     },
        ...     company_id
        ... )
        >>> load = resources["load"]
        >>> driver = resources["driver"]
    """
    verified = {}
    
    for name, (model, resource_id, id_field) in resources.items():
        resource = verify_resource_ownership(
            db, model, resource_id, company_id, id_field
        )
        verified[name] = resource
    
    return verified


def get_user_id_from_token(token: dict) -> Optional[str]:
    """
    Extract user_id from JWT token.
    
    Args:
        token: JWT token dictionary
        
    Returns:
        User ID if present, None otherwise
    """
    return token.get("userId") or token.get("userid") or token.get("user_id")


def validate_same_company(*resources) -> bool:
    """
    Validate that all resources belong to the same company.
    
    Args:
        *resources: Variable number of resources with companyId attribute
        
    Returns:
        True if all resources have the same companyId
        
    Raises:
        HTTPException: 403 if resources belong to different companies
        
    Example:
        >>> validate_same_company(load, driver, truck)
    """
    if not resources:
        return True
    
    company_ids = {getattr(r, 'companyId', None) for r in resources if r}
    company_ids.discard(None)
    
    if len(company_ids) > 1:
        logger.error(f"Cross-company operation attempted: {company_ids}")
        raise HTTPException(
            status_code=403,
            detail="Resources belong to different companies"
        )
    
    return True

