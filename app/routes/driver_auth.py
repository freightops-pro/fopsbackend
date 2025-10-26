from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import jwt
from pydantic import BaseModel, EmailStr

from app.config.db import get_db
from app.models.userModels import Driver, Companies, Equipment
from app.config.settings import settings
from app.routes.user import verify_token

router = APIRouter(prefix="/api/driver", tags=["driver-auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class DriverLoginRequest(BaseModel):
    email: EmailStr
    password: str


class DriverSignupRequest(BaseModel):
    email: EmailStr
    password: str
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    phone: Optional[str] = None


class DriverResponse(BaseModel):
    id: str
    email: str
    firstName: str
    lastName: str
    phone: Optional[str]
    companyId: str
    companyName: str
    status: str
    licenseNumber: Optional[str]
    licenseClass: Optional[str]
    currentLocation: Optional[str]
    isActive: bool


def create_driver_token(driver_id: str, company_id: str) -> str:
    """Create JWT token for driver"""
    expire = datetime.utcnow() + timedelta(days=30)
    to_encode = {
        "driverId": driver_id,
        "companyId": company_id,
        "type": "driver",
        "exp": expire
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_driver_token(token: str) -> dict:
    """Verify driver JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "driver":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def hash_password(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    newPassword: str


@router.post("/login")
def driver_login(request: DriverLoginRequest, db: Session = Depends(get_db)):
    """
    Driver login endpoint
    - Drivers log in with email and password
    - Email must match the one used by company when adding driver
    """
    # Find driver by email
    driver = db.query(Driver).filter(Driver.email == request.email).first()
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please check your credentials and try again."
        )
    
    # Check if driver has a password set
    if not driver.passwordHash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please complete signup first to set your password"
        )
    
    # Verify password
    if not verify_password(request.password, driver.passwordHash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please check your credentials and try again."
        )
    
    # Check if driver is active
    if not driver.isActive:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact your company administrator."
        )
    
    # Get company details
    company = db.query(Companies).filter(Companies.id == driver.companyId).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Company not found"
        )
    
    # Create token
    token = create_driver_token(driver.id, driver.companyId)
    
    # Return driver info
    return {
        "success": True,
        "token": token,
        "driver": {
            "id": driver.id,
            "email": driver.email,
            "firstName": driver.firstName,
            "lastName": driver.lastName,
            "phone": driver.phone,
            "companyId": driver.companyId,
            "companyName": company.name,
            "status": driver.status or "available",
            "licenseNumber": driver.licenseNumber,
            "licenseClass": driver.licenseClass,
            "currentLocation": driver.currentLocation,
            "isActive": driver.isActive,
            "dateOfBirth": driver.dateOfBirth.isoformat() if driver.dateOfBirth else None,
            "licenseExpiry": driver.licenseExpiry.isoformat() if driver.licenseExpiry else None,
            "hireDate": driver.hireDate.isoformat() if driver.hireDate else None,
        }
    }


@router.post("/signup")
def driver_signup(request: DriverSignupRequest, db: Session = Depends(get_db)):
    """
    Driver signup endpoint
    - Drivers must be already added by company (email must exist)
    - This endpoint allows them to set password and complete profile
    """
    # Find driver by email
    driver = db.query(Driver).filter(Driver.email == request.email).first()
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No driver account found with this email. Please contact your company to add you as a driver first."
        )
    
    # Check if already signed up
    if driver.passwordHash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account already exists. Please login instead."
        )
    
    # Hash password and update driver
    driver.passwordHash = hash_password(request.password)
    
    # Update optional fields if provided
    if request.firstName:
        driver.firstName = request.firstName
    if request.lastName:
        driver.lastName = request.lastName
    if request.phone:
        driver.phone = request.phone
    
    db.commit()
    db.refresh(driver)
    
    # Get company details
    company = db.query(Companies).filter(Companies.id == driver.companyId).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Company not found"
        )
    
    # Create token
    token = create_driver_token(driver.id, driver.companyId)
    
    # Return driver info
    return {
        "success": True,
        "token": token,
        "driver": {
            "id": driver.id,
            "email": driver.email,
            "firstName": driver.firstName,
            "lastName": driver.lastName,
            "phone": driver.phone,
            "companyId": driver.companyId,
            "companyName": company.name,
            "status": driver.status or "available",
            "licenseNumber": driver.licenseNumber,
            "licenseClass": driver.licenseClass,
            "currentLocation": driver.currentLocation,
            "isActive": driver.isActive,
            "dateOfBirth": driver.dateOfBirth.isoformat() if driver.dateOfBirth else None,
            "licenseExpiry": driver.licenseExpiry.isoformat() if driver.licenseExpiry else None,
            "hireDate": driver.hireDate.isoformat() if driver.hireDate else None,
        }
    }


@router.post("/admin/reset-password")
def admin_reset_driver_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Reset a driver's password by email (unprotected for now)."""
    driver = db.query(Driver).filter(Driver.email == request.email).first()
    if not driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")

    driver.passwordHash = hash_password(request.newPassword)
    db.commit()
    return {"success": True}


from fastapi import Header

def get_current_driver_token(authorization: str = Header(...)):
    """Extract and verify the driver token from the Authorization header"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.replace("Bearer ", "")
    return verify_driver_token(token)

@router.get("/me")
def get_current_driver(
    token_data: dict = Depends(get_current_driver_token),
    db: Session = Depends(get_db)
):
    """Get current driver information"""
    driver_id = token_data.get("driverId")
    
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    # Get company details
    company = db.query(Companies).filter(Companies.id == driver.companyId).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Company not found"
        )
    
    return {
        "id": driver.id,
        "email": driver.email,
        "firstName": driver.firstName,
        "lastName": driver.lastName,
        "phone": driver.phone,
        "companyId": driver.companyId,
        "companyName": company.name,
        "status": driver.status or "available",
        "licenseNumber": driver.licenseNumber,
        "licenseClass": driver.licenseClass,
        "currentLocation": driver.currentLocation,
        "isActive": driver.isActive,
        "dateOfBirth": driver.dateOfBirth.isoformat() if driver.dateOfBirth else None,
        "licenseExpiry": driver.licenseExpiry.isoformat() if driver.licenseExpiry else None,
        "hireDate": driver.hireDate.isoformat() if driver.hireDate else None,
    }


@router.get("/truck")
def get_assigned_truck(
    token_data: dict = Depends(get_current_driver_token),
    db: Session = Depends(get_db)
):
    """Get the truck assigned to the current driver"""
    driver_id = token_data.get("driverId")
    
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    # Find equipment (truck) assigned to this driver
    # First check Equipment table for assigned truck
    truck = db.query(Equipment).filter(
        Equipment.assignedDriverId == driver_id,
        Equipment.equipmentType.in_(["Tractor", "Straight Truck", "Day Cab", "Sleeper"]),
        Equipment.isActive == True
    ).first()
    
    if not truck:
        # If no truck in Equipment table, return None - driver has no assigned truck
        return None
    
    return {
        "id": truck.id,
        "truckNumber": truck.equipmentNumber,
        "equipmentType": truck.equipmentType,
        "make": truck.make,
        "model": truck.model,
        "year": truck.year,
        "vin": truck.vinNumber,
        "licensePlate": truck.plateNumber,
        "registrationState": truck.registrationState,
        "status": truck.status,
        "operationalStatus": truck.operationalStatus,
        "fuelType": truck.fuelType,
        "currentMileage": truck.currentMileage,
        "engineType": truck.engineType,
        "eldProvider": truck.eldProvider,
        "eldDeviceId": truck.eldDeviceId,
        "registrationExpiry": truck.registrationExpiry.isoformat() if truck.registrationExpiry else None,
        "insuranceProvider": truck.insuranceProvider,
        "insurancePolicyNumber": truck.insurancePolicyNumber,
        "insuranceExpiry": truck.insuranceExpiry.isoformat() if truck.insuranceExpiry else None,
        "homeTerminal": truck.homeTerminal,
        "isActive": truck.isActive,
        "specialFeatures": truck.specialFeatures,
        "additionalNotes": truck.additionalNotes,
        "currentLocation": truck.currentLocation,
        "companyId": truck.companyId
    }


@router.patch("/truck/status")
def update_truck_status(
    request: dict,
    token_data: dict = Depends(get_current_driver_token),
    db: Session = Depends(get_db)
):
    """Update truck status (for pre-trip inspection, etc.)"""
    driver_id = token_data.get("driverId")
    
    # Find driver's assigned truck
    truck = db.query(Equipment).filter(
        Equipment.assignedDriverId == driver_id,
        Equipment.equipmentType.in_(["Tractor", "Straight Truck", "Day Cab", "Sleeper"]),
        Equipment.isActive == True
    ).first()
    
    if not truck:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No assigned truck found"
        )
    
    # Update truck status
    if "status" in request:
        truck.status = request["status"]
    
    if "notes" in request:
        if not truck.additionalNotes:
            truck.additionalNotes = ""
        truck.additionalNotes += f"\n[{datetime.utcnow().isoformat()}] {request['notes']}"
    
    db.commit()
    
    return {"success": True, "message": "Truck status updated"}


@router.post("/truck/issue")
def report_truck_issue(
    request: dict,
    token_data: dict = Depends(get_current_driver_token),
    db: Session = Depends(get_db)
):
    """Report a truck issue"""
    driver_id = token_data.get("driverId")
    
    # Find driver's assigned truck
    truck = db.query(Equipment).filter(
        Equipment.assignedDriverId == driver_id,
        Equipment.equipmentType.in_(["Tractor", "Straight Truck", "Day Cab", "Sleeper"]),
        Equipment.isActive == True
    ).first()
    
    if not truck:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No assigned truck found"
        )
    
    # Add issue to truck notes
    issue_report = f"\n[ISSUE - {datetime.utcnow().isoformat()}] {request.get('type', 'General')}: {request.get('description', 'No description')} (Severity: {request.get('severity', 'medium')})"
    
    if not truck.additionalNotes:
        truck.additionalNotes = ""
    truck.additionalNotes += issue_report
    
    # If critical issue, mark truck as maintenance required
    if request.get("severity") == "critical":
        truck.status = "maintenance"
        truck.operationalStatus = "maintenance"
    
    db.commit()
    
    return {"success": True, "message": "Issue reported successfully"}
