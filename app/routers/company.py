from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.models.company import Company
from app.models.user import User
from app.schemas.company import (
    CompanyProfileResponse,
    CompanyProfileUpdate,
    CompanySummaryResponse,
    CompanyUserResponse,
)
from app.schemas.user import UserProfileResponse, UserProfileUpdate

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


# ============ User Profile Endpoints ============


@router.get("/user/profile", response_model=UserProfileResponse)
async def get_user_profile(
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Get current user's profile."""
    company = await db.get(Company, current_user.company_id)

    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        phone=current_user.phone,
        avatar_url=current_user.avatar_url,
        timezone=current_user.timezone or "America/Chicago",
        job_title=current_user.job_title,
        role=current_user.role,
        company_id=current_user.company_id,
        company_name=company.name if company else None,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


@router.put("/user/profile", response_model=UserProfileResponse)
async def update_user_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """Update current user's own profile."""
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(current_user, field, value)

    await db.commit()
    await db.refresh(current_user)

    company = await db.get(Company, current_user.company_id)

    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        phone=current_user.phone,
        avatar_url=current_user.avatar_url,
        timezone=current_user.timezone or "America/Chicago",
        job_title=current_user.job_title,
        role=current_user.role,
        company_id=current_user.company_id,
        company_name=company.name if company else None,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


# ============ Company Profile Endpoints (Admin Only) ============


@router.get("/company/profile", response_model=CompanyProfileResponse)
async def get_company_profile(
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompanyProfileResponse:
    """Get company profile. Any authenticated user can view."""
    company = await db.get(Company, current_user.company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    return CompanyProfileResponse(
        id=company.id,
        name=company.name,
        legal_name=company.legal_name,
        email=company.email,
        phone=company.phone,
        fax=company.fax,
        business_type=company.businessType,
        dot_number=company.dotNumber,
        mc_number=company.mcNumber,
        tax_id=company.tax_id,
        primary_contact_name=company.primaryContactName,
        address_line1=company.address_line1,
        address_line2=company.address_line2,
        city=company.city,
        state=company.state,
        zip_code=company.zip_code,
        description=company.description,
        website=company.website,
        year_founded=company.year_founded,
        logo_url=company.logo_url,
        is_active=company.isActive,
        created_at=company.createdAt,
        updated_at=company.updatedAt,
    )


@router.put("/company/profile", response_model=CompanyProfileResponse)
async def update_company_profile(
    payload: CompanyProfileUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompanyProfileResponse:
    """Update company profile. Only TENANT_ADMIN can update."""
    # Check if user is admin
    user_role = (current_user.role or "").upper()
    if user_role != "TENANT_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update company profile"
        )

    company = await db.get(Company, current_user.company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Map schema fields to model fields
    field_mapping = {
        "business_type": "businessType",
        "dot_number": "dotNumber",
        "mc_number": "mcNumber",
        "primary_contact_name": "primaryContactName",
    }

    for field, value in update_data.items():
        model_field = field_mapping.get(field, field)
        setattr(company, model_field, value)

    await db.commit()
    await db.refresh(company)

    return CompanyProfileResponse(
        id=company.id,
        name=company.name,
        legal_name=company.legal_name,
        email=company.email,
        phone=company.phone,
        fax=company.fax,
        business_type=company.businessType,
        dot_number=company.dotNumber,
        mc_number=company.mcNumber,
        tax_id=company.tax_id,
        primary_contact_name=company.primaryContactName,
        address_line1=company.address_line1,
        address_line2=company.address_line2,
        city=company.city,
        state=company.state,
        zip_code=company.zip_code,
        description=company.description,
        website=company.website,
        year_founded=company.year_founded,
        logo_url=company.logo_url,
        is_active=company.isActive,
        created_at=company.createdAt,
        updated_at=company.updatedAt,
    )

