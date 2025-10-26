from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.config.db import get_db
from app.models.userModels import Users, Companies
from app.models.company_user import CompanyUser
from app.schema.company_user import CompanyUserResponse, CompanyUserCreate, CompanyUserUpdate
from app.routes.user import get_current_user

router = APIRouter(prefix="/api")

def get_current_company_id(current_user: Users = Depends(get_current_user)) -> str:
    """Get current user's company ID"""
    return current_user.companyid

@router.get("/user/companies", response_model=List[dict])
async def get_user_companies(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all companies the user has access to"""
    try:
        # Get all company users for this user
        company_users = db.query(CompanyUser).filter(
            CompanyUser.user_id == current_user.id,
            CompanyUser.is_active == True
        ).all()
        
        companies = []
        for cu in company_users:
            company = db.query(Companies).filter(
                Companies.id == cu.company_id,
                Companies.isActive == True
            ).first()
            
            if company:
                companies.append({
                    "id": company.id,
                    "name": company.name,
                    "type": company.businessType or "carrier",
                    "dot_number": company.dotNumber,
                    "mc_number": company.mcNumber,
                    "is_active": company.isActive,
                    "user_role": cu.role
                })
        
        return companies
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user companies: {str(e)}"
        )

@router.get("/companies/{company_id}/users", response_model=List[CompanyUserResponse])
async def get_company_users(
    company_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all users for a specific company"""
    try:
        # Verify user has access to this company
        company_user = db.query(CompanyUser).filter(
            CompanyUser.user_id == current_user.id,
            CompanyUser.company_id == company_id,
            CompanyUser.is_active == True
        ).first()
        
        if not company_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this company"
            )
        
        # Get all company users
        company_users = db.query(CompanyUser).filter(
            CompanyUser.company_id == company_id,
            CompanyUser.is_active == True
        ).all()
        
        return company_users
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch company users: {str(e)}"
        )

@router.post("/companies/{company_id}/users", response_model=CompanyUserResponse)
async def add_company_user(
    company_id: str,
    user_data: CompanyUserCreate,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a user to a company"""
    try:
        # Verify current user has admin access to this company
        current_company_user = db.query(CompanyUser).filter(
            CompanyUser.user_id == current_user.id,
            CompanyUser.company_id == company_id,
            CompanyUser.is_active == True
        ).first()
        
        if not current_company_user or current_company_user.role not in ['admin']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        # Verify user exists
        user = db.query(Users).filter(Users.id == user_data.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if user is already in this company
        existing_company_user = db.query(CompanyUser).filter(
            CompanyUser.user_id == user_data.user_id,
            CompanyUser.company_id == company_id
        ).first()
        
        if existing_company_user:
            if existing_company_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User is already active in this company"
                )
            else:
                # Reactivate user
                existing_company_user.is_active = True
                existing_company_user.role = user_data.role
                existing_company_user.permissions = user_data.permissions
                db.commit()
                db.refresh(existing_company_user)
                return existing_company_user
        
        # Create new company user
        company_user = CompanyUser(
            user_id=user_data.user_id,
            company_id=company_id,
            role=user_data.role,
            permissions=user_data.permissions,
            is_active=user_data.is_active
        )
        
        db.add(company_user)
        db.commit()
        db.refresh(company_user)
        
        return company_user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add user to company: {str(e)}"
        )

@router.put("/companies/{company_id}/users/{user_id}", response_model=CompanyUserResponse)
async def update_company_user(
    company_id: str,
    user_id: str,
    user_data: CompanyUserUpdate,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a user's role in a company"""
    try:
        # Verify current user has admin access to this company
        current_company_user = db.query(CompanyUser).filter(
            CompanyUser.user_id == current_user.id,
            CompanyUser.company_id == company_id,
            CompanyUser.is_active == True
        ).first()
        
        if not current_company_user or current_company_user.role not in ['admin']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        # Find the company user to update
        company_user = db.query(CompanyUser).filter(
            CompanyUser.user_id == user_id,
            CompanyUser.company_id == company_id
        ).first()
        
        if not company_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in this company"
            )
        
        # Update fields
        if user_data.role is not None:
            company_user.role = user_data.role
        if user_data.permissions is not None:
            company_user.permissions = user_data.permissions
        if user_data.is_active is not None:
            company_user.is_active = user_data.is_active
        
        db.commit()
        db.refresh(company_user)
        
        return company_user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update company user: {str(e)}"
        )
