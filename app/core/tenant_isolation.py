"""
Tenant Isolation Utilities

Helper functions to ensure proper data isolation in multi-tenant queries.
All functions enforce company_id filtering to prevent cross-tenant data access.
"""

from typing import TypeVar, Type, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.base import Base

T = TypeVar("T", bound=Base)


async def get_entity_by_id(
    db: AsyncSession,
    model: Type[T],
    entity_id: str,
    company_id: str,
    company_id_field: str = "company_id",
    error_message: Optional[str] = None,
) -> T:
    """
    Safely retrieve an entity by ID with company_id filtering.
    
    This function ensures that entities can only be accessed if they belong
    to the specified company, preventing cross-tenant data leakage.
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        entity_id: ID of the entity to retrieve
        company_id: Company ID to filter by (from authenticated user)
        company_id_field: Name of the company_id column (default: "company_id")
        error_message: Custom error message if entity not found
    
    Returns:
        The entity if found and belongs to the company
    
    Raises:
        HTTPException: 404 if entity not found or doesn't belong to company
    """
    # Build query with company_id filter
    query = select(model).where(
        model.id == entity_id,
        getattr(model, company_id_field) == company_id
    )
    
    result = await db.execute(query)
    entity = result.scalar_one_or_none()
    
    if not entity:
        msg = error_message or f"{model.__name__} not found or access denied"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=msg
        )
    
    return entity


async def verify_entity_belongs_to_company(
    db: AsyncSession,
    model: Type[T],
    entity_id: str,
    company_id: str,
    company_id_field: str = "company_id",
) -> bool:
    """
    Verify that an entity belongs to a specific company without raising exceptions.
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        entity_id: ID of the entity to check
        company_id: Company ID to verify against
        company_id_field: Name of the company_id column (default: "company_id")
    
    Returns:
        True if entity exists and belongs to company, False otherwise
    """
    query = select(model).where(
        model.id == entity_id,
        getattr(model, company_id_field) == company_id
    )
    
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None

