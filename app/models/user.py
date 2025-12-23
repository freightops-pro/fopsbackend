from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class User(Base):
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)

    # Profile fields
    phone = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    timezone = Column(String, nullable=True, default="America/Chicago")
    job_title = Column(String, nullable=True)

    # Legacy role column - kept for backwards compatibility during migration
    # New code should use user_roles relationship instead
    role = Column(String, nullable=True, default=None)

    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    must_change_password = Column(Boolean, nullable=False, default=False)

    # Email verification
    email_verified = Column(Boolean, nullable=False, default=False)
    email_verification_token = Column(String, nullable=True)
    email_verification_sent_at = Column(DateTime, nullable=True)

    # Account security
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String, nullable=True)
    password_changed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    company = relationship("Company", back_populates="users")

    # RBAC: Many-to-many relationship with roles
    user_roles = relationship(
        "UserRole",
        back_populates="user",
        foreign_keys="UserRole.user_id",
        cascade="all, delete-orphan"
    )

