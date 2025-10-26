from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class EmployeeBase(BaseModel):
    name: str
    position: Optional[str] = None
    department: Optional[str] = None
    status: Optional[str] = "Active"
    hireDate: Optional[datetime] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    cdlClass: Optional[str] = None
    experienceYears: Optional[int] = 0
    location: Optional[str] = None
    profileInitials: Optional[str] = None
    companyId: Optional[str] = None


class EmployeeCreate(EmployeeBase):
    name: str


class EmployeeOut(EmployeeBase):
    id: str
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class EmployeeStats(BaseModel):
    totalEmployees: int
    activeDrivers: int
    officeStaff: int
    onLeave: int
    newHires: int
    retention: float


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    status: Optional[str] = None
    hireDate: Optional[datetime] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    cdlClass: Optional[str] = None
    experienceYears: Optional[int] = None
    location: Optional[str] = None
    profileInitials: Optional[str] = None
