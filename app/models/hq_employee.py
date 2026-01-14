"""HQ Employee model for SaaS admin users."""

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, Numeric, String, func
import enum
from typing import Set

from app.models.base import Base


class HQRole(str, enum.Enum):
    """HQ Employee roles with hierarchical permissions."""
    SUPER_ADMIN = "SUPER_ADMIN"      # Full system access, can manage other admins
    ADMIN = "ADMIN"                   # Most access, cannot manage super admins
    HR_MANAGER = "HR_MANAGER"         # HR, payroll, employee management
    SALES_MANAGER = "SALES_MANAGER"   # Tenants, contracts, quotes, credits
    ACCOUNTANT = "ACCOUNTANT"         # Billing, GL, A/R, A/P, payouts
    SUPPORT = "SUPPORT"               # Read-only access to tenants and basic info


class HQPermission(str, enum.Enum):
    """HQ Portal permissions."""
    # System
    MANAGE_EMPLOYEES = "manage_employees"
    MANAGE_ADMINS = "manage_admins"
    MANAGE_SYSTEM = "manage_system"
    VIEW_AUDIT_LOGS = "view_audit_logs"

    # Tenant Management
    VIEW_TENANTS = "view_tenants"
    MANAGE_TENANTS = "manage_tenants"
    DELETE_TENANTS = "delete_tenants"

    # Sales
    VIEW_CONTRACTS = "view_contracts"
    MANAGE_CONTRACTS = "manage_contracts"
    VIEW_QUOTES = "view_quotes"
    MANAGE_QUOTES = "manage_quotes"
    VIEW_CREDITS = "view_credits"
    MANAGE_CREDITS = "manage_credits"

    # Accounting
    VIEW_ACCOUNTING = "view_accounting"
    MANAGE_ACCOUNTING = "manage_accounting"
    VIEW_GL = "view_gl"
    MANAGE_GL = "manage_gl"
    VIEW_PAYOUTS = "view_payouts"
    MANAGE_PAYOUTS = "manage_payouts"

    # Banking
    VIEW_BANKING = "view_banking"
    MANAGE_BANKING = "manage_banking"

    # HR
    VIEW_HR = "view_hr"
    MANAGE_HR = "manage_hr"
    VIEW_PAYROLL = "view_payroll"
    MANAGE_PAYROLL = "manage_payroll"


# Role to Permission mapping
HQ_ROLE_PERMISSIONS: dict[HQRole, Set[HQPermission]] = {
    HQRole.SUPER_ADMIN: set(HQPermission),  # All permissions

    HQRole.ADMIN: {
        HQPermission.MANAGE_EMPLOYEES,
        HQPermission.VIEW_AUDIT_LOGS,
        HQPermission.VIEW_TENANTS, HQPermission.MANAGE_TENANTS,
        HQPermission.VIEW_CONTRACTS, HQPermission.MANAGE_CONTRACTS,
        HQPermission.VIEW_QUOTES, HQPermission.MANAGE_QUOTES,
        HQPermission.VIEW_CREDITS, HQPermission.MANAGE_CREDITS,
        HQPermission.VIEW_ACCOUNTING, HQPermission.MANAGE_ACCOUNTING,
        HQPermission.VIEW_GL, HQPermission.MANAGE_GL,
        HQPermission.VIEW_PAYOUTS, HQPermission.MANAGE_PAYOUTS,
        HQPermission.VIEW_BANKING, HQPermission.MANAGE_BANKING,
        HQPermission.VIEW_HR, HQPermission.MANAGE_HR,
        HQPermission.VIEW_PAYROLL, HQPermission.MANAGE_PAYROLL,
    },

    HQRole.HR_MANAGER: {
        HQPermission.VIEW_TENANTS,
        HQPermission.VIEW_HR, HQPermission.MANAGE_HR,
        HQPermission.VIEW_PAYROLL, HQPermission.MANAGE_PAYROLL,
    },

    HQRole.SALES_MANAGER: {
        HQPermission.VIEW_TENANTS, HQPermission.MANAGE_TENANTS,
        HQPermission.VIEW_CONTRACTS, HQPermission.MANAGE_CONTRACTS,
        HQPermission.VIEW_QUOTES, HQPermission.MANAGE_QUOTES,
        HQPermission.VIEW_CREDITS, HQPermission.MANAGE_CREDITS,
    },

    HQRole.ACCOUNTANT: {
        HQPermission.VIEW_TENANTS,
        HQPermission.VIEW_CONTRACTS,
        HQPermission.VIEW_ACCOUNTING, HQPermission.MANAGE_ACCOUNTING,
        HQPermission.VIEW_GL, HQPermission.MANAGE_GL,
        HQPermission.VIEW_PAYOUTS, HQPermission.MANAGE_PAYOUTS,
        HQPermission.VIEW_BANKING,
    },

    HQRole.SUPPORT: {
        HQPermission.VIEW_TENANTS,
        HQPermission.VIEW_CONTRACTS,
        HQPermission.VIEW_QUOTES,
    },
}


def has_hq_permission(role: HQRole, permission: HQPermission) -> bool:
    """Check if a role has a specific permission."""
    return permission in HQ_ROLE_PERMISSIONS.get(role, set())


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
    title = Column(String, nullable=True)  # Job title
    phone = Column(String, nullable=True)
    hire_date = Column(DateTime, nullable=True)  # Date of hire
    salary = Column(Integer, nullable=True)  # Annual salary
    emergency_contact = Column(String, nullable=True)  # Emergency contact name
    emergency_phone = Column(String, nullable=True)  # Emergency contact phone
    is_active = Column(Boolean, nullable=False, default=True)
    must_change_password = Column(Boolean, nullable=False, default=False)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Master Spec Module 4: Affiliate & Sales - Referral Codes
    referral_code = Column(String, nullable=True, unique=True, comment="Master Spec: Unique referral code for this agent")
    referral_code_generated_at = Column(DateTime, nullable=True, comment="Master Spec: When referral code was generated")

    # Master Spec Module 4: Commission Rates
    commission_rate_mrr = Column(Numeric(5, 4), nullable=True, comment="Master Spec: Commission % on MRR (e.g., 0.1000 = 10%)")
    commission_rate_setup = Column(Numeric(5, 4), nullable=True, comment="Master Spec: Commission % on setup fees")
    commission_rate_fintech = Column(Numeric(5, 4), nullable=True, comment="Master Spec: Commission % on fintech revenue")

    # Master Spec Module 4: Performance Metrics
    lifetime_referrals = Column(Integer, nullable=True, default=0, comment="Master Spec: Total tenants referred by this agent")
    lifetime_commission_earned = Column(Numeric(12, 2), nullable=True, default=0, comment="Master Spec: Total commissions earned")
