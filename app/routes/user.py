from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, Request, Body, Query, Path
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Callable
from datetime import timedelta, datetime
from pydantic import BaseModel, EmailStr
import re
import jwt
from passlib.context import CryptContext
import uuid
from typing import Optional, Any

from app.config.db import get_db
from app.config.settings import settings
from app.models.userModels import UserCreate, UserUpdate, UserResponse, CompanyCreate, CompanyUpdate, CompanyResponse, Users, Companies, Driver, Equipment
from app.services import fleet_service, driver_service
from app.services.email_service import email_service
from app.middleware.rate_limit import limiter, LOGIN_RATE_LIMIT

# API Router
router = APIRouter(prefix="/api/auth", tags=["Users"])

# JWT Configuration
JWT_SECRET = settings.SECRET_KEY
JWT_EXPIRATION_HOURS = settings.ACCESS_TOKEN_EXPIRE_MINUTES / 60

# Password context for bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Password verification function
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Get current user from JWT token
def get_current_user_from_token(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("userId")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = db.query(Users).filter(Users.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Check role based user authentication
def require_role_auth(required_role: str) -> Callable:
    def role_checker_auth(current_user=Depends(get_current_user)):
        if not current_user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        
        # Allow specific roles
        if current_user.role in [required_role, "platform_owner", "support_staff"]:
            return current_user
        
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return role_checker_auth

def verify_token(request: Request) -> dict:
    # First try to get token from Authorization header
    auth_header = request.headers.get("Authorization")
    token = None
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]  # Extract the token after "Bearer"
    else:
        # If no Authorization header, try to get token from cookies
        token = request.cookies.get("access_token")
    
    if not token:
        raise HTTPException(status_code=401, detail="Access token required")

    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        # Store user info in request state (like req.user in Express)
        request.state.user = decoded
        return decoded
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Used to check the token verification
@router.get("/protected")
def protected_route(user=Depends(verify_token)):
    return {"message": "Access granted", "user": user}

# Request body schema for register
class RegisterUserRequest(BaseModel):
    email: EmailStr
    password: str
    firstName: str
    lastName: str
    phone: str
    role: str = "user"
    companyName: str
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zipCode: str | None = None
    dotNumber: str | None = None
    mcNumber: str | None = None
    ein: str | None = None
    businessType: str | None = None
    yearsInBusiness: str | None = None
    numberOfTrucks: int | None = None

# ----- Routes -----
@router.post("/register")
async def register_user(request_data: RegisterUserRequest, request: Request, db: Session = Depends(get_db)):
    try:
        # Check if user already exists
        existing_user = db.query(Users).filter(Users.email == request_data.email.lower().strip()).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="User with this email already exists")

        # Check if company already exists
        existing_company = db.query(Companies).filter(Companies.email == request_data.email.lower().strip()).first()
        if existing_company:
            raise HTTPException(status_code=400, detail="Company with this email already exists")

        # Create company first
        company_id = str(uuid.uuid4())
        company = Companies(
            id=company_id,
            name=request_data.companyName,
            email=request_data.email.lower().strip(),
            phone=request_data.phone,
            address=request_data.address,
            city=request_data.city,
            state=request_data.state,
            zipCode=request_data.zipCode,
            dotNumber=request_data.dotNumber,
            mcNumber=request_data.mcNumber,
            ein=request_data.ein,
            businessType=request_data.businessType,
            yearsInBusiness=request_data.yearsInBusiness,
            numberOfTrucks=request_data.numberOfTrucks,
            walletBalance=0,
            subscriptionStatus="trial",
            subscriptionPlan="starter",
            isActive=True
        )
        db.add(company)
        db.flush()  # Get the company ID

        # Hash password
        hashed_password = pwd_context.hash(request_data.password)

        # Generate activation token
        activation_token = email_service.generate_activation_token()
        activation_expiry = datetime.utcnow() + timedelta(hours=24)

        # Create user (inactive until email verification)
        user_id = str(uuid.uuid4())
        user = Users(
            id=user_id,
            email=request_data.email.lower().strip(),
            firstname=request_data.firstName,
            lastname=request_data.lastName,
            password=hashed_password,
            phone=request_data.phone,
            role=request_data.role,
            companyid=company_id,
            isactive=False,  # User must activate email first
            emailverified=False,
            activationtoken=activation_token,
            activationtokenexpiry=activation_expiry,
            lastlogin=None  # No login until activated
        )
        db.add(user)
        db.commit()

        # Create session user data
        session_user = {
            "id": user.id,
            "email": user.email,
            "firstName": user.firstname,
            "lastName": user.lastname,
            "phone": user.phone,
            "role": user.role,
            "companyId": user.companyid,
            "companyName": company.name,
            "isActive": user.isactive,
            "lastLogin": user.lastlogin.isoformat() if user.lastlogin else None,
            "createdAt": user.createdat.isoformat() if user.createdat else None,
            "updatedAt": user.updatedat.isoformat() if user.updatedat else None
        }

        # Send activation email
        user_full_name = f"{request_data.firstName} {request_data.lastName}"
        email_sent = email_service.send_activation_email(
            email=request_data.email.lower().strip(),
            user_name=user_full_name,
            activation_token=activation_token
        )

        if not email_sent:
            # Log warning but don't fail registration
            print(f"Warning: Failed to send activation email to {request_data.email}")

        return {
            "success": True,
            "message": "Registration successful! Please check your email to activate your account.",
            "emailSent": email_sent,
            "redirectUrl": "/login?message=check-email"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

# Email activation endpoint
@router.get("/activate/{token}")
async def activate_account(token: str, db: Session = Depends(get_db)):
    """Activate user account with email verification token"""
    try:
        # Find user by activation token
        user = db.query(Users).filter(
            Users.activationtoken == token,
            Users.activationtokenexpiry > datetime.utcnow()
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired activation token. Please request a new activation email."
            )
        
        # Check if already activated
        if user.emailverified:
            return {
                "success": True,
                "message": "Account is already activated. You can now sign in.",
                "redirectUrl": "/login?message=already-activated"
            }
        
        # Activate the account
        user.emailverified = True
        user.isactive = True
        user.activationtoken = None  # Clear the token
        user.activationtokenexpiry = None
        db.commit()
        
        # Get company info
        company = None
        if user.companyid:
            company = db.query(Companies).filter(Companies.id == user.companyid).first()
        
        # Send welcome email
        user_full_name = f"{user.firstname} {user.lastname}"
        company_name = company.name if company else "Your Company"
        email_service.send_welcome_email(
            email=user.email,
            user_name=user_full_name,
            company_name=company_name
        )
        
        return {
            "success": True,
            "message": "Account activated successfully! Welcome to FreightOps Pro.",
            "user": {
                "email": user.email,
                "firstName": user.firstname,
                "lastName": user.lastname,
                "companyName": company_name
            },
            "redirectUrl": "/login?message=activated"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Account activation error: {e}")
        raise HTTPException(status_code=500, detail="Account activation failed")

# Resend activation email endpoint
@router.post("/resend-activation")
async def resend_activation_email(request_data: dict, db: Session = Depends(get_db)):
    """Resend activation email to user"""
    try:
        email = request_data.get("email", "").lower().strip()
        
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")
        
        # Find user
        user = db.query(Users).filter(Users.email == email).first()
        
        if not user:
            # Don't reveal if user exists or not for security
            return {
                "success": True,
                "message": "If an account exists with this email, an activation email has been sent."
            }
        
        # Check if already activated
        if user.emailverified:
            return {
                "success": True,
                "message": "Account is already activated. You can sign in now."
            }
        
        # Generate new activation token
        activation_token = email_service.generate_activation_token()
        activation_expiry = datetime.utcnow() + timedelta(hours=24)
        
        # Update user with new token
        user.activationtoken = activation_token
        user.activationtokenexpiry = activation_expiry
        db.commit()
        
        # Send activation email
        user_full_name = f"{user.firstname} {user.lastname}"
        email_sent = email_service.send_activation_email(
            email=user.email,
            user_name=user_full_name,
            activation_token=activation_token
        )
        
        return {
            "success": True,
            "message": "Activation email sent! Please check your email inbox.",
            "emailSent": email_sent
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Resend activation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to resend activation email")

# Route to get user's companies
@router.get("/user/companies")
async def get_user_companies(decoded: dict = Depends(verify_token), db: Session = Depends(get_db)):
    try:
        user_id = decoded.get("userId")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Get user's companies
        companies = db.query(Companies).filter(Companies.id.in_(
            db.query(Users.companyId).filter(Users.id == user_id)
        )).all()
        
        return [CompanyResponse(
            id=company.id,
            name=company.name,
            email=company.email,
            phone=company.phone,
            address=company.address,
            city=company.city,
            state=company.state,
            zipCode=company.zipCode,
            dotNumber=company.dotNumber,
            mcNumber=company.mcNumber,
            ein=company.ein,
            businessType=company.businessType,
            yearsInBusiness=company.yearsInBusiness,
            numberOfTrucks=company.numberOfTrucks,
            subscriptionTier=company.subscriptionTier,
            subscriptionStatus=company.subscriptionStatus,
            createdAt=company.createdAt,
            updatedAt=company.updatedAt
        ) for company in companies]
        
    except Exception as e:
        print(f"Get user companies error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get companies")

# Route to get current user
@router.get("/me")
async def get_current_user(decoded: dict = Depends(verify_token), db: Session = Depends(get_db)):
    try:
        # Get fresh user and company data from DB
        user = db.query(Users).filter(Users.id == decoded.get("userId")).first()
        company = db.query(Companies).filter(Companies.id == decoded.get("companyId")).first()

        if not user or not company:
            raise HTTPException(status_code=401, detail="User not found")

        user_data = {
            "id": user.id,
            "email": user.email,
            "firstName": user.firstname,
            "lastName": user.lastname,
            "phone": user.phone,
            "role": user.role,
            "companyId": user.companyid,
            "companyName": company.name,
            "isActive": user.isactive,
            "lastLogin": user.lastlogin,
            "createdAt": user.createdat,
            "updatedAt": user.updatedat
        }

        company_data = {
            "id": company.id,
            "name": company.name,
            "email": company.email,
            "phone": company.phone,
            "address": company.address,
            "city": company.city,
            "state": company.state,
            "zipCode": company.zipCode,
            "dotNumber": company.dotNumber,
            "mcNumber": company.mcNumber,
            "ein": company.ein,
            "businessType": company.businessType,
            "yearsInBusiness": company.yearsInBusiness,
            "numberOfTrucks": company.numberOfTrucks,
            "walletBalance": float(company.walletBalance),
            "subscriptionStatus": company.subscriptionStatus,
            "subscriptionPlan": company.subscriptionPlan,
            "isActive": company.isActive
        }

        return {"user": user_data, "company": company_data}

    except Exception as e:
        print("Get current user error:", e)
        raise HTTPException(status_code=500, detail="Failed to get current user")

# Request body schema for login
class LoginRequest(BaseModel):
    email: str
    password: str
    dotNumber: str | None = None
    mcNumber: str | None = None
    customerId: str | None = None

# Main login endpoint - NeonDB Authentication
@router.post("/login")
@limiter.limit(LOGIN_RATE_LIMIT)
def login(req_body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = req_body.email
    password = req_body.password
    dot_number = req_body.dotNumber
    mc_number = req_body.mcNumber
    customer_id = req_body.customerId

    # Input validation
    if not email or not password:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Email and password are required",
                "missingFields": {
                    "email": not email,
                    "password": not password
                }
            }
        )

    # Validate DOT or MC number is provided
    if not dot_number and not mc_number:
        raise HTTPException(
            status_code=400,
            detail="Either US DOT number or MC number is required for verification"
        )

    # Sanitize inputs
    sanitized_email = email.lower().strip()

    # Basic email validation (already handled by EmailStr, but let's keep for parity)
    email_regex = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    if not re.match(email_regex, sanitized_email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address")

    # Authenticate user
    user = db.query(Users).filter(Users.email == sanitized_email).first()

    if not user or not verify_password(password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password. Please check your credentials and try again.")

    # Check if email is verified
    if not user.emailverified:
        raise HTTPException(
            status_code=403,
            detail="Please activate your account by clicking the link in your email before signing in. Check your email inbox or spam folder."
        )

    # Fetch company
    company = None
    if user.companyid:
        company = db.query(Companies).filter(Companies.id == user.companyid).first()

    # Verify DOT or MC number matches company
    if company:
        # Since we're sending the same value for both fields, check if it matches either DOT or MC
        provided_number = dot_number or mc_number
        dot_match = provided_number and company.dotNumber and company.dotNumber.strip() == provided_number.strip()
        mc_match = provided_number and company.mcNumber and company.mcNumber.strip() == provided_number.strip()
        
        if not (dot_match or mc_match):
            raise HTTPException(
                status_code=403,
                detail="US DOT number or MC number does not match your company records. Please verify your credentials or contact support."
            )
    else:
        raise HTTPException(
            status_code=403,
            detail="No company associated with this account. Please contact support."
        )

    # Session equivalent (FastAPI doesn't have built-in sessions unless using middleware)
    session_user = {
        "id": user.id,
        "email": user.email,
        "firstName": user.firstname,
        "lastName": user.lastname,
        "phone": user.phone,
        "role": user.role,
        "companyId": user.companyid,
        "companyName": company.name if company else None,
        "isActive": user.isactive,
        "lastLogin": user.lastlogin.isoformat() if user.lastlogin else None,
        "createdAt": user.createdat.isoformat() if user.createdat else None,
        "updatedAt": user.updatedat.isoformat() if user.updatedat else None
    }

    # Update last login
    user.lastlogin = datetime.utcnow()
    db.commit()

    # Generate JWT token
    payload = {
        "userId": user.id,
        "email": user.email,
        "companyId": user.companyid,
        "role": user.role,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    # Logging
    print(f"Login successful for: {sanitized_email} Company: {company.name if company else 'N/A'}")

    # Create response with user data
    response_data = {
        "success": True,
        "user": session_user,
        "company": {
            "id": company.id if company else None,
            "name": company.name if company else None,
            "email": company.email if company else None,
            "phone": company.phone if company else None,
            "address": company.address if company else None,
            "city": company.city if company else None,
            "state": company.state if company else None,
            "zipCode": company.zipCode if company else None,
            "dotNumber": company.dotNumber if company else None,
            "mcNumber": company.mcNumber if company else None,
            "ein": company.ein if company else None,
            "businessType": company.businessType if company else None,
            "yearsInBusiness": company.yearsInBusiness if company else None,
            "numberOfTrucks": company.numberOfTrucks if company else None,
            "walletBalance": float(company.walletBalance) if company else None,
            "subscriptionStatus": company.subscriptionStatus if company else None,
            "subscriptionPlan": company.subscriptionPlan if company else None,
            "isActive": company.isActive if company else None
        },
        "redirectUrl": "/dashboard"
    }
    
    # Create response with HTTP-only cookie
    response = JSONResponse(response_data)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=JWT_EXPIRATION_HOURS * 3600  # Convert hours to seconds
    )
    
    return response

# Logout endpoint
@router.post("/logout")
async def logout(request: Request):
    try:
        response = JSONResponse({"success": True, "message": "Logged out successfully"})
        # Clear the access token cookie
        response.delete_cookie(key="access_token")
        return response
    except Exception as e:
        print("Logout error:", e)
        raise HTTPException(status_code=500, detail="Logout failed")


# =============================== Fleet Management Routes ===============================

# NOTE: Depend on verify_token directly so this works regardless of parameter order
# and avoids relying on request.state.*
def extract_tenant_id(decoded: dict = Depends(verify_token)):
    company_id = decoded.get("companyId") or decoded.get("companyid")
    if not company_id:
        raise HTTPException(status_code=400, detail="Company ID missing from token")
    return company_id

def get_tenant_id(tenant_id: str = Depends(extract_tenant_id)):
    return tenant_id

# Get fleet stats
@router.get("/fleet/stats")
async def get_fleet_stats(
    tenant_id: str = Depends(get_tenant_id),
    _: None = Depends(verify_token)
):
    try:
        return await fleet_service.get_fleet_stats(tenant_id)
    except Exception as e:
        print("Get fleet stats error:", e)
        raise HTTPException(status_code=500, detail="Failed to get fleet statistics")

# Get vehicles
@router.get("/fleet/vehicles")
async def get_vehicles(
    tenant_id: str = Depends(get_tenant_id),
    _: None = Depends(verify_token),
    page: int = Query(1),
    limit: int = Query(20),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sortBy: str = Query("createdAt"),
    sortOrder: str = Query("desc")
):
    try:
        return await fleet_service.get_vehicles(tenant_id, {
            "page": page,
            "limit": limit,
            "search": search,
            "status": status,
            "sortBy": sortBy,
            "sortOrder": sortOrder
        })
    except Exception as e:
        print("Get vehicles error:", e)
        raise HTTPException(status_code=500, detail="Failed to get vehicles")

# Get vehicle by id
@router.get("/fleet/vehicles/{id}")
async def get_vehicle_by_id(
    id: str = Path(...),
    tenant_id: str = Depends(get_tenant_id),
    _: None = Depends(verify_token)
):
    try:
        vehicle = await fleet_service.get_vehicle_by_id(id, tenant_id)
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        return vehicle
    except HTTPException:
        raise
    except Exception as e:
        print("Get vehicle error:", e)
        raise HTTPException(status_code=500, detail="Failed to get vehicle")

# Create vehicle
@router.post("/fleet/vehicles", status_code=201)
async def create_vehicle(
    vehicle_data: dict,
    payload: dict = Depends(verify_token),
    tenant_id: str = Depends(get_tenant_id)
):
    try:
        print(f"Create vehicle endpoint called with data: {vehicle_data}")
        print(f"Tenant ID: {tenant_id}")
        
        new_vehicle = await fleet_service.create_vehicle(tenant_id, vehicle_data)
        print("Vehicle created successfully:", new_vehicle.get("truckNumber", "Unknown"))
        return new_vehicle
    except ValueError as e:
        print(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Create vehicle error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to create vehicle")

# Update vehicle
@router.put("/fleet/vehicles/{id}")
async def update_vehicle(
    id: str,
    vehicle_data: dict,
    tenant_id: str = Depends(get_tenant_id),
    _: None = Depends(verify_token)
):
    try:
        updated_vehicle = await fleet_service.update_vehicle(id, tenant_id, vehicle_data)
        return updated_vehicle
    except Exception as e:
        print("Update vehicle error:", e)
        raise HTTPException(status_code=500, detail="Failed to update vehicle")

# Delete vehicle
@router.delete("/fleet/vehicles/{id}")
async def delete_vehicle(
    id: str,
    tenant_id: str = Depends(get_tenant_id),
    _: None = Depends(verify_token)
):
    try:
        await fleet_service.delete_vehicle(id, tenant_id)
        return {"success": True}
    except Exception as e:
        print("Delete vehicle error:", e)
        raise HTTPException(status_code=500, detail="Failed to delete vehicle")


# Alias for get_vehicles
@router.get("/fleet/trucks")
async def get_trucks(
    tenant_id: str = Depends(get_tenant_id),
    _: None = Depends(verify_token),
    page: int = Query(1),
    limit: int = Query(20),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sortBy: str = Query("createdAt"),
    sortOrder: str = Query("desc")
):
    try:
        return await fleet_service.get_vehicles(tenant_id, {
            "page": page,
            "limit": limit,
            "search": search,
            "status": status,
            "sortBy": sortBy,
            "sortOrder": sortOrder
        })
    except Exception as e:
        print("Get trucks error:", e)
        raise HTTPException(status_code=500, detail="Failed to list trucks")


# Get individual truck by id
@router.get("/fleet/trucks/{truck_id}")
async def get_truck_by_id(
    truck_id: str = Path(...),
    tenant_id: str = Depends(get_tenant_id),
    _: None = Depends(verify_token)
):
    try:
        truck = await fleet_service.get_vehicle_by_id(truck_id, tenant_id)
        if not truck:
            raise HTTPException(status_code=404, detail="Truck not found")
        return truck
    except HTTPException:
        raise
    except Exception as e:
        print("Get truck error:", e)
        raise HTTPException(status_code=500, detail="Failed to get truck")


# ----- Pydantic models for drivers -----
class DriverCreate(BaseModel):
    firstName: str
    lastName: str
    email: str
    phone: str
    licenseNumber: str
    licenseClass: str
    licenseExpiry: str
    dateOfBirth: str
    address: str
    city: str
    state: str
    zipCode: str
    emergencyContact: str
    emergencyPhone: str
    hireDate: str
    payRate: float
    payType: str
    status: Optional[str] = "available"
    hoursRemaining: Optional[float] = None
    currentLocation: Optional[str] = None
    isActive: Optional[bool] = True

class DriverUpdate(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    licenseNumber: Optional[str] = None
    licenseClass: Optional[str] = None
    licenseExpiry: Optional[str] = None
    dateOfBirth: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipCode: Optional[str] = None
    emergencyContact: Optional[str] = None
    emergencyPhone: Optional[str] = None
    hireDate: Optional[str] = None
    payRate: Optional[float] = None
    payType: Optional[str] = None
    status: Optional[str] = None
    hoursRemaining: Optional[float] = None
    currentLocation: Optional[str] = None
    isActive: Optional[bool] = None

class MaintenanceUpdate(BaseModel):
    due_date: Optional[str] = None
    notes: Optional[str] = None

# ----- Driver routes -----
@router.get("/fleet/drivers")
async def get_drivers(
    page: int = Query(1),
    limit: int = Query(20),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sortBy: str = Query("createdAt"),
    sortOrder: str = Query("desc"),
    tenant_id: str = Depends(get_tenant_id),
    _: None = Depends(verify_token)
):
    try:
        return await driver_service.get_drivers(tenant_id, {
            "page": page,
            "limit": limit,
            "search": search,
            "status": status,
            "sortBy": sortBy,
            "sortOrder": sortOrder
        })
    except Exception as e:
        print("Get drivers error:", e)
        raise HTTPException(status_code=500, detail="Failed to get drivers")


@router.get("/fleet/drivers/{driver_id}")
async def get_driver(
    driver_id: str, 
    tenant_id: str = Depends(get_tenant_id),
    _: None = Depends(verify_token)
):
    try:
        print(f"Getting driver by ID: {driver_id} for tenant: {tenant_id}")
        driver = await driver_service.get_driver_by_id(driver_id, tenant_id)
        print(f"Driver result: {driver}")
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        return driver
    except HTTPException:
        raise
    except Exception as e:
        print("Get driver error:", e)
        raise HTTPException(status_code=500, detail="Failed to get driver")


@router.post("/fleet/drivers", status_code=201)
async def create_driver(
    driver_data: DriverCreate, 
    tenant_id: str = Depends(get_tenant_id),
    _: None = Depends(verify_token)
):
    try:
        return await driver_service.create_driver(tenant_id, driver_data.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print("Create driver error:", e)
        raise HTTPException(status_code=500, detail="Failed to create driver")


@router.put("/fleet/drivers/{driver_id}")
async def update_driver(
    driver_id: str, 
    update_data: DriverUpdate, 
    tenant_id: str = Depends(get_tenant_id),
    _: None = Depends(verify_token)
):
    try:
        # Filter out None values
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        updated_driver = await driver_service.update_driver(driver_id, tenant_id, update_dict)
        if not updated_driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        return updated_driver
    except HTTPException:
        raise
    except Exception as e:
        print("Update driver error:", e)
        raise HTTPException(status_code=500, detail="Failed to update driver")


@router.delete("/fleet/drivers/{driver_id}")
async def delete_driver(
    driver_id: str, 
    tenant_id: str = Depends(get_tenant_id),
    _: None = Depends(verify_token)
):
    try:
        success = await driver_service.delete_driver(driver_id, tenant_id)
        if not success:
            raise HTTPException(status_code=404, detail="Driver not found")
        return {"success": True, "message": "Driver deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print("Delete driver error:", e)
        raise HTTPException(status_code=500, detail="Failed to delete driver")


@router.get("/fleet/drivers/available")
async def get_available_drivers(
    tenant_id: str = Depends(get_tenant_id),
    _: None = Depends(verify_token)
):
    try:
        return await driver_service.get_available_drivers(tenant_id)
    except Exception as e:
        print("Get available drivers error:", e)
        raise HTTPException(status_code=500, detail="Failed to get available drivers")


@router.get("/fleet/drivers/stats")
async def get_driver_stats(
    tenant_id: str = Depends(get_tenant_id),
    _: None = Depends(verify_token)
):
    try:
        return await driver_service.get_driver_stats(tenant_id)
    except Exception as e:
        print("Get driver stats error:", e)
        raise HTTPException(status_code=500, detail="Failed to get driver statistics")


# Health check endpoint
@router.get("/health")
def health_check():
    return {"status": "healthy", "message": "FreightOps API is running"}

# Test endpoint for getting drivers without authentication (for development only)
@router.get("/test/drivers")
async def get_test_drivers(db: Session = Depends(get_db)):
    """Get drivers for testing (no authentication required)"""
    try:
        # Get the first company
        company = db.query(Companies).filter(Companies.isActive == True).first()
        if not company:
            raise HTTPException(status_code=404, detail="No company found")
        
        # Get drivers for this company
        drivers = db.query(Driver).filter(
            Driver.companyId == company.id,
            Driver.isActive == True
        ).all()
        
        # Serialize drivers
        driver_list = []
        for driver in drivers:
            driver_list.append({
                "id": driver.id,
                "firstName": driver.firstName,
                "lastName": driver.lastName,
                "email": driver.email,
                "phone": driver.phone,
                "licenseNumber": driver.licenseNumber,
                "licenseClass": driver.licenseClass,
                "status": driver.status,
                "isActive": driver.isActive
            })
        
        return {"items": driver_list}
        
    except Exception as e:
        print(f"Error getting test drivers: {e}")
        raise HTTPException(status_code=500, detail="Failed to get drivers")

# Test endpoint for getting equipment without authentication (for development only)
@router.get("/test/equipment")
async def get_test_equipment(db: Session = Depends(get_db)):
    """Get equipment for testing (no authentication required)"""
    try:
        # Get the first company
        company = db.query(Companies).filter(Companies.isActive == True).first()
        if not company:
            raise HTTPException(status_code=404, detail="No company found")
        
        # Get equipment for this company
        equipment = db.query(Equipment).filter(
            Equipment.companyId == company.id,
            Equipment.isActive == True
        ).all()
        
        # Serialize equipment
        equipment_list = []
        for item in equipment:
            equipment_list.append({
                "id": item.id,
                "equipmentNumber": item.equipmentNumber,
                "equipmentType": item.equipmentType,
                "make": item.make,
                "model": item.model,
                "year": item.year,
                "status": item.status,
                "isActive": item.isActive
            })
        
        return equipment_list
        
    except Exception as e:
        print(f"Error getting test equipment: {e}")
        raise HTTPException(status_code=500, detail="Failed to get equipment")
