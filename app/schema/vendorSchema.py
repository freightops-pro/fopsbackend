from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, Literal, Dict, Any
from datetime import date, datetime


class VendorBase(BaseModel):
    name: str
    contactPerson: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipCode: Optional[str] = None
    category: Optional[str] = None
    paymentTerms: Optional[int] = None
    status: Optional[Literal['active', 'inactive', 'suspended']] = 'active'
    totalSpend: Optional[float] = 0
    lastPayment: Optional[date] = None
    details: Optional[Dict[str, Any]] = None


class VendorCreate(VendorBase):
    companyId: str


class VendorUpdate(BaseModel):
    name: Optional[str] = None
    contactPerson: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipCode: Optional[str] = None
    category: Optional[str] = None
    paymentTerms: Optional[int] = None
    status: Optional[Literal['active', 'inactive', 'suspended']] = None
    totalSpend: Optional[float] = None
    lastPayment: Optional[date] = None
    details: Optional[Dict[str, Any]] = None


class VendorOut(VendorBase):
    id: str
    companyId: str
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True) 