from sqlalchemy import Boolean, Column, DateTime, Date, ForeignKey, Integer, Numeric, String, Text, JSON, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class BankingCustomer(Base):
    __tablename__ = "banking_customer"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="pending")
    external_id = Column(String, nullable=True, unique=True)
    synctera_business_id = Column(String, nullable=True, unique=True, index=True)  # Synctera business ID
    kyb_status = Column(String, nullable=True)  # pending, verified, rejected
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    accounts = relationship("BankingAccount", back_populates="customer", cascade="all, delete-orphan")


class BankingAccount(Base):
    __tablename__ = "banking_account"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    customer_id = Column(String, ForeignKey("banking_customer.id"), nullable=False, index=True)
    account_type = Column(String, nullable=False)
    nickname = Column(String, nullable=True)
    currency = Column(String, nullable=False, default="USD")
    balance = Column(Numeric(14, 2), nullable=False, default=0)
    current_balance = Column(Numeric(14, 2), nullable=True)  # Current balance from Synctera
    available_balance = Column(Numeric(14, 2), nullable=True)  # Available balance from Synctera
    status = Column(String, nullable=False, default="inactive")
    external_id = Column(String, nullable=True, unique=True)
    synctera_id = Column(String, nullable=True, unique=True, index=True)  # Synctera account ID
    account_number = Column(String, nullable=True)  # Masked account number
    routing_number = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    customer = relationship("BankingCustomer", back_populates="accounts")
    cards = relationship("BankingCard", back_populates="account", cascade="all, delete-orphan")
    transactions = relationship("BankingTransaction", back_populates="account", cascade="all, delete-orphan")


class BankingCard(Base):
    __tablename__ = "banking_card"

    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("banking_account.id"), nullable=False, index=True)
    cardholder_name = Column(String, nullable=False)
    last_four = Column(String, nullable=False)
    card_type = Column(String, nullable=False)  # virtual, physical
    card_form = Column(String, nullable=True)  # VIRTUAL, PHYSICAL
    status = Column(String, nullable=False, default="inactive")
    expiration_month = Column(String, nullable=True)
    expiration_year = Column(String, nullable=True)
    synctera_id = Column(String, nullable=True, unique=True, index=True)  # Synctera card ID
    card_product_id = Column(String, nullable=True)  # Synctera card product ID
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    account = relationship("BankingAccount", back_populates="cards")


class BankingTransaction(Base):
    __tablename__ = "banking_transaction"

    id = Column(String, primary_key=True)
    account_id = Column(String, ForeignKey("banking_account.id"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String, nullable=False, default="USD")
    description = Column(String, nullable=True)
    category = Column(String, nullable=False, default="general")
    posted_at = Column(DateTime, nullable=False)
    pending = Column(Boolean, nullable=False, default=True)
    external_id = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    account = relationship("BankingAccount", back_populates="transactions")


# =============================================================================
# Banking Application Models (Multi-step KYB Onboarding)
# =============================================================================


class BankingApplication(Base):
    """Banking application for business account opening with KYB workflow."""

    __tablename__ = "banking_application"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    reference = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, default="draft")  # draft, submitted, pending_review, approved, rejected, needs_info, synctera_error

    # Primary applicant reference
    primary_person_id = Column(String, ForeignKey("banking_person.id"), nullable=True)

    # Account selection preferences (JSON)
    account_choices = Column(JSON, nullable=True)

    # Synctera integration
    synctera_business_id = Column(String, nullable=True, index=True)  # Synctera business ID after submission

    # KYC/KYB status tracking
    kyc_status = Column(String, nullable=True)  # pending, passed, failed, needs_review, provisional, error
    kyc_provider_ref = Column(String, nullable=True)  # External KYC provider reference
    kyc_completed_at = Column(DateTime, nullable=True)

    # Submission tracking
    submitted_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    business = relationship("BankingBusiness", back_populates="application", uselist=False, cascade="all, delete-orphan")
    people = relationship("BankingPerson", back_populates="application", foreign_keys="BankingPerson.application_id", cascade="all, delete-orphan")
    documents = relationship("BankingApplicationDocument", back_populates="application", cascade="all, delete-orphan")


class BankingBusiness(Base):
    """Business details for banking application."""

    __tablename__ = "banking_business"

    id = Column(String, primary_key=True)
    application_id = Column(String, ForeignKey("banking_application.id"), nullable=False, unique=True, index=True)
    synctera_id = Column(String, nullable=True, index=True)  # Synctera business ID

    # Core business info
    legal_name = Column(String, nullable=False)
    dba = Column(String, nullable=True)
    entity_type = Column(String, nullable=False)  # sole_proprietorship, llc, corporation, partnership, non_profit, trust
    ein = Column(String, nullable=True)  # Encrypted/tokenized
    formation_date = Column(Date, nullable=True)
    state_of_formation = Column(String, nullable=True)

    # Addresses
    physical_address = Column(Text, nullable=True)
    mailing_address = Column(Text, nullable=True)

    # Contact
    phone = Column(String, nullable=True)
    website = Column(String, nullable=True)

    # Industry & operations
    naics_code = Column(String, nullable=True)
    industry_description = Column(String, nullable=True)
    employees = Column(Integer, nullable=True)
    estimated_revenue = Column(Numeric(14, 2), nullable=True)
    monthly_volume = Column(Numeric(14, 2), nullable=True)

    # Risk flags
    cash_heavy = Column(Boolean, nullable=False, default=False)
    international_transactions = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    application = relationship("BankingApplication", back_populates="business")


class BankingPerson(Base):
    """Person record for banking application (primary, owner, signer)."""

    __tablename__ = "banking_person"

    id = Column(String, primary_key=True)
    application_id = Column(String, ForeignKey("banking_application.id"), nullable=False, index=True)
    synctera_id = Column(String, nullable=True, index=True)  # Synctera person ID

    # Person type: primary, owner, signer
    person_type = Column(String, nullable=False)

    # Personal info
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    dob = Column(Date, nullable=True)
    ssn_last4 = Column(String, nullable=True)  # Last 4 only for display, full SSN encrypted separately
    ssn_token = Column(String, nullable=True)  # Tokenized SSN from KYC provider

    # Address
    address = Column(Text, nullable=True)

    # Contact
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    # Citizenship & identity
    citizenship = Column(String, nullable=True)
    id_type = Column(String, nullable=True)  # drivers_license, passport, state_id
    id_file_url = Column(String, nullable=True)

    # Ownership details (for owners)
    ownership_pct = Column(Numeric(5, 2), nullable=True)
    is_controller = Column(Boolean, nullable=False, default=False)

    # Role (for signers)
    role = Column(String, nullable=True)  # CEO, CFO, Accountant, Signer Only

    # KYC status for this person
    kyc_status = Column(String, nullable=True)
    kyc_provider_ref = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    application = relationship("BankingApplication", back_populates="people", foreign_keys=[application_id])


class BankingApplicationDocument(Base):
    """Document attached to banking application."""

    __tablename__ = "banking_application_document"

    id = Column(String, primary_key=True)
    application_id = Column(String, ForeignKey("banking_application.id"), nullable=False, index=True)

    # Document type: articles, operating_agreement, ein_letter, dba_cert, other
    doc_type = Column(String, nullable=False)
    file_name = Column(String, nullable=True)
    file_url = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String, nullable=True)

    # Upload tracking
    uploaded_by = Column(String, nullable=True)  # Person ID who uploaded
    uploaded_at = Column(DateTime, nullable=False, server_default=func.now())

    # Verification
    verified = Column(Boolean, nullable=False, default=False)
    verified_at = Column(DateTime, nullable=True)
    verified_by = Column(String, nullable=True)

    # Relationships
    application = relationship("BankingApplication", back_populates="documents")

