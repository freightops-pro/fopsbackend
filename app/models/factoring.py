from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import relationship

from app.models.base import Base


class FactoringProvider(Base):
    """Factoring company/provider configuration."""
    __tablename__ = "factoring_providers"

    id = Column(String, primary_key=True, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)

    # Provider details
    provider_name = Column(String, nullable=False)  # e.g., "TBS Factoring", "OTR Capital"
    api_key = Column(String, nullable=True)  # Encrypted API key
    api_endpoint = Column(String, nullable=True)  # API base URL
    webhook_secret = Column(String, nullable=True)  # For validating webhooks

    # Factoring terms
    factoring_rate = Column(Float, nullable=False)  # Percentage rate (e.g., 3.5 for 3.5%)
    advance_rate = Column(Float, nullable=False, default=95.0)  # Percentage advanced (e.g., 95%)
    payment_terms_days = Column(Float, nullable=True)  # Days until advance

    # Status
    is_active = Column(Boolean, default=True)
    is_configured = Column(Boolean, default=False)  # True when API credentials are set

    # Metadata
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    company = relationship("Company", back_populates="factoring_providers")
    transactions = relationship("FactoringTransaction", back_populates="provider")


class FactoringTransaction(Base):
    """Individual factoring transaction for a load/invoice."""
    __tablename__ = "factoring_transactions"

    id = Column(String, primary_key=True, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    provider_id = Column(String, ForeignKey("factoring_providers.id"), nullable=False, index=True)
    load_id = Column(String, ForeignKey("loads.id"), nullable=False, index=True)
    invoice_id = Column(String, nullable=True)  # Optional link to invoice

    # Transaction details
    invoice_amount = Column(Float, nullable=False)  # Original invoice amount
    factoring_fee = Column(Float, nullable=False)  # Fee charged by factor
    advance_amount = Column(Float, nullable=False)  # Amount advanced to carrier
    reserve_amount = Column(Float, nullable=False)  # Amount held in reserve

    # Status tracking
    status = Column(
        String,
        nullable=False,
        default="PENDING",
        index=True
    )  # PENDING, SENT, ACCEPTED, VERIFIED, FUNDED, PAID, REJECTED, CANCELLED

    # External references
    external_reference_id = Column(String, nullable=True)  # Factor's transaction ID
    batch_id = Column(String, nullable=True, index=True)  # For batch submissions

    # Timestamps
    sent_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)  # When factor verified documents
    funded_at = Column(DateTime, nullable=True)  # When advance was sent
    paid_at = Column(DateTime, nullable=True)  # When customer paid factor
    rejected_at = Column(DateTime, nullable=True)

    # Payment details
    payment_method = Column(String, nullable=True)  # ACH, WIRE, CHECK
    payment_reference = Column(String, nullable=True)

    # Documents
    documents_submitted = Column(JSON, nullable=True)  # List of document URLs/IDs
    rejection_reason = Column(String, nullable=True)

    # Notes and metadata
    notes = Column(String, nullable=True)
    metadata_json = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    company = relationship("Company")
    provider = relationship("FactoringProvider", back_populates="transactions")
    load = relationship("Load", back_populates="factoring_transaction")
