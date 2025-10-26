from sqlalchemy import Column, String, DateTime, Numeric, Boolean, Date, func
from app.config.db import Base


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(String, primary_key=True, nullable=False)
    company_id = Column("companyId", String, index=True, nullable=False)

    # Personal Details
    title = Column(String, nullable=True)
    first_name = Column("firstName", String, nullable=True)
    middle_name = Column("middleName", String, nullable=True)
    last_name = Column("lastName", String, nullable=True)
    suffix = Column(String, nullable=True)

    # Company Details
    company = Column(String, nullable=True)
    display_name = Column("displayName", String, nullable=False)
    print_on_check = Column("printOnCheck", String, nullable=True)

    # Address Information
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    zip_code = Column("zipCode", String, nullable=True)
    country = Column(String, nullable=True)

    # Contact Information
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    mobile = Column(String, nullable=True)
    fax = Column(String, nullable=True)
    other = Column(String, nullable=True)
    website = Column(String, nullable=True)

    # Financial Information
    billing_rate = Column("billingRate", Numeric, nullable=True)
    terms = Column(String, nullable=True)
    opening_balance = Column("openingBalance", Numeric, nullable=True)
    balance_as_of = Column("balanceAsOf", Date, nullable=True)
    account_number = Column("accountNumber", String, nullable=True)

    # 1099 Tracking
    tax_id = Column("taxId", String, nullable=True)
    track_payments_for_1099 = Column("trackPaymentsFor1099", Boolean, default=False)

    # Status
    is_active = Column("isActive", Boolean, default=True)

    created_at = Column("createdAt", DateTime, server_default=func.now())
    updated_at = Column("updatedAt", DateTime, server_default=func.now(), onupdate=func.now()) 