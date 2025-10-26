from sqlalchemy import Column, String, DateTime, Numeric, Date, JSON, func, Text
from app.config.db import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String, primary_key=True, nullable=False)
    companyId = Column(String, index=True, nullable=False)

    # Header Information
    invoiceNumber = Column(String, nullable=False, index=True)
    invoiceDate = Column(Date, nullable=False)
    consigneePO = Column(String, nullable=True)
    shipperBL = Column(String, nullable=True)
    shippingSCAC = Column(String, nullable=True)
    paymentMethod = Column(String, default="prepaid")  # prepaid, collect
    deliveryDate = Column(Date, nullable=True)
    actualPickupDate = Column(Date, nullable=True)
    transportationMethod = Column(String, default="ltl")  # ltl, ftl, intermodal
    currencyCode = Column(String, default="USD")

    # Bill To Information
    billToName = Column(String, nullable=False)
    billToAddress = Column(Text, nullable=False)
    billToCodeType = Column(String, default="assigned_by_buyer")
    billToCode = Column(String, nullable=True)

    # Shipper Information
    shipperName = Column(String, nullable=False)
    shipperAddress = Column(Text, nullable=False)
    shipperCodeType = Column(String, default="assigned_by_buyer")
    shipperCode = Column(String, nullable=True)

    # Consignee Information
    consigneeName = Column(String, nullable=False)
    consigneeAddress = Column(Text, nullable=False)
    consigneeCodeType = Column(String, default="assigned_by_buyer")
    consigneeCode = Column(String, nullable=True)

    # Line Items (stored as JSON)
    lineItems = Column(JSON, nullable=False, default=list)

    # Additional Load Details
    routingSequenceCode = Column(String, default="origin_carrier")
    cityOfExchange = Column(String, nullable=True)
    equipmentInitial = Column(String, nullable=True)
    equipmentNumber = Column(String, nullable=True)
    ladingQty = Column(String, nullable=True)
    ladingQtyUOM = Column(String, default="pounds")
    totalWeight = Column(String, nullable=True)
    totalWeightUOM = Column(String, default="gross_weight")

    # Status and metadata
    status = Column(String, default="draft")  # draft, sent, paid, overdue
    totalAmount = Column(Numeric, nullable=False)
    notes = Column(Text, nullable=True)

    createdAt = Column(DateTime, server_default=func.now())
    updatedAt = Column(DateTime, server_default=func.now(), onupdate=func.now())
