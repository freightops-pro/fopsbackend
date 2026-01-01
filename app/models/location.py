from sqlalchemy import Column, DateTime, ForeignKey, Float, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class Location(Base):
    """Address book for storing reusable pickup/delivery locations (shippers, consignees, receivers)"""
    __tablename__ = "location"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    # Location identification
    business_name = Column(String, nullable=False)
    location_type = Column(String, nullable=True)  # shipper, consignee, both, warehouse, terminal, etc.

    # Address fields
    address = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)
    postal_code = Column(String, nullable=False)
    country = Column(String, nullable=True, default="US")

    # GPS coordinates (for mapping and distance calculations)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

    # Contact information
    contact_name = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)

    # Additional details
    special_instructions = Column(String, nullable=True)  # Dock info, gate codes, etc.
    operating_hours = Column(String, nullable=True)  # e.g., "Mon-Fri 8AM-5PM"

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationship to company
    company = relationship("Company", back_populates="locations")
