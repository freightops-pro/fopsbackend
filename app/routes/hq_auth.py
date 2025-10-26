"""
HQ Authentication Routes - Separate from tenant authentication
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from passlib.context import CryptContext
from passlib.hash import bcrypt
import jwt
import uuid
from typing import Optional

from app.config.db import get_db
from app.config.settings import settings
from app.models.hqModels import HQAdmin
from app.schema.hqSchema import (
    HQAdminCreate, 
    HQAdminUpdate, 
    HQAdminResponse, 
    HQLoginRequest, 
    HQLoginResponse
)
from app.middleware.rate_limit import limiter, LOGIN_RATE_LIMIT

router = APIRouter(prefix="/hq", tags=["HQ Authentication"])

# Password context for HQ admins
hq_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration for HQ
HQ_JWT_SECRET = settings.SECRET_KEY + "_HQ"  # Separate secret for HQ
HQ_JWT_ALGORITHM = settings.ALGORITHM
HQ_JWT_EXPIRATION_HOURS = 8  # Longer sessions for HQ admins


def hash_hq_password(password: str) -> str:
    """Hash password for HQ admin"""
    return hq_pwd_context.hash(password)


def verify_hq_password(plain_password: str, hashed_password: str) -> bool:
    """Verify HQ admin password"""
    return hq_pwd_context.verify(plain_password, hashed_password)


def create_hq_token(admin_id: str) -> str:
    """Create JWT token for HQ admin"""
    expire = datetime.utcnow() + timedelta(hours=HQ_JWT_EXPIRATION_HOURS)
    payload = {
        "sub": admin_id,
        "exp": expire,
        "type": "hq_admin",
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, HQ_JWT_SECRET, algorithm=HQ_JWT_ALGORITHM)


def verify_hq_token(token: str) -> Optional[str]:
    """Verify HQ JWT token and return admin ID"""
    try:
        payload = jwt.decode(token, HQ_JWT_SECRET, algorithms=[HQ_JWT_ALGORITHM])
        if payload.get("type") != "hq_admin":
            return None
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.JWTError:
        return None


def get_current_hq_admin(token: str = None, db: Session = Depends(get_db)) -> HQAdmin:
    """Get current HQ admin from token"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="HQ authentication required"
        )
    
    admin_id = verify_hq_token(token)
    if not admin_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HQ token"
        )
    
    admin = db.query(HQAdmin).filter(HQAdmin.id == admin_id).first()
    if not admin or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="HQ admin not found or inactive"
        )
    
    return admin


@router.post("/login", response_model=HQLoginResponse)
@limiter.limit(LOGIN_RATE_LIMIT)
def hq_login(hq_request: HQLoginRequest, request: Request, db: Session = Depends(get_db)):
    """HQ Admin login endpoint"""
    # Find HQ admin by email
    admin = db.query(HQAdmin).filter(HQAdmin.email == hq_request.email.lower().strip()).first()
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please check your credentials and try again."
        )
    
    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="HQ admin account is inactive"
        )
    
    # Verify password
    if not verify_hq_password(hq_request.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please check your credentials and try again."
        )
    
    # Update last login
    admin.last_login = datetime.utcnow()
    db.commit()
    
    # Create token
    token = create_hq_token(admin.id)
    
    # Return response
    return HQLoginResponse(
        access_token=token,
        admin=HQAdminResponse.from_orm(admin)
    )


@router.get("/me", response_model=HQAdminResponse)
def get_hq_admin_profile(current_admin: HQAdmin = Depends(get_current_hq_admin)):
    """Get current HQ admin profile"""
    return HQAdminResponse.from_orm(current_admin)


@router.post("/create-admin", response_model=HQAdminResponse)
def create_hq_admin(
    admin_data: HQAdminCreate, 
    db: Session = Depends(get_db),
    current_admin: HQAdmin = Depends(get_current_hq_admin)
):
    """Create new HQ admin (only super_admin and platform_owner can do this)"""
    if current_admin.role not in ["super_admin", "platform_owner"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins and platform owners can create HQ admins"
        )
    
    # Check if email already exists
    existing_admin = db.query(HQAdmin).filter(HQAdmin.email == admin_data.email.lower().strip()).first()
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HQ admin with this email already exists"
        )
    
    # Create new HQ admin
    new_admin = HQAdmin(
        id=str(uuid.uuid4()),
        email=admin_data.email.lower().strip(),
        password_hash=hash_hq_password(admin_data.password),
        first_name=admin_data.first_name,
        last_name=admin_data.last_name,
        role=admin_data.role,
        notes=admin_data.notes
    )
    
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    
    return HQAdminResponse.from_orm(new_admin)


@router.get("/admins", response_model=list[HQAdminResponse])
def list_hq_admins(
    db: Session = Depends(get_db),
    current_admin: HQAdmin = Depends(get_current_hq_admin)
):
    """List all HQ admins (only super_admin and platform_owner can do this)"""
    if current_admin.role not in ["super_admin", "platform_owner"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins and platform owners can list HQ admins"
        )
    
    admins = db.query(HQAdmin).all()
    return [HQAdminResponse.from_orm(admin) for admin in admins]


@router.put("/admins/{admin_id}", response_model=HQAdminResponse)
def update_hq_admin(
    admin_id: str,
    admin_data: HQAdminUpdate,
    db: Session = Depends(get_db),
    current_admin: HQAdmin = Depends(get_current_hq_admin)
):
    """Update HQ admin (only super_admin and platform_owner can do this)"""
    if current_admin.role not in ["super_admin", "platform_owner"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins and platform owners can update HQ admins"
        )
    
    admin = db.query(HQAdmin).filter(HQAdmin.id == admin_id).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HQ admin not found"
        )
    
    # Update fields
    if admin_data.email:
        # Check if email already exists
        existing_admin = db.query(HQAdmin).filter(
            HQAdmin.email == admin_data.email.lower().strip(),
            HQAdmin.id != admin_id
        ).first()
        if existing_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="HQ admin with this email already exists"
            )
        admin.email = admin_data.email.lower().strip()
    
    if admin_data.first_name:
        admin.first_name = admin_data.first_name
    if admin_data.last_name:
        admin.last_name = admin_data.last_name
    if admin_data.role:
        admin.role = admin_data.role
    if admin_data.is_active is not None:
        admin.is_active = admin_data.is_active
    if admin_data.notes is not None:
        admin.notes = admin_data.notes
    
    admin.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(admin)
    
    return HQAdminResponse.from_orm(admin)
