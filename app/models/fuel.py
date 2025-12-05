from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class FuelCard(Base):
    """Physical or virtual fuel card assigned to a driver/truck."""

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    # Card details
    card_number = Column(String, nullable=False)  # Last 4 digits for display (masked)
    card_number_full = Column(String, nullable=True)  # Encrypted full number if stored
    card_provider = Column(String, nullable=False)  # wex, comdata, efs, fleetcor, motive, other
    card_type = Column(String, nullable=False, default="physical")  # physical, virtual
    card_nickname = Column(String, nullable=True)  # User-friendly name

    # Assignment
    driver_id = Column(String, ForeignKey("driver.id"), nullable=True, index=True)
    truck_id = Column(String, nullable=True, index=True)  # Equipment ID

    # Card status
    status = Column(String, nullable=False, default="active")  # active, inactive, lost, expired
    expiration_date = Column(Date, nullable=True)

    # External tracking
    external_id = Column(String, nullable=True, index=True)  # Provider's card ID
    external_source = Column(String, nullable=True)  # Integration source

    # Limits
    daily_limit = Column(Numeric(12, 2), nullable=True)
    transaction_limit = Column(Numeric(12, 2), nullable=True)

    # Metadata
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    company = relationship("Company")
    driver = relationship("Driver")


class FuelTransaction(Base):
    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    driver_id = Column(String, ForeignKey("driver.id"), nullable=True, index=True)
    truck_id = Column(String, nullable=True, index=True)  # Equipment ID
    load_id = Column(String, nullable=True, index=True)  # Associated load for IFTA tracking

    # External integration tracking (WEX, Motive, etc.)
    external_id = Column(String, nullable=True, index=True)  # External system transaction ID
    external_source = Column(String, nullable=True)  # Source system (wex_encompass, motive, etc.)

    transaction_date = Column(Date, nullable=False)
    jurisdiction = Column(String, nullable=True)
    location = Column(String, nullable=True)
    gallons = Column(Numeric(12, 3), nullable=False)
    cost = Column(Numeric(12, 2), nullable=False)
    price_per_gallon = Column(Numeric(8, 4), nullable=True)
    fuel_card = Column(String, nullable=True)

    # Transaction status for reconciliation
    status = Column(String, nullable=True, default="posted")  # pending, posted, cancelled
    posted_at = Column(DateTime, nullable=True)

    metadata_text = Column("metadata", String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    company = relationship("Company")
    driver = relationship("Driver")


class JurisdictionRollup(Base):
    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    jurisdiction = Column(String, nullable=False)

    gallons = Column(Numeric(12, 3), nullable=False, default=0)
    taxable_gallons = Column(Numeric(12, 3), nullable=False, default=0)
    miles = Column(Numeric(12, 1), nullable=False, default=0)
    tax_due = Column(Numeric(12, 2), nullable=False, default=0)
    surcharge_due = Column(Numeric(12, 2), nullable=True)

    last_trip_date = Column(Date, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    company = relationship("Company")

