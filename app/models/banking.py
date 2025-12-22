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


# =============================================================================
# Banking Statement Model (Synctera Integration)
# =============================================================================


class BankingStatement(Base):
    """Monthly account statement from Synctera."""

    __tablename__ = "banking_statement"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    account_id = Column(String, ForeignKey("banking_account.id"), nullable=False, index=True)
    synctera_id = Column(String, nullable=True, unique=True, index=True)  # Synctera statement ID

    # Statement period
    statement_date = Column(Date, nullable=False)  # End of period date
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # Balances
    opening_balance = Column(Numeric(14, 2), nullable=False, default=0)
    closing_balance = Column(Numeric(14, 2), nullable=False, default=0)
    total_credits = Column(Numeric(14, 2), nullable=False, default=0)
    total_debits = Column(Numeric(14, 2), nullable=False, default=0)
    transaction_count = Column(Integer, nullable=False, default=0)

    # PDF storage
    pdf_url = Column(String, nullable=True)  # URL to generated PDF
    pdf_generated_at = Column(DateTime, nullable=True)

    # Status
    status = Column(String, nullable=False, default="pending")  # pending, available, generating

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


# =============================================================================
# Banking Document Model (Synctera Integration)
# =============================================================================


class BankingDocument(Base):
    """Document record for banking (agreements, tax forms, etc.)."""

    __tablename__ = "banking_document"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    customer_id = Column(String, ForeignKey("banking_customer.id"), nullable=True, index=True)
    account_id = Column(String, ForeignKey("banking_account.id"), nullable=True, index=True)
    synctera_id = Column(String, nullable=True, unique=True, index=True)  # Synctera document ID

    # Document info
    document_type = Column(String, nullable=False)  # account_agreement, fee_schedule, tax_1099, etc.
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # File info
    file_url = Column(String, nullable=True)
    file_name = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String, nullable=True)

    # Tax document specific
    year = Column(Integer, nullable=True)  # For tax documents

    # Status
    status = Column(String, nullable=False, default="pending")  # pending, available, generating, expired
    expires_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


# =============================================================================
# Banking Dispute Model (Synctera Integration)
# =============================================================================


class BankingDispute(Base):
    """Transaction dispute record for chargeback processing."""

    __tablename__ = "banking_dispute"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    account_id = Column(String, ForeignKey("banking_account.id"), nullable=False, index=True)
    transaction_id = Column(String, nullable=False, index=True)  # Reference to disputed transaction
    synctera_id = Column(String, nullable=True, unique=True, index=True)  # Synctera dispute ID

    # Transaction info (cached for display)
    transaction_date = Column(DateTime, nullable=True)
    transaction_amount = Column(Numeric(12, 2), nullable=True)
    transaction_description = Column(String, nullable=True)
    merchant_name = Column(String, nullable=True)

    # Dispute details
    reason = Column(String, nullable=False)  # NO_CARDHOLDER_AUTHORIZATION, FRAUD, DUPLICATE, etc.
    reason_details = Column(Text, nullable=True)
    disputed_amount = Column(Numeric(12, 2), nullable=False)

    # Status tracking (Synctera lifecycle)
    status = Column(String, nullable=False, default="submitted")  # submitted, under_review, pending_documentation, resolved_in_favor, resolved_against, withdrawn, closed
    lifecycle_state = Column(String, nullable=True)  # PENDING_ACTION, CHARGEBACK, REPRESENTMENT, PRE_ARBITRATION, ARBITRATION, DENIED, WRITE_OFF
    decision = Column(String, nullable=True)  # WON, LOST, ONGOING, RESOLVED, NONE
    credit_status = Column(String, nullable=True)  # NONE, PROVISIONAL, FINAL

    # Credit info
    provisional_credit = Column(Numeric(12, 2), nullable=True)
    provisional_credit_date = Column(DateTime, nullable=True)

    # Resolution
    resolution_date = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Supporting documents (JSON array of URLs)
    documents = Column(JSON, nullable=True)

    # Timestamps
    date_customer_reported = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


# =============================================================================
# Banking Check Deposit Model
# =============================================================================


class BankingCheckDeposit(Base):
    """Mobile check deposit record."""

    __tablename__ = "banking_check_deposit"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    account_id = Column(String, ForeignKey("banking_account.id"), nullable=False, index=True)
    synctera_id = Column(String, nullable=True, unique=True, index=True)  # Synctera deposit ID

    # Check details
    amount = Column(Numeric(12, 2), nullable=False)
    check_number = Column(String, nullable=True)
    memo = Column(String, nullable=True)

    # Check images
    front_image_url = Column(String, nullable=False)
    back_image_url = Column(String, nullable=False)

    # Status tracking
    status = Column(String, nullable=False, default="pending")  # pending, approved, rejected, processing, completed
    rejection_reason = Column(Text, nullable=True)

    # Processing info
    initiated_by = Column(String, nullable=True)  # User ID
    processed_at = Column(DateTime, nullable=True)
    available_at = Column(DateTime, nullable=True)  # When funds become available

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


# =============================================================================
# Banking Fraud Report Model
# =============================================================================


class BankingFraudReport(Base):
    """Fraud report for suspected fraudulent activity."""

    __tablename__ = "banking_fraud_report"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    account_id = Column(String, ForeignKey("banking_account.id"), nullable=False, index=True)
    card_id = Column(String, ForeignKey("banking_card.id"), nullable=True, index=True)
    synctera_id = Column(String, nullable=True, unique=True, index=True)  # Synctera case ID

    # Affected transactions (JSON array of transaction IDs)
    transaction_ids = Column(JSON, nullable=True)

    # Fraud details
    fraud_type = Column(String, nullable=False)  # unauthorized, lost_card, stolen_card, counterfeit, account_takeover, other
    description = Column(Text, nullable=True)

    # Status tracking
    status = Column(String, nullable=False, default="submitted")  # submitted, investigating, resolved, closed
    resolution_notes = Column(Text, nullable=True)

    # Reporting info
    reported_by = Column(String, nullable=True)  # User ID
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


# =============================================================================
# Banking Transfer Model (for tracking transfers)
# =============================================================================


class BankingTransfer(Base):
    """Transfer record for internal, ACH, and wire transfers."""

    __tablename__ = "banking_transfer"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    external_id = Column(String, nullable=True, unique=True, index=True)  # Synctera transfer ID

    # Transfer type
    transfer_type = Column(String, nullable=False)  # internal, ach, wire

    # Accounts
    from_account_id = Column(String, ForeignKey("banking_account.id"), nullable=False, index=True)
    to_account_id = Column(String, ForeignKey("banking_account.id"), nullable=True, index=True)  # For internal transfers

    # Amount
    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String, nullable=False, default="USD")
    fee_amount = Column(Numeric(10, 2), nullable=True)

    # Recipient info (for ACH/Wire)
    recipient_id = Column(String, nullable=True)  # Saved recipient ID
    recipient_name = Column(String, nullable=True)
    recipient_routing_number = Column(String, nullable=True)
    recipient_account_number = Column(String, nullable=True)
    recipient_account_type = Column(String, nullable=True)  # checking, savings
    recipient_bank_name = Column(String, nullable=True)

    # Wire-specific fields
    wire_type = Column(String, nullable=True)  # domestic, international
    recipient_swift_code = Column(String, nullable=True)
    recipient_address = Column(JSON, nullable=True)

    # Transfer details
    description = Column(String, nullable=True)
    scheduled_date = Column(DateTime, nullable=True)
    estimated_completion_date = Column(DateTime, nullable=True)

    # Status tracking
    status = Column(String, nullable=False, default="pending")  # pending, processing, completed, failed, cancelled
    error_message = Column(Text, nullable=True)

    # Processing info
    initiated_by = Column(String, nullable=True)  # User ID
    processed_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


# =============================================================================
# Banking ACH Recipient Model (saved recipients)
# =============================================================================


class BankingACHRecipient(Base):
    """Saved ACH recipient for faster transfers."""

    __tablename__ = "banking_ach_recipient"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    # Recipient details
    name = Column(String, nullable=False)
    routing_number = Column(String, nullable=False)
    account_number = Column(String, nullable=False)  # Should be encrypted in production
    account_type = Column(String, nullable=False)  # checking, savings

    # Metadata
    nickname = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
