from sqlalchemy import Column, String, DateTime, Numeric, Date, func, ForeignKey
from sqlalchemy.orm import relationship
from app.config.db import Base


class Bill(Base):
    __tablename__ = "bills"

    id = Column(String, primary_key=True, nullable=False)
    company_id = Column("companyId", String, index=True, nullable=False)

    # Vendor Information (can be either vendorId or vendorName for flexibility)
    vendor_id = Column("vendorId", String, ForeignKey("vendors.id"), index=True, nullable=True)
    vendor_name = Column("vendorName", String, nullable=False)  # Fallback if no vendorId

    # Bill Information
    amount = Column(Numeric, nullable=False)
    bill_date = Column("billDate", Date, nullable=True)
    due_date = Column("dueDate", Date, nullable=True)
    category = Column(String, nullable=True)  # Fuel, Maintenance, Insurance, Tires, Repairs, Other
    status = Column(String, default="pending")  # pending, paid, due, overdue
    notes = Column(String, nullable=True)

    # Relationship to vendor
    vendor = relationship("Vendor", backref="bills")

    created_at = Column("createdAt", DateTime, server_default=func.now())
    updated_at = Column("updatedAt", DateTime, server_default=func.now(), onupdate=func.now())


