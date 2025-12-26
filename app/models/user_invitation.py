"""
User Invitation Model for team member invitations.

Tracks invitations sent to new users with:
- Invitation details (email, role, company)
- Token for secure acceptance
- Status tracking (pending, accepted, expired, cancelled)
- Audit trail (invited_by, accepted_at)
"""

from sqlalchemy import Column, DateTime, ForeignKey, String, func, Index
from sqlalchemy.orm import relationship

from app.models.base import Base


class UserInvitation(Base):
    """
    User invitation for onboarding new team members.

    Flow:
    1. Admin creates invitation with email and role
    2. System sends email with unique token link
    3. User clicks link, sets password, account created
    4. Invitation marked as accepted
    """
    __tablename__ = "user_invitations"

    id = Column(String, primary_key=True)

    # Who is being invited
    email = Column(String, nullable=False, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)

    # What role will they have
    role_id = Column(String, ForeignKey("roles.id"), nullable=True)

    # Which company
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    # Who invited them
    invited_by = Column(String, ForeignKey("users.id"), nullable=False)
    invited_at = Column(DateTime, nullable=False, server_default=func.now())

    # Secure token for acceptance
    token = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)

    # Status tracking
    status = Column(String, nullable=False, default="pending", index=True)

    # Acceptance details
    accepted_at = Column(DateTime, nullable=True)
    accepted_by_user_id = Column(String, ForeignKey("users.id"), nullable=True)

    # Optional message from inviter
    message = Column(String, nullable=True)

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    role = relationship("Role", foreign_keys=[role_id])
    inviter = relationship("User", foreign_keys=[invited_by])
    accepted_user = relationship("User", foreign_keys=[accepted_by_user_id])

    __table_args__ = (
        Index("idx_invitations_company_status", "company_id", "status"),
        Index("idx_invitations_email_company", "email", "company_id"),
    )
