from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime


class DocumentBase(BaseModel):
    name: str
    type: str
    category: str
    description: Optional[str] = None
    fileName: str
    fileSize: Optional[int] = None
    fileType: Optional[str] = None
    filePath: Optional[str] = None
    employeeId: Optional[str] = None
    employeeName: Optional[str] = None
    status: Optional[str] = "Active"
    expiryDate: Optional[datetime] = None
    details: Optional[Dict[str, Any]] = None


class DocumentCreate(DocumentBase):
    companyId: str


class DocumentUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    fileName: Optional[str] = None
    fileSize: Optional[int] = None
    fileType: Optional[str] = None
    filePath: Optional[str] = None
    employeeId: Optional[str] = None
    employeeName: Optional[str] = None
    status: Optional[str] = None
    expiryDate: Optional[datetime] = None
    details: Optional[Dict[str, Any]] = None


class DocumentOut(DocumentBase):
    id: str
    companyId: str
    uploadDate: datetime
    createdAt: datetime
    updatedAt: datetime

    model_config = ConfigDict(from_attributes=True) 