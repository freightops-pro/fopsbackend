from datetime import date, datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, EmailStr


class DriverIncidentCreate(BaseModel):
    occurred_at: datetime
    incident_type: str
    severity: str = Field(..., pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    description: Optional[str] = None


class DriverTrainingCreate(BaseModel):
    course_name: str
    completed_at: datetime
    expires_at: Optional[datetime] = None
    instructor: Optional[str] = None
    notes: Optional[str] = None


class DriverResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: Optional[str]
    phone: Optional[str]
    cdl_expiration: Optional[date]
    medical_card_expiration: Optional[date]

    model_config = {"from_attributes": True}


class DriverIncidentResponse(BaseModel):
    id: str
    occurred_at: datetime
    incident_type: str
    severity: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class DriverTrainingResponse(BaseModel):
    id: str
    course_name: str
    completed_at: datetime
    expires_at: Optional[datetime] = None
    instructor: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class DriverDocumentResponse(BaseModel):
    id: str
    document_type: str
    file_url: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class DriverComplianceResponse(BaseModel):
    driver: DriverResponse
    incidents: List[DriverIncidentResponse]
    training: List[DriverTrainingResponse]
    documents: List[DriverDocumentResponse]


class DriverComplianceSummaryResponse(BaseModel):
    cdl_expiration: Optional[date] = None
    medical_card_expiration: Optional[date] = None
    last_mvr_check: Optional[datetime] = None
    last_drug_test: Optional[datetime] = None
    clearinghouse_status: Optional[str] = None
    safety_rating: Optional[str] = None
    violations: Optional[int] = None


class DriverDocumentAttachmentResponse(BaseModel):
    id: str
    file_name: str
    url: Optional[str] = None
    uploaded_at: datetime
    uploaded_by: Optional[str] = None


class DriverComplianceProfileResponse(BaseModel):
    id: str
    company_id: str
    driver_number: Optional[str] = None
    first_name: str
    last_name: str
    middle_initial: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    status: str = "ACTIVE"
    home_address: Optional[str] = None
    license_number: Optional[str] = None
    license_state: Optional[str] = None
    license_class: Optional[str] = None
    license_expiration: Optional[date] = None
    medical_card_expiration: Optional[date] = None
    endorsements: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    compliance: Optional[DriverComplianceSummaryResponse] = None
    incidents: List[DriverIncidentResponse] = Field(default_factory=list)
    training: List[DriverTrainingResponse] = Field(default_factory=list)
    documents: List[DriverDocumentAttachmentResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class DriverComplianceUpdateRequest(BaseModel):
    cdl_expiration: Optional[date] = None  # Accept cdl_expiration from frontend
    medical_card_expiration: Optional[date] = None
    last_mvr_check: Optional[datetime] = None
    last_drug_test: Optional[datetime] = None
    clearinghouse_status: Optional[str] = None
    safety_rating: Optional[str] = None
    violations: Optional[int] = None


class DriverEndorsements(BaseModel):
    hazmat: bool = False
    tankers: bool = False
    doubles_triples: bool = False
    other: Optional[str] = None


class DriverCreate(BaseModel):
    driverType: Literal["company", "owner_driver", "owner_operator"]
    firstName: str
    middleInitial: Optional[str] = None
    lastName: str
    ssn: str
    dob: date
    phoneNumber: str
    email: Optional[EmailStr] = None
    homeAddress: str
    emergencyContact: str
    licenseNumber: str
    licenseState: str
    licenseClass: Literal["A", "B"]
    licenseIssue: date
    licenseExpiry: date
    endorsements: DriverEndorsements = Field(default_factory=lambda: DriverEndorsements())
    payrollType: Literal["hourly", "salary", "per_mile", "per_load"]
    payRate: str
    depositType: Literal["check", "direct_deposit"]
    bankName: Optional[str] = None
    routingNumber: Optional[str] = None
    accountNumber: Optional[str] = None
    notes: Optional[str] = None
    createAppAccess: bool = True  # Whether to create a user account for app access


class DriverCreateResponse(BaseModel):
    driver_id: str
    user_id: Optional[str] = None
    email: Optional[str] = None
    temporary_password: Optional[str] = None
    message: str


class DriverProfileUpdate(BaseModel):
    """Update driver profile information"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_initial: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    phone: Optional[str] = None  # Accept both phone and phone_number from frontend
    home_address: Optional[str] = None
    status: Optional[Literal["ACTIVE", "INACTIVE", "SUSPENDED", "ONBOARDING"]] = None

    # CDL information
    license_number: Optional[str] = None
    cdl_number: Optional[str] = None  # Accept both cdl_number and license_number from frontend
    license_state: Optional[str] = None
    license_class: Optional[Literal["A", "B"]] = None
    license_expiration: Optional[date] = None

    # Compliance dates
    medical_card_expiration: Optional[date] = None

    # Endorsements
    endorsements: Optional[DriverEndorsements] = None


class UserAccessInfo(BaseModel):
    """User access information for a driver"""
    user_id: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None  # active, suspended, none
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserAccessActionResponse(BaseModel):
    """Response for user access actions"""
    success: bool
    message: str


class GeneratePasswordResponse(BaseModel):
    """Response for generating a new password"""
    temporary_password: str
    message: str


class DriverEquipmentInfo(BaseModel):
    """Equipment assigned to a driver"""
    truck_id: Optional[str] = None
    truck_number: Optional[str] = None
    trailer_id: Optional[str] = None
    trailer_number: Optional[str] = None
    fuel_card_id: Optional[str] = None
    fuel_card_number: Optional[str] = None


class EquipmentBasicInfo(BaseModel):
    """Basic equipment information"""
    id: str
    unit_number: str
    equipment_type: str
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    status: str

    model_config = {"from_attributes": True}


class FuelCardBasicInfo(BaseModel):
    """Basic fuel card information"""
    id: str
    card_number: str
    card_provider: str
    card_nickname: Optional[str] = None
    status: str

    model_config = {"from_attributes": True}


class AvailableEquipmentResponse(BaseModel):
    """Available equipment for assignment"""
    trucks: List[EquipmentBasicInfo] = Field(default_factory=list)
    trailers: List[EquipmentBasicInfo] = Field(default_factory=list)
    fuel_cards: List[FuelCardBasicInfo] = Field(default_factory=list)


class AssignEquipmentRequest(BaseModel):
    """Request to assign equipment to a driver"""
    equipment_id: str


class LocationUpdate(BaseModel):
    """Driver location update for real-time tracking"""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in degrees")
    speed: Optional[float] = Field(None, ge=0, description="Speed in mph")
    heading: Optional[float] = Field(None, ge=0, lt=360, description="Heading in degrees (0-359)")
    accuracy: Optional[float] = Field(None, ge=0, description="Accuracy in meters")
    altitude: Optional[float] = Field(None, description="Altitude in meters")
    timestamp: Optional[datetime] = Field(None, description="Location timestamp")
    load_id: Optional[str] = Field(None, description="Current load ID if on active load")

