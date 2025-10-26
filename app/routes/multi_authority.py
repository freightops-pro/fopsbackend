"""
Multi-Authority Operations Routes

API routes for managing multiple operating authorities within a company.
Supports carrier, brokerage, NVOCC, and freight forwarder operations.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config.db import get_db
from app.routes.user import get_current_user
from app.models.userModels import Users
from app.services.multi_authority_service import MultiAuthorityService
from app.schema.multi_authority import (
    AuthorityCreate, AuthorityUpdate, AuthorityResponse,
    AuthorityUserCreate, AuthorityUserUpdate, AuthorityUserResponse,
    AuthorityFinancialsCreate, AuthorityFinancialsResponse,
    AuthorityCustomerCreate, AuthorityCustomerResponse,
    AuthorityIntegrationCreate, AuthorityIntegrationResponse,
    AuthorityAnalyticsResponse, AuthoritySwitchRequest,
    CompanyAuthoritiesResponse
)

router = APIRouter(prefix="/api/multi-authority", tags=["Multi-Authority Operations"])


def get_current_company_id(current_user: Users = Depends(get_current_user)) -> str:
    """Get current user's company ID"""
    return current_user.company_id


# Authority Management Routes
@router.post("/authorities", response_model=AuthorityResponse, status_code=status.HTTP_201_CREATED)
async def create_authority(
    authority_data: AuthorityCreate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id)
):
    """Create a new operating authority"""
    try:
        service = MultiAuthorityService(db)
        authority = await service.create_authority(
            authority_data=authority_data,
            company_id=company_id,
            created_by_user_id=current_user.id
        )
        return authority
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create authority")


@router.get("/authorities", response_model=List[AuthorityResponse])
async def get_authorities(
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Get all authorities for the company"""
    try:
        service = MultiAuthorityService(db)
        authorities = await service.get_authorities(company_id=company_id)
        return authorities
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch authorities")


@router.get("/authorities/{authority_id}", response_model=AuthorityResponse)
async def get_authority(
    authority_id: str,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Get a specific authority"""
    try:
        service = MultiAuthorityService(db)
        authority = await service.get_authority(authority_id=authority_id, company_id=company_id)
        if not authority:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Authority not found")
        return authority
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch authority")


@router.put("/authorities/{authority_id}", response_model=AuthorityResponse)
async def update_authority(
    authority_id: str,
    authority_data: AuthorityUpdate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id)
):
    """Update an authority"""
    try:
        service = MultiAuthorityService(db)
        authority = await service.update_authority(
            authority_id=authority_id,
            authority_data=authority_data,
            company_id=company_id,
            updated_by_user_id=current_user.id
        )
        if not authority:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Authority not found")
        return authority
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update authority")


@router.delete("/authorities/{authority_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_authority(
    authority_id: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id)
):
    """Delete an authority"""
    try:
        service = MultiAuthorityService(db)
        success = await service.delete_authority(
            authority_id=authority_id,
            company_id=company_id,
            deleted_by_user_id=current_user.id
        )
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Authority not found")
        return None
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete authority")


# Authority User Management Routes
@router.post("/authorities/{authority_id}/users", response_model=AuthorityUserResponse, status_code=status.HTTP_201_CREATED)
async def assign_user_to_authority(
    authority_id: str,
    user_data: AuthorityUserCreate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id)
):
    """Assign a user to an authority with specific permissions"""
    try:
        service = MultiAuthorityService(db)
        authority_user = await service.assign_user_to_authority(
            authority_id=authority_id,
            user_data=user_data,
            company_id=company_id,
            assigned_by_user_id=current_user.id
        )
        return authority_user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to assign user to authority")


@router.get("/users/{user_id}/authorities", response_model=List[AuthorityUserResponse])
async def get_user_authorities(
    user_id: str,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Get all authorities a user has access to"""
    try:
        service = MultiAuthorityService(db)
        authority_users = await service.get_user_authorities(user_id=user_id, company_id=company_id)
        return authority_users
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch user authorities")


@router.get("/authorities/{authority_id}/users", response_model=List[AuthorityUserResponse])
async def get_authority_users(
    authority_id: str,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Get all users assigned to an authority"""
    try:
        service = MultiAuthorityService(db)
        authority_users = await service.get_authority_users(authority_id=authority_id, company_id=company_id)
        return authority_users
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch authority users")


# Authority Financials Routes
@router.post("/authorities/{authority_id}/financials", response_model=AuthorityFinancialsResponse, status_code=status.HTTP_201_CREATED)
async def create_authority_financials(
    authority_id: str,
    financials_data: AuthorityFinancialsCreate,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Create financial metrics for an authority"""
    try:
        service = MultiAuthorityService(db)
        financials = await service.create_authority_financials(
            authority_id=authority_id,
            financials_data=financials_data,
            company_id=company_id
        )
        return financials
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create authority financials")


@router.get("/authorities/{authority_id}/financials", response_model=List[AuthorityFinancialsResponse])
async def get_authority_financials(
    authority_id: str,
    period_type: Optional[str] = None,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Get financial metrics for an authority"""
    try:
        service = MultiAuthorityService(db)
        financials = await service.get_authority_financials(
            authority_id=authority_id,
            company_id=company_id,
            period_type=period_type
        )
        return financials
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch authority financials")


# Authority Customer Management Routes
@router.post("/authorities/{authority_id}/customers", response_model=AuthorityCustomerResponse, status_code=status.HTTP_201_CREATED)
async def assign_customer_to_authority(
    authority_id: str,
    customer_data: AuthorityCustomerCreate,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Assign a customer to an authority"""
    try:
        service = MultiAuthorityService(db)
        authority_customer = await service.assign_customer_to_authority(
            authority_id=authority_id,
            customer_data=customer_data,
            company_id=company_id
        )
        return authority_customer
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to assign customer to authority")


# Authority Integration Management Routes
@router.post("/authorities/{authority_id}/integrations", response_model=AuthorityIntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_authority_integration(
    authority_id: str,
    integration_data: AuthorityIntegrationCreate,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Create an integration for an authority"""
    try:
        service = MultiAuthorityService(db)
        integration = await service.create_authority_integration(
            authority_id=authority_id,
            integration_data=integration_data,
            company_id=company_id
        )
        return integration
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create authority integration")


@router.get("/authorities/{authority_id}/integrations", response_model=List[AuthorityIntegrationResponse])
async def get_authority_integrations(
    authority_id: str,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Get all integrations for an authority"""
    try:
        service = MultiAuthorityService(db)
        integrations = await service.get_authority_integrations(
            authority_id=authority_id,
            company_id=company_id
        )
        return integrations
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch authority integrations")


# Authority Analytics Routes
@router.get("/authorities/{authority_id}/analytics", response_model=AuthorityAnalyticsResponse)
async def get_authority_analytics(
    authority_id: str,
    period_type: str = "monthly",
    months_back: int = 12,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Get comprehensive analytics for an authority"""
    try:
        service = MultiAuthorityService(db)
        analytics = await service.get_authority_analytics(
            authority_id=authority_id,
            company_id=company_id,
            period_type=period_type,
            months_back=months_back
        )
        return analytics
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch authority analytics")


# Authority Switch Routes
@router.post("/users/{user_id}/switch-authority", status_code=status.HTTP_200_OK)
async def switch_user_authority(
    user_id: str,
    switch_request: AuthoritySwitchRequest,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Switch a user's primary authority"""
    try:
        service = MultiAuthorityService(db)
        success = await service.switch_user_authority(
            user_id=user_id,
            new_authority_id=switch_request.authority_id,
            company_id=company_id
        )
        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to switch authority")
        return {"message": "Authority switched successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to switch authority")


# Company Authorities Summary
@router.get("/company/authorities", response_model=CompanyAuthoritiesResponse)
async def get_company_authorities_summary(
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Get summary of all authorities for the company"""
    try:
        service = MultiAuthorityService(db)
        
        # Get all authorities
        authorities = await service.get_authorities(company_id=company_id)
        
        # Get summary data for each authority
        authority_summaries = []
        primary_authority = None
        
        for authority in authorities:
            # Get user count
            user_count = len(await service.get_authority_users(authority.id, company_id))
            
            # Get customer count (simplified - would need customer service)
            customer_count = 0  # Placeholder
            
            # Get integration count
            integrations = await service.get_authority_integrations(authority.id, company_id)
            integration_count = len(integrations)
            
            # Get financial summary (latest period)
            financials = await service.get_authority_financials(
                authority_id=authority.id,
                company_id=company_id,
                period_type="monthly"
            )
            
            total_revenue = sum(f.total_revenue for f in financials) if financials else 0
            total_profit = sum(f.net_profit for f in financials) if financials else 0
            load_count = sum(f.load_count for f in financials) if financials else 0
            
            summary = {
                "id": authority.id,
                "name": authority.name,
                "authority_type": authority.authority_type,
                "is_primary": authority.is_primary,
                "is_active": authority.is_active,
                "user_count": user_count,
                "customer_count": customer_count,
                "integration_count": integration_count,
                "total_revenue": total_revenue,
                "total_profit": total_profit,
                "load_count": load_count
            }
            
            authority_summaries.append(summary)
            
            if authority.is_primary:
                primary_authority = summary
        
        return CompanyAuthoritiesResponse(
            company_id=company_id,
            authorities=authority_summaries,
            total_authorities=len(authority_summaries),
            primary_authority=primary_authority
        )
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch company authorities summary")
