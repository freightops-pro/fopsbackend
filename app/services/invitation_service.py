"""
Invitation Service for managing user invitations.

Handles:
- Creating invitations with secure tokens
- Sending invitation emails
- Accepting invitations and creating users
- Expiration and cancellation
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.company import Company
from app.models.rbac import Role, UserRole
from app.models.user_invitation import UserInvitation
from app.schemas.invitation import (
    InvitationCreate,
    InvitationResponse,
    InvitationListResponse,
    AcceptInvitationRequest,
    AcceptInvitationResponse,
    ResendInvitationResponse,
    InvitationStats,
)
from app.services.email import EmailService
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)

# Token expiration in days
INVITATION_EXPIRY_DAYS = 7


class InvitationService:
    """Service for managing user invitations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_invitation(
        self,
        company_id: str,
        invited_by: str,
        data: InvitationCreate,
    ) -> InvitationResponse:
        """
        Create a new user invitation.

        Args:
            company_id: Company the user will join
            invited_by: User ID of the inviter
            data: Invitation details

        Raises:
            ValueError: If email already exists or has pending invitation
        """
        # Check if email already exists as a user in this company
        existing_user = await self.db.execute(
            select(User).where(
                and_(
                    User.email == data.email.lower(),
                    User.company_id == company_id,
                )
            )
        )
        if existing_user.scalar_one_or_none():
            raise ValueError("A user with this email already exists in your company")

        # Check for pending invitation
        existing_invite = await self.db.execute(
            select(UserInvitation).where(
                and_(
                    UserInvitation.email == data.email.lower(),
                    UserInvitation.company_id == company_id,
                    UserInvitation.status == "pending",
                )
            )
        )
        if existing_invite.scalar_one_or_none():
            raise ValueError("A pending invitation already exists for this email")

        # Generate secure token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=INVITATION_EXPIRY_DAYS)

        # Create invitation
        invitation = UserInvitation(
            id=str(uuid4()),
            email=data.email.lower(),
            first_name=data.first_name,
            last_name=data.last_name,
            role_id=data.role_id,
            company_id=company_id,
            invited_by=invited_by,
            token=token,
            expires_at=expires_at,
            status="pending",
            message=data.message,
        )

        self.db.add(invitation)
        await self.db.commit()
        await self.db.refresh(invitation)

        # Get company and inviter info for email
        company = await self.db.get(Company, company_id)
        inviter = await self.db.get(User, invited_by)

        # Send invitation email
        await self._send_invitation_email(
            invitation=invitation,
            company_name=company.name if company else "FreightOps",
            inviter_name=f"{inviter.first_name} {inviter.last_name}" if inviter else "Your team",
        )

        return await self._to_response(invitation)

    async def list_invitations(
        self,
        company_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> InvitationListResponse:
        """List invitations for a company."""
        query = select(UserInvitation).where(
            UserInvitation.company_id == company_id
        )
        count_query = select(func.count(UserInvitation.id)).where(
            UserInvitation.company_id == company_id
        )

        if status:
            query = query.where(UserInvitation.status == status)
            count_query = count_query.where(UserInvitation.status == status)

        # Auto-expire old invitations
        await self._expire_old_invitations(company_id)

        # Get total
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated results
        offset = (page - 1) * page_size
        query = query.order_by(UserInvitation.invited_at.desc()).offset(offset).limit(page_size)

        result = await self.db.execute(query)
        invitations = result.scalars().all()

        items = [await self._to_response(inv) for inv in invitations]

        return InvitationListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_invitation_by_token(self, token: str) -> Optional[UserInvitation]:
        """Get invitation by token."""
        result = await self.db.execute(
            select(UserInvitation).where(UserInvitation.token == token)
        )
        return result.scalar_one_or_none()

    async def accept_invitation(
        self,
        data: AcceptInvitationRequest,
        ip_address: Optional[str] = None,
    ) -> AcceptInvitationResponse:
        """
        Accept an invitation and create the user account.

        Args:
            data: Acceptance details including token and password
            ip_address: IP address for audit logging
        """
        invitation = await self.get_invitation_by_token(data.token)

        if not invitation:
            return AcceptInvitationResponse(
                success=False,
                message="Invalid or expired invitation link",
            )

        if invitation.status != "pending":
            return AcceptInvitationResponse(
                success=False,
                message=f"This invitation has already been {invitation.status}",
            )

        if invitation.expires_at < datetime.now(timezone.utc):
            invitation.status = "expired"
            await self.db.commit()
            return AcceptInvitationResponse(
                success=False,
                message="This invitation has expired. Please request a new one.",
            )

        # Create the user
        user = User(
            id=str(uuid4()),
            email=invitation.email,
            hashed_password=get_password_hash(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            company_id=invitation.company_id,
            is_active=True,
            email_verified=True,  # Verified by accepting invitation
        )

        self.db.add(user)
        await self.db.flush()  # Get user ID

        # Assign role if specified
        if invitation.role_id:
            user_role = UserRole(
                id=str(uuid4()),
                user_id=user.id,
                role_id=invitation.role_id,
                assigned_by=invitation.invited_by,
            )
            self.db.add(user_role)

        # Update invitation status
        invitation.status = "accepted"
        invitation.accepted_at = datetime.now(timezone.utc)
        invitation.accepted_by_user_id = user.id

        await self.db.commit()

        logger.info(f"User {user.email} created via invitation, company: {invitation.company_id}")

        return AcceptInvitationResponse(
            success=True,
            message="Account created successfully! You can now log in.",
            user_id=user.id,
            email=user.email,
            redirect_url="/login",
        )

    async def cancel_invitation(
        self,
        invitation_id: str,
        company_id: str,
    ) -> bool:
        """Cancel a pending invitation."""
        result = await self.db.execute(
            select(UserInvitation).where(
                and_(
                    UserInvitation.id == invitation_id,
                    UserInvitation.company_id == company_id,
                    UserInvitation.status == "pending",
                )
            )
        )
        invitation = result.scalar_one_or_none()

        if not invitation:
            return False

        invitation.status = "cancelled"
        await self.db.commit()
        return True

    async def resend_invitation(
        self,
        invitation_id: str,
        company_id: str,
    ) -> Optional[ResendInvitationResponse]:
        """Resend an invitation email with new token."""
        result = await self.db.execute(
            select(UserInvitation).where(
                and_(
                    UserInvitation.id == invitation_id,
                    UserInvitation.company_id == company_id,
                    UserInvitation.status == "pending",
                )
            )
        )
        invitation = result.scalar_one_or_none()

        if not invitation:
            return None

        # Generate new token and extend expiration
        invitation.token = secrets.token_urlsafe(32)
        invitation.expires_at = datetime.now(timezone.utc) + timedelta(days=INVITATION_EXPIRY_DAYS)

        await self.db.commit()

        # Get company and inviter info
        company = await self.db.get(Company, company_id)
        inviter = await self.db.get(User, invitation.invited_by)

        # Send email
        await self._send_invitation_email(
            invitation=invitation,
            company_name=company.name if company else "FreightOps",
            inviter_name=f"{inviter.first_name} {inviter.last_name}" if inviter else "Your team",
        )

        return ResendInvitationResponse(
            success=True,
            message="Invitation email sent successfully",
            new_expires_at=invitation.expires_at,
        )

    async def get_invitation_stats(self, company_id: str) -> InvitationStats:
        """Get invitation statistics for a company."""
        # Auto-expire old invitations first
        await self._expire_old_invitations(company_id)

        result = await self.db.execute(
            select(UserInvitation.status, func.count(UserInvitation.id))
            .where(UserInvitation.company_id == company_id)
            .group_by(UserInvitation.status)
        )
        status_counts = {row[0]: row[1] for row in result.fetchall()}

        return InvitationStats(
            pending_count=status_counts.get("pending", 0),
            accepted_count=status_counts.get("accepted", 0),
            expired_count=status_counts.get("expired", 0),
            cancelled_count=status_counts.get("cancelled", 0),
        )

    async def _expire_old_invitations(self, company_id: str) -> None:
        """Mark expired invitations."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(UserInvitation).where(
                and_(
                    UserInvitation.company_id == company_id,
                    UserInvitation.status == "pending",
                    UserInvitation.expires_at < now,
                )
            )
        )
        expired = result.scalars().all()

        for inv in expired:
            inv.status = "expired"

        if expired:
            await self.db.commit()

    async def _to_response(self, invitation: UserInvitation) -> InvitationResponse:
        """Convert invitation model to response schema."""
        # Get related data
        company = await self.db.get(Company, invitation.company_id)
        inviter = await self.db.get(User, invitation.invited_by)
        role = await self.db.get(Role, invitation.role_id) if invitation.role_id else None

        return InvitationResponse(
            id=invitation.id,
            email=invitation.email,
            first_name=invitation.first_name,
            last_name=invitation.last_name,
            role_id=invitation.role_id,
            role_name=role.display_name if role else None,
            company_id=invitation.company_id,
            company_name=company.name if company else None,
            invited_by=invitation.invited_by,
            inviter_email=inviter.email if inviter else None,
            inviter_name=f"{inviter.first_name} {inviter.last_name}" if inviter else None,
            invited_at=invitation.invited_at,
            expires_at=invitation.expires_at,
            status=invitation.status,
            accepted_at=invitation.accepted_at,
            message=invitation.message,
        )

    async def _send_invitation_email(
        self,
        invitation: UserInvitation,
        company_name: str,
        inviter_name: str,
    ) -> bool:
        """Send invitation email."""
        return EmailService.send_user_invitation(
            email=invitation.email,
            token=invitation.token,
            company_name=company_name,
            inviter_name=inviter_name,
            expires_at=invitation.expires_at,
            message=invitation.message,
        )
