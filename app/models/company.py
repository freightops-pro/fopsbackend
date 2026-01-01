from sqlalchemy import Boolean, Column, DateTime, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class Company(Base):
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    legal_name = Column(String, nullable=True)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String, nullable=True)
    fax = Column(String, nullable=True)
    subscriptionPlan = Column("subscription_plan", String, nullable=False, default="pro")
    isActive = Column("is_active", Boolean, nullable=False, default=True)
    businessType = Column("business_type", String, nullable=True)
    dotNumber = Column("dot_number", String, nullable=True, unique=True)
    mcNumber = Column("mc_number", String, nullable=True, unique=True)
    tax_id = Column(String, nullable=True)
    primaryContactName = Column("primary_contact_name", String, nullable=True)

    # Address fields
    address_line1 = Column(String, nullable=True)
    address_line2 = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    zip_code = Column(String, nullable=True)

    # Additional fields
    description = Column(Text, nullable=True)
    website = Column(String, nullable=True)
    year_founded = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)

    createdAt = Column("created_at", DateTime, nullable=False, server_default=func.now())
    updatedAt = Column("updated_at", DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    users = relationship("User", back_populates="company", cascade="all, delete-orphan")
    drivers = relationship("Driver", back_populates="company", cascade="all, delete-orphan")
    automationRules = relationship("AutomationRule", back_populates="company", cascade="all, delete-orphan")
    integrations = relationship("CompanyIntegration", back_populates="company", cascade="all, delete-orphan")
    workers = relationship("Worker", back_populates="company", cascade="all, delete-orphan")
    subscription = relationship("Subscription", back_populates="company", uselist=False, cascade="all, delete-orphan")
    locations = relationship("Location", back_populates="company", cascade="all, delete-orphan")

    # RBAC: Custom roles defined by this tenant
    custom_roles = relationship("Role", back_populates="company", cascade="all, delete-orphan")

