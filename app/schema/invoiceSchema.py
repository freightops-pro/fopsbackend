from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal


class LineItemBase(BaseModel):
    lineNumber: int
    description: str
    billedAsQty: str
    qtyPieces: int
    weight: str
    freightRate: str
    charge: str
    weightUOM: str = "gross_weight"
    rateType: str = "flat_rate"
    chargeCode: str = "freight"
    chargeDescription: str = "Freight Charge"
    freightClassCode: Optional[str] = None
    ladingDescription: Optional[str] = None


class InvoiceBase(BaseModel):
    # Header Information
    invoiceNumber: str
    invoiceDate: date
    consigneePO: Optional[str] = None
    shipperBL: Optional[str] = None
    shippingSCAC: Optional[str] = None
    paymentMethod: str = "prepaid"
    deliveryDate: Optional[date] = None
    actualPickupDate: Optional[date] = None
    transportationMethod: str = "ltl"
    currencyCode: str = "USD"

    # Bill To Information
    billToName: str
    billToAddress: str
    billToCodeType: str = "assigned_by_buyer"
    billToCode: Optional[str] = None

    # Shipper Information
    shipperName: str
    shipperAddress: str
    shipperCodeType: str = "assigned_by_buyer"
    shipperCode: Optional[str] = None

    # Consignee Information
    consigneeName: str
    consigneeAddress: str
    consigneeCodeType: str = "assigned_by_buyer"
    consigneeCode: Optional[str] = None

    # Line Items
    lineItems: List[LineItemBase]

    # Additional Load Details
    routingSequenceCode: str = "origin_carrier"
    cityOfExchange: Optional[str] = None
    equipmentInitial: Optional[str] = None
    equipmentNumber: Optional[str] = None
    ladingQty: Optional[str] = None
    ladingQtyUOM: str = "pounds"
    totalWeight: Optional[str] = None
    totalWeightUOM: str = "gross_weight"

    # Status and metadata
    status: str = "draft"
    totalAmount: Decimal
    notes: Optional[str] = None


class InvoiceCreate(InvoiceBase):
    companyId: str


class InvoiceUpdate(BaseModel):
    # Header Information
    invoiceNumber: Optional[str] = None
    invoiceDate: Optional[date] = None
    consigneePO: Optional[str] = None
    shipperBL: Optional[str] = None
    shippingSCAC: Optional[str] = None
    paymentMethod: Optional[str] = None
    deliveryDate: Optional[date] = None
    actualPickupDate: Optional[date] = None
    transportationMethod: Optional[str] = None
    currencyCode: Optional[str] = None

    # Bill To Information
    billToName: Optional[str] = None
    billToAddress: Optional[str] = None
    billToCodeType: Optional[str] = None
    billToCode: Optional[str] = None

    # Shipper Information
    shipperName: Optional[str] = None
    shipperAddress: Optional[str] = None
    shipperCodeType: Optional[str] = None
    shipperCode: Optional[str] = None

    # Consignee Information
    consigneeName: Optional[str] = None
    consigneeAddress: Optional[str] = None
    consigneeCodeType: Optional[str] = None
    consigneeCode: Optional[str] = None

    # Line Items
    lineItems: Optional[List[LineItemBase]] = None

    # Additional Load Details
    routingSequenceCode: Optional[str] = None
    cityOfExchange: Optional[str] = None
    equipmentInitial: Optional[str] = None
    equipmentNumber: Optional[str] = None
    ladingQty: Optional[str] = None
    ladingQtyUOM: Optional[str] = None
    totalWeight: Optional[str] = None
    totalWeightUOM: Optional[str] = None

    # Status and metadata
    status: Optional[str] = None
    totalAmount: Optional[Decimal] = None
    notes: Optional[str] = None


class InvoiceOut(InvoiceBase):
    id: str
    companyId: str
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True)
