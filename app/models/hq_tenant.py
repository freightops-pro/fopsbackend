"""HQ Tenant model for managing customer companies."""

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class TenantStatus(str, enum.Enum):
    ACTIVE = "active"
    TRIAL = "trial"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class SubscriptionTier(str, enum.Enum):
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class SubscriptionStatus(str, enum.Enum):
    """Master Spec: Subscription lifecycle status."""
    ACTIVE = "ACTIVE"
    TRIALING = "TRIALING"
    PAUSED_HARDSHIP = "PAUSED_HARDSHIP"
    CANCELLED = "CANCELLED"
    DELINQUENT = "DELINQUENT"


class BankingStatus(str, enum.Enum):
    """Master Spec: Embedded banking onboarding status."""
    NOT_STARTED = "NOT_STARTED"
    KYB_PENDING = "KYB_PENDING"
    KYB_APPROVED = "KYB_APPROVED"
    KYB_REJECTED = "KYB_REJECTED"
    ACCOUNT_OPENED = "ACCOUNT_OPENED"
    ACCOUNT_CLOSED = "ACCOUNT_CLOSED"


class PayrollStatus(str, enum.Enum):
    """Master Spec: Payroll system onboarding status."""
    NOT_STARTED = "NOT_STARTED"
    ONBOARDING = "ONBOARDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class HQTenant(Base):
    """
    HQ-level tenant management.
    Links to Company model for tenant-specific data.
    """

    __tablename__ = "hq_tenant"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), unique=True, nullable=False, index=True)
    status = Column(
        Enum(TenantStatus, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=TenantStatus.TRIAL
    )
    subscription_tier = Column(
        Enum(SubscriptionTier, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=SubscriptionTier.STARTER
    )
    monthly_rate = Column(Numeric(10, 2), nullable=True)
    setup_fee = Column(Numeric(10, 2), nullable=True, default=0)
    billing_email = Column(String, nullable=True)
    stripe_customer_id = Column(String, nullable=True, unique=True)
    stripe_subscription_id = Column(String, nullable=True, unique=True)
    trial_ends_at = Column(DateTime, nullable=True)
    subscription_started_at = Column(DateTime, nullable=True)
    current_period_ends_at = Column(DateTime, nullable=True)
    assigned_sales_rep_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Master Spec Module 2: Tenant Management - Subscription Lifecycle
    subscription_status = Column(
        Enum(SubscriptionStatus, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=True,
        comment="Master Spec: Enhanced subscription status (ACTIVE, TRIALING, PAUSED_HARDSHIP, CANCELLED, DELINQUENT)"
    )
    paused_at = Column(DateTime, nullable=True, comment="Master Spec: When subscription was paused")
    pause_reason = Column(String, nullable=True, comment="Master Spec: Reason for hardship pause")
    pause_expires_at = Column(DateTime, nullable=True, comment="Master Spec: When hardship pause expires (auto-resume)")
    paused_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True, comment="Master Spec: HQ employee who approved pause")

    # Master Spec Module 2: Referral Tracking
    referred_by_agent_id = Column(String, ForeignKey("hq_employee.id"), nullable=True, comment="Master Spec: Agent who referred this tenant")
    referral_code_used = Column(String, nullable=True, comment="Master Spec: Referral code used during signup")
    parent_tenant_id = Column(String, ForeignKey("hq_tenant.id"), nullable=True, comment="Master Spec: Parent tenant if multi-org")

    # Master Spec Module 3: Embedded Finance - Banking
    banking_status = Column(
        Enum(BankingStatus, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=True,
        default=BankingStatus.NOT_STARTED,
        comment="Master Spec: Synctera KYB onboarding status"
    )
    synctera_account_id = Column(String, nullable=True, unique=True, comment="Master Spec: Synctera business account ID")

    # Master Spec Module 3: Embedded Finance - Payroll
    payroll_status = Column(
        Enum(PayrollStatus, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=True,
        default=PayrollStatus.NOT_STARTED,
        comment="Master Spec: CheckHQ payroll onboarding status"
    )
    checkhq_company_id = Column(String, nullable=True, unique=True, comment="Master Spec: CheckHQ company ID")

    # Master Spec Module 3: MRR & Financial Metrics
    mrr_amount = Column(Numeric(10, 2), nullable=True, comment="Master Spec: Current monthly recurring revenue")
    fintech_take_rate = Column(Numeric(5, 4), nullable=True, comment="Master Spec: Revenue share from fintech services (e.g., 0.0025)")
    total_deposits_mtd = Column(Numeric(12, 2), nullable=True, comment="Master Spec: Total deposits this month (for fintech rev calc)")
    active_employees_paid = Column(Numeric(10, 0), nullable=True, comment="Master Spec: Active employees on payroll")
    lifetime_value = Column(Numeric(12, 2), nullable=True, comment="Master Spec: Total revenue from this tenant")
    churn_risk_score = Column(Numeric(3, 2), nullable=True, comment="Master Spec: ML churn prediction (0.00-1.00)")

    # Master Spec Module 2: Impersonation Tracking
    last_impersonated_at = Column(DateTime, nullable=True, comment="Master Spec: Last time an admin impersonated this tenant")
    last_impersonated_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True, comment="Master Spec: Admin who last impersonated")

    # Relationships
    company = relationship("Company", backref="hq_tenant")
    assigned_sales_rep = relationship("HQEmployee", foreign_keys=[assigned_sales_rep_id])
    contracts = relationship("HQContract", back_populates="tenant", cascade="all, delete-orphan")
    quotes = relationship("HQQuote", back_populates="tenant", cascade="all, delete-orphan")
    credits = relationship("HQCredit", back_populates="tenant", cascade="all, delete-orphan")
    payouts = relationship("HQPayout", back_populates="tenant", cascade="all, delete-orphan")
    customer = relationship("HQCustomer", back_populates="tenant", uselist=False)
    subscription = relationship("HQSubscription", back_populates="tenant", uselist=False)

    # Master Spec: New relationships
    paused_by = relationship("HQEmployee", foreign_keys=[paused_by_id])
    referred_by_agent = relationship("HQEmployee", foreign_keys=[referred_by_agent_id])
    parent_tenant = relationship(
        "HQTenant",
        remote_side=[id],
        foreign_keys=[parent_tenant_id],
        back_populates="child_tenants"
    )
    child_tenants = relationship(
        "HQTenant",
        foreign_keys="HQTenant.parent_tenant_id",
        back_populates="parent_tenant"
    )
    last_impersonated_by = relationship("HQEmployee", foreign_keys=[last_impersonated_by_id])
