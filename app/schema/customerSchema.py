from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, Literal, Dict, Any
from datetime import date, datetime


class CustomerBase(BaseModel):
    name: str
    contactPerson: Optional[str] = None
    contactTitle: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    fax: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipCode: Optional[str] = None
    accountNumber: Optional[str] = None
    taxId: Optional[str] = None
    customerType: Optional[str] = None
    # Mailing/Billing addresses
    mailingAddress: Optional[str] = None
    mailingCity: Optional[str] = None
    mailingState: Optional[str] = None
    mailingZip: Optional[str] = None
    mailingCountry: Optional[str] = None
    billingAddress: Optional[str] = None
    billingCity: Optional[str] = None
    billingState: Optional[str] = None
    billingZip: Optional[str] = None
    billingCountry: Optional[str] = None
    creditLimit: Optional[float] = None
    paymentTerms: Optional[int] = None
    status: Optional[Literal['active','inactive','suspended']] = 'active'
    totalRevenue: Optional[float] = 0
    lastOrder: Optional[date] = None
    billingMethod: Optional[str] = None
    currency: Optional[str] = None
    notes: Optional[str] = None
    # Raw flexible details payload for any additional sections (accounts team etc.)
    details: Optional[Dict[str, Any]] = None


class CustomerCreate(CustomerBase):
    companyId: str


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    contactPerson: Optional[str] = None
    contactTitle: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    fax: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipCode: Optional[str] = None
    accountNumber: Optional[str] = None
    taxId: Optional[str] = None
    customerType: Optional[str] = None
    mailingAddress: Optional[str] = None
    mailingCity: Optional[str] = None
    mailingState: Optional[str] = None
    mailingZip: Optional[str] = None
    mailingCountry: Optional[str] = None
    billingAddress: Optional[str] = None
    billingCity: Optional[str] = None
    billingState: Optional[str] = None
    billingZip: Optional[str] = None
    billingCountry: Optional[str] = None
    creditLimit: Optional[float] = None
    paymentTerms: Optional[int] = None
    status: Optional[Literal['active','inactive','suspended']] = None
    totalRevenue: Optional[float] = None
    lastOrder: Optional[date] = None
    billingMethod: Optional[str] = None
    currency: Optional[str] = None
    notes: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class CustomerOut(CustomerBase):
    id: str
    companyId: str
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True)
