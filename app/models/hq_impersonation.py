"""HQ Impersonation Log model for admin access tracking."""

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class HQImpersonationLog(Base):
    """Master Spec Module 2: Track when HQ admins impersonate tenant accounts."""

    __tablename__ = "hq_impersonation_log"

    id = Column(String, primary_key=True)

    # Who impersonated
    admin_id = Column(String, ForeignKey("hq_employee.id"), nullable=False, index=True)

    # Which tenant
    tenant_id = Column(String, ForeignKey("hq_tenant.id"), nullable=False, index=True)

    # Session details
    session_token = Column(String, nullable=False, unique=True, index=True, comment="Temporary impersonation token")
    expires_at = Column(DateTime, nullable=False, comment="Token expiration (e.g., 1 hour)")

    # Tracking
    started_at = Column(DateTime, nullable=False, server_default=func.now())
    ended_at = Column(DateTime, nullable=True, comment="When session ended (logout or timeout)")

    # Audit
    reason = Column(Text, nullable=True, comment="Why impersonation was needed (support ticket #, etc.)")
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)

    # Relationships
    admin = relationship("HQEmployee")
    tenant = relationship("HQTenant")
