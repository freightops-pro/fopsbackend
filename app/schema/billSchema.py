from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date, datetime


class BillBase(BaseModel):
    vendorName: str
    amount: float
    vendorId: Optional[str] = None
    billDate: Optional[date] = None
    dueDate: Optional[date] = None
    category: Optional[str] = None
    status: Optional[str] = "pending"
    notes: Optional[str] = None


class BillCreate(BillBase):
    companyId: str


class BillUpdate(BaseModel):
    vendorName: Optional[str] = None
    vendorId: Optional[str] = None
    amount: Optional[float] = None
    billDate: Optional[date] = None
    dueDate: Optional[date] = None
    category: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class BillOut(BillBase):
    id: str
    companyId: str
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True)


# Vendor Schema
class VendorBase(BaseModel):
    # Personal Details
    title: Optional[str] = None
    firstName: Optional[str] = None
    middleName: Optional[str] = None
    lastName: Optional[str] = None
    suffix: Optional[str] = None
    
    # Company Details
    company: Optional[str] = None
    displayName: str
    printOnCheck: Optional[str] = None
    
    # Address Information
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipCode: Optional[str] = None
    country: Optional[str] = None
    
    # Contact Information
    email: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    fax: Optional[str] = None
    other: Optional[str] = None
    website: Optional[str] = None
    
    # Financial Information
    billingRate: Optional[float] = None
    terms: Optional[str] = None
    openingBalance: Optional[float] = None
    balanceAsOf: Optional[date] = None
    accountNumber: Optional[str] = None
    
    # 1099 Tracking
    taxId: Optional[str] = None
    trackPaymentsFor1099: Optional[bool] = False


class VendorCreate(VendorBase):
    companyId: str


class VendorUpdate(BaseModel):
    # Personal Details
    title: Optional[str] = None
    firstName: Optional[str] = None
    middleName: Optional[str] = None
    lastName: Optional[str] = None
    suffix: Optional[str] = None
    
    # Company Details
    company: Optional[str] = None
    displayName: Optional[str] = None
    printOnCheck: Optional[str] = None
    
    # Address Information
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipCode: Optional[str] = None
    country: Optional[str] = None
    
    # Contact Information
    email: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    fax: Optional[str] = None
    other: Optional[str] = None
    website: Optional[str] = None
    
    # Financial Information
    billingRate: Optional[float] = None
    terms: Optional[str] = None
    openingBalance: Optional[float] = None
    balanceAsOf: Optional[date] = None
    accountNumber: Optional[str] = None
    
    # 1099 Tracking
    taxId: Optional[str] = None
    trackPaymentsFor1099: Optional[bool] = None


class VendorOut(VendorBase):
    id: str
    companyId: str
    isActive: bool
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True)


# Combined Vendor and Bill Schema
class VendorBillCreate(BaseModel):
    companyId: str
    
    # Vendor Information
    title: Optional[str] = None
    firstName: Optional[str] = None
    middleName: Optional[str] = None
    lastName: Optional[str] = None
    suffix: Optional[str] = None
    company: Optional[str] = None
    displayName: str
    printOnCheck: Optional[str] = None
    
    # Address Information
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipCode: Optional[str] = None
    country: Optional[str] = None
    
    # Contact Information
    email: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    fax: Optional[str] = None
    other: Optional[str] = None
    website: Optional[str] = None
    
    # Financial Information
    billingRate: Optional[float] = None
    terms: Optional[str] = None
    openingBalance: Optional[float] = None
    balanceAsOf: Optional[date] = None
    accountNumber: Optional[str] = None
    
    # 1099 Tracking
    taxId: Optional[str] = None
    trackPaymentsFor1099: Optional[bool] = False
    
    # Bill Information
    amount: float
    billDate: Optional[date] = None
    dueDate: Optional[date] = None
    category: Optional[str] = None
    status: Optional[str] = "pending"
    notes: Optional[str] = None


