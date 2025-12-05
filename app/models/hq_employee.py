"""HQ Employee model for SaaS admin users."""

from sqlalchemy import Boolean, Column, DateTime, Enum, String, func
import enum

from app.models.base import Base


class HQRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    HR_MANAGER = "HR_MANAGER"
    SALES_MANAGER = "SALES_MANAGER"
    ACCOUNTANT = "ACCOUNTANT"
    SUPPORT = "SUPPORT"


class HQEmployee(Base):
    """HQ Admin Portal employee/user."""

    __tablename__ = "hq_employee"

    id = Column(String, primary_key=True)
    employee_number = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    role = Column(Enum(HQRole), nullable=False, default=HQRole.SUPPORT)
    department = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    must_change_password = Column(Boolean, nullable=False, default=False)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
