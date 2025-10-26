from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import List, Optional
from sqlalchemy.orm import Session
from app.config.db import get_db
from app.models.userModels import Companies
from pydantic import BaseModel
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/companies", tags=["Companies"])

# Pydantic models for request/response
class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipCode: Optional[str] = None
    dotNumber: Optional[str] = None
    mcNumber: Optional[str] = None
    ein: Optional[str] = None
    businessType: Optional[str] = None
    yearsInBusiness: Optional[int] = None
    numberOfTrucks: Optional[int] = None

class CompanyResponse(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipCode: Optional[str] = None
    dotNumber: Optional[str] = None
    mcNumber: Optional[str] = None
    ein: Optional[str] = None
    businessType: Optional[str] = None
    yearsInBusiness: Optional[int] = None
    numberOfTrucks: Optional[int] = None
    walletBalance: float
    subscriptionStatus: str
    subscriptionPlan: str
    isActive: bool
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True

class CompanySetting(BaseModel):
    settingKey: str
    settingValue: str

class CompanyUser(BaseModel):
    id: str
    name: str
    email: str
    role: str
    status: str

    class Config:
        from_attributes = True

# Helper function to get current company (placeholder for authentication)
def get_current_company(db: Session):
    # For now, return the first active company
    # In a real implementation, this would be based on user authentication
    company = db.query(Companies).filter(Companies.isActive == True).first()
    if not company:
        # Create a default company if none exists
        company_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        default_company = Companies(
            id=company_id,
            name="Default FreightOps Company",
            email="admin@freightops.com",
            phone="+1-555-0123",
            address="123 Main Street",
            city="Chicago",
            state="IL",
            zipCode="60601",
            dotNumber="DOT1234567",
            mcNumber="MC-123456",
            ein="12-3456789",
            businessType="LLC",
            yearsInBusiness=5,
            numberOfTrucks=10,
            walletBalance=0.0,
            subscriptionStatus="trial",
            subscriptionPlan="starter",
            createdAt=now,
            updatedAt=now,
            isActive=True,
            handlesContainers=False,
            containerTrackingEnabled=False
        )
        
        db.add(default_company)
        db.commit()
        db.refresh(default_company)
        return default_company
    
    return company

@router.get("", response_model=List[CompanyResponse])
def get_companies(db: Session = Depends(get_db)):
    """Get all companies (for now, returns current user's company)"""
    companies = db.query(Companies).filter(Companies.isActive == True).all()
    return companies

@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(company_id: str = Path(...), db: Session = Depends(get_db)):
    """Get a specific company by ID"""
    company = db.query(Companies).filter(Companies.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company

@router.patch("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: str = Path(...),
    company_data: CompanyUpdate = None,
    db: Session = Depends(get_db)
):
    """Update company information"""
    company = db.query(Companies).filter(Companies.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Update only provided fields
    if company_data:
        update_data = company_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(company, field):
                setattr(company, field, value)
        
        company.updatedAt = datetime.utcnow()
        db.add(company)
        db.commit()
        db.refresh(company)
    
    return company

@router.get("/{company_id}/settings", response_model=List[CompanySetting])
def get_company_settings(company_id: str = Path(...), db: Session = Depends(get_db)):
    """Get company settings (placeholder - would need a settings table)"""
    # For now, return empty list - in a real implementation, this would query a settings table
    return []

@router.put("/{company_id}/settings/{setting_key}")
def update_company_setting(
    company_id: str = Path(...),
    setting_key: str = Path(...),
    setting_data: dict = None,
    db: Session = Depends(get_db)
):
    """Update a specific company setting (placeholder)"""
    # For now, just return success - in a real implementation, this would update a settings table
    return {"message": "Setting updated successfully"}

@router.get("/{company_id}/users", response_model=List[CompanyUser])
def get_company_users(company_id: str = Path(...), db: Session = Depends(get_db)):
    """Get users for a specific company (placeholder)"""
    # For now, return empty list - in a real implementation, this would query the users table
    return []
