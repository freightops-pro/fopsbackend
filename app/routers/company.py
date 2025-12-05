from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.models.company import Company
from app.models.user import User
from app.schemas.company import CompanySummaryResponse, CompanyUserResponse

router = APIRouter()


@router.get("/user/companies", response_model=List[CompanySummaryResponse])
async def list_user_companies(
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[CompanySummaryResponse]:
    company = await db.get(Company, current_user.company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found for user")

    summary = CompanySummaryResponse(
        id=company.id,
        name=company.name,
        type=(company.businessType or "unknown").lower(),
        dot_number=company.dotNumber,
        mc_number=company.mcNumber,
        contact_phone=company.phone,
        primary_contact_name=company.primaryContactName,
        is_active=company.isActive,
        user_role=(current_user.role or "dispatcher").upper(),
    )

    return [summary]


@router.get("/companies/{company_id}/users", response_model=List[CompanyUserResponse])
async def list_company_users(
    company_id: str,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[CompanyUserResponse]:
    if company_id != current_user.company_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied for company users")

    result = await db.execute(select(User).where(User.company_id == company_id))
    users = result.scalars().all()

    return [
        CompanyUserResponse(
            id=user.id,
            user_id=user.id,
            company_id=user.company_id,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            role=(user.role or "dispatcher").upper(),
            permissions=[],
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        for user in users
    ]

