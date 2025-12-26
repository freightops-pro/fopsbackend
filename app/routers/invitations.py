"""
Invitations Router - API endpoints for user invitations.

Provides endpoints for:
- Creating invitations (TENANT_ADMIN)
- Listing pending invitations
- Cancelling invitations
- Resending invitation emails
- Accepting invitations (public endpoint)
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.models.user import User
from app.services.invitation_service import InvitationService
from app.schemas.invitation import (
    InvitationCreate,
    InvitationResponse,
    InvitationListResponse,
    AcceptInvitationRequest,
    AcceptInvitationResponse,
    ResendInvitationResponse,
    InvitationStats,
)

router = APIRouter()


async def _service(db: AsyncSession = Depends(get_db)) -> InvitationService:
    return InvitationService(db)


async def _company_id(current_user: User = Depends(deps.get_current_user)) -> str:
    return current_user.company_id


@router.post("", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    data: InvitationCreate,
    company_id: str = Depends(_company_id),
    service: InvitationService = Depends(_service),
    current_user: User = Depends(deps.require_role("TENANT_ADMIN")),
) -> InvitationResponse:
    """
    Create a new user invitation.

    Requires TENANT_ADMIN role. Sends an invitation email to the specified address.
    """
    try:
        return await service.create_invitation(
            company_id=company_id,
            invited_by=current_user.id,
            data=data,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=InvitationListResponse)
async def list_invitations(
    company_id: str = Depends(_company_id),
    service: InvitationService = Depends(_service),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _current_user: User = Depends(deps.get_current_user),
) -> InvitationListResponse:
    """
    List invitations for the current company.

    Returns paginated list of all invitations.
    """
    return await service.list_invitations(
        company_id=company_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=InvitationStats)
async def get_invitation_stats(
    company_id: str = Depends(_company_id),
    service: InvitationService = Depends(_service),
    _current_user: User = Depends(deps.get_current_user),
) -> InvitationStats:
    """Get invitation statistics for the current company."""
    return await service.get_invitation_stats(company_id)


@router.delete("/{invitation_id}")
async def cancel_invitation(
    invitation_id: str,
    company_id: str = Depends(_company_id),
    service: InvitationService = Depends(_service),
    _current_user: User = Depends(deps.require_role("TENANT_ADMIN")),
) -> dict:
    """
    Cancel a pending invitation.

    Requires TENANT_ADMIN role.
    """
    success = await service.cancel_invitation(invitation_id, company_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found or already processed",
        )
    return {"success": True, "message": "Invitation cancelled"}


@router.post("/{invitation_id}/resend", response_model=ResendInvitationResponse)
async def resend_invitation(
    invitation_id: str,
    company_id: str = Depends(_company_id),
    service: InvitationService = Depends(_service),
    _current_user: User = Depends(deps.require_role("TENANT_ADMIN")),
) -> ResendInvitationResponse:
    """
    Resend an invitation email.

    Generates a new token and extends expiration. Requires TENANT_ADMIN role.
    """
    result = await service.resend_invitation(invitation_id, company_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found or not pending",
        )
    return result


# Public endpoint for accepting invitations
@router.post("/accept", response_model=AcceptInvitationResponse)
async def accept_invitation(
    data: AcceptInvitationRequest,
    request: Request,
    service: InvitationService = Depends(_service),
) -> AcceptInvitationResponse:
    """
    Accept an invitation and create user account.

    This is a public endpoint - no authentication required.
    The token in the request validates the invitation.
    """
    ip_address = request.client.host if request.client else None
    return await service.accept_invitation(data, ip_address)


# Public endpoint to validate token
@router.get("/validate/{token}")
async def validate_invitation_token(
    token: str,
    service: InvitationService = Depends(_service),
) -> dict:
    """
    Validate an invitation token.

    Public endpoint to check if a token is valid before showing the accept form.
    """
    invitation = await service.get_invitation_by_token(token)

    if not invitation:
        return {
            "valid": False,
            "message": "Invalid invitation link",
        }

    if invitation.status != "pending":
        return {
            "valid": False,
            "message": f"This invitation has been {invitation.status}",
        }

    from datetime import datetime, timezone
    if invitation.expires_at < datetime.now(timezone.utc):
        return {
            "valid": False,
            "message": "This invitation has expired",
        }

    # Get company name for display
    from app.models.company import Company
    company = await service.db.get(Company, invitation.company_id)

    return {
        "valid": True,
        "email": invitation.email,
        "company_name": company.name if company else "FreightOps",
        "first_name": invitation.first_name,
        "last_name": invitation.last_name,
        "expires_at": invitation.expires_at.isoformat(),
    }
