from sqlalchemy import Column, String, DateTime, Integer, Numeric, func, Date, JSON
from app.config.db import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True, nullable=False)
    companyId = Column(String, index=True, nullable=False)

    # Company & Contact
    name = Column(String, nullable=False)
    contactPerson = Column(String)
    email = Column(String)
    phone = Column(String)

    # Address
    address = Column(String)
    city = Column(String)
    state = Column(String)
    zipCode = Column(String)

    # Financials
    creditLimit = Column(Numeric)
    paymentTerms = Column(Integer)
    status = Column(String, default="active")  # active | inactive | suspended
    totalRevenue = Column(Numeric, default=0)
    lastOrder = Column(Date)
    # Extra structured data for additional fields from UI
    details = Column(JSON)

    # Timestamps
    createdAt = Column(DateTime, server_default=func.now())
    updatedAt = Column(DateTime, server_default=func.now(), onupdate=func.now())
