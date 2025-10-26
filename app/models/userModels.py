from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, func, Integer, Numeric, text, UUID, Text, JSON, Date
from sqlalchemy.orm import relationship
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, TYPE_CHECKING
from datetime import datetime, date
from app.config.db import Base
import uuid

# TYPE_CHECKING imports - only used for type hints, avoids circular imports
if TYPE_CHECKING:
    from app.models.load_leg import LoadLeg
    from app.models.multi_location import Location

# SQLAlchemy Models

# -------- Users Table --------
class Users(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    firstname = Column("first_name", String)
    lastname = Column("last_name", String)
    password = Column(String, nullable=False)
    phone = Column(String)
    role = Column(String, default="user")
    companyid = Column("company_id", String, ForeignKey("companies.id"))
    isactive = Column("is_active", Boolean, default=True)
    lastlogin = Column("last_login", DateTime)
    createdat = Column("created_at", DateTime, default=func.now())
    updatedat = Column("updated_at", DateTime, default=func.now(), onupdate=func.now())
    
    # Email verification fields (commented out - not in Neon database schema)
    # emailverified = Column("email_verified", Boolean, default=False)
    # activationtoken = Column("activation_token", String)
    # activationtokenexpiry = Column("activation_token_expiry", DateTime)
    
    # Set these as properties to avoid AttributeError
    @property
    def emailverified(self):
        return True  # Assume users in Neon DB are verified
    
    @property
    def activationtoken(self):
        return None
    
    @property
    def activationtokenexpiry(self):
        return None

    # Relationships
    company = relationship("Companies", back_populates="users")
    company_users = relationship("CompanyUser", back_populates="user")


# -------- Companies Table --------
class Companies(Base):
    __tablename__ = "companies"

    id = Column(String, primary_key=True, index=True)
    # subscriber_id = Column(String, ForeignKey("subscribers.id"), nullable=True)  # Not in Neon DB schema
    name = Column(String, nullable=False)
    email = Column(String, unique=True)
    phone = Column(String)
    address = Column(String)
    city = Column(String)
    state = Column(String)
    zipCode = Column("zip_code", String)
    dotNumber = Column("dot_number", String)
    mcNumber = Column("mc_number", String)
    ein = Column(String)
    businessType = Column("business_type", String)
    yearsInBusiness = Column("years_in_business", Integer)
    numberOfTrucks = Column("number_of_trucks", Integer)
    walletBalance = Column("wallet_balance", Numeric, default=0)
    subscriptionStatus = Column("subscription_status", String, default="trial")
    subscriptionPlan = Column("subscription_plan", String, default="starter")
    subscriptionTier = Column("subscription_tier", String)  # This column exists in DB
    # Columns commented out - not in Neon database schema
    # stripeCustomerId = Column("stripe_customer_id", String)
    # railsrEnduserId = Column("railsr_enduser_id", String)
    # railsrLedgerId = Column("railsr_ledger_id", String)
    # bankAccountNumber = Column("bank_account_number", String)
    # bankRoutingNumber = Column("bank_routing_number", String)
    # gustoCompanyId = Column("gusto_company_id", String)
    # gustoAccessToken = Column("gusto_access_token", String)
    # gustoRefreshToken = Column("gusto_refresh_token", String)
    # gustoTokenExpiry = Column("gusto_token_expiry", DateTime)
    createdAt = Column("created_at", DateTime, default=func.now())
    updatedAt = Column("updated_at", DateTime, default=func.now(), onupdate=func.now())
    isActive = Column("is_active", Boolean, default=True)
    # handlesContainers = Column("handles_containers", Boolean, default=False)  # Not in DB
    # containerTrackingEnabled = Column("container_tracking_enabled", Boolean, default=False)  # Not in DB
    
    # Properties for backward compatibility
    @property
    def stripeCustomerId(self):
        return None
    
    @property
    def railsrEnduserId(self):
        return None
    
    @property
    def railsrLedgerId(self):
        return None
    
    @property
    def bankAccountNumber(self):
        return None
    
    @property
    def bankRoutingNumber(self):
        return None
    
    @property
    def gustoCompanyId(self):
        return None
    
    @property
    def gustoAccessToken(self):
        return None
    
    @property
    def gustoRefreshToken(self):
        return None
    
    @property
    def gustoTokenExpiry(self):
        return None
    
    @property
    def handlesContainers(self):
        return False
    
    @property
    def containerTrackingEnabled(self):
        return False

    # Relationships
    # subscriber = relationship("Subscriber", back_populates="companies")  # Not in Neon DB schema
    users = relationship("Users", back_populates="company")
    drivers = relationship("Driver", back_populates="company")
    trucks = relationship("Truck", back_populates="company")
    loads = relationship("Loads", back_populates="company")
    stripe_customer = relationship("StripeCustomer", back_populates="company", uselist=False)
    subscription = relationship("CompanySubscription", back_populates="company", uselist=False)
    company_users = relationship("CompanyUser", back_populates="company")
    
    # Enterprise relationships
    white_label_config = relationship("WhiteLabelConfig", back_populates="company", uselist=False)
    webhooks = relationship("Webhook", back_populates="company")
    custom_workflows = relationship("CustomWorkflow", back_populates="company")
    enterprise_integrations = relationship("EnterpriseIntegration", back_populates="company")
    
    # Multi-authority relationship
    authorities = relationship("Authority", back_populates="company")
    
    # Load legs relationship
    load_legs = relationship("LoadLeg", back_populates="company")
    
    # Multi-location relationship
    locations = relationship("Location", back_populates="company")


# -------- Drivers Table --------
class Driver(Base):
    __tablename__ = "drivers"

    id = Column(String, primary_key=True, nullable=False)
    companyId = Column(String, ForeignKey("companies.id"), nullable=False)
    firstName = Column(String, nullable=False)
    lastName = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    licenseNumber = Column(String, nullable=False)
    licenseClass = Column(String, nullable=False)
    licenseExpiry = Column(DateTime, nullable=False)
    dateOfBirth = Column(DateTime, nullable=False)
    address = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)
    zipCode = Column(String, nullable=False)
    emergencyContact = Column(String, nullable=False)
    emergencyPhone = Column(String, nullable=False)
    hireDate = Column(DateTime, nullable=False)
    status = Column(String, server_default="available")
    payRate = Column(Numeric, nullable=False)
    payType = Column(String, nullable=False)
    hoursRemaining = Column(Numeric)
    currentLocation = Column(String)
    passwordHash = Column("passwordhash", String, nullable=True)
    isActive = Column(Boolean, server_default="true")
    homeLocationId = Column("home_location_id", Integer, ForeignKey("locations.id"), nullable=True)
    createdAt = Column(DateTime, server_default=func.now())
    updatedAt = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Companies", back_populates="drivers")
    home_location = relationship("Location", back_populates="drivers")

# -------- Trucks Table --------
class Truck(Base):
    __tablename__ = "trucks"

    id = Column(String, primary_key=True, nullable=False)
    companyId = Column(String, ForeignKey("companies.id"), nullable=False)
    truckNumber = Column(String, nullable=False)
    make = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    vin = Column(String, nullable=False)
    licensePlate = Column(String, nullable=False)
    registrationState = Column(String)
    status = Column(String)
    createdAt = Column(DateTime, server_default=func.now())
    updatedAt = Column(DateTime, server_default=func.now(), onupdate=func.now())
    fuelType = Column(String)
    fuelEfficiency = Column(Numeric)
    maintenanceStatus = Column(String)
    lastMaintenanceDate = Column(DateTime)
    nextMaintenanceDate = Column(DateTime)
    insuranceProvider = Column(String)
    insurancePolicyNumber = Column(String)
    insuranceExpiry = Column(DateTime)
    isActive = Column(Boolean, server_default='true')
    homeLocationId = Column("home_location_id", Integer, ForeignKey("locations.id"), nullable=True)
    
    # Relationships
    company = relationship("Companies", back_populates="trucks")
    home_location = relationship("Location", back_populates="vehicles")

# -------- Equipment Table (Unified for Trucks and Trailers) --------
class Equipment(Base):
    __tablename__ = "equipment"

    id = Column(String, primary_key=True, nullable=False, default=lambda: str(uuid.uuid4()))
    companyId = Column(String, ForeignKey("companies.id"), nullable=False)
    
    # Basic Information
    equipmentNumber = Column(String, nullable=False, unique=True)
    equipmentType = Column(String, nullable=False)  # Tractor, Straight Truck, Day Cab, Sleeper, Yard Truck, Dry Van Trailer, Reefer Trailer, etc.
    make = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year = Column(String, nullable=False)
    vinNumber = Column(String, nullable=False, unique=True)
    plateNumber = Column(String)  # Optional for trailers
    
    # Engine & Performance (for trucks only)
    currentMileage = Column(Integer)
    engineType = Column(String)
    fuelType = Column(String, default="Diesel")
    
    # ELD Integration (for trucks only)
    eldProvider = Column(String)
    eldDeviceId = Column(String)
    
    # Trailer Specifications (for trailers only)
    trailerType = Column(String)
    trailerLength = Column(String)
    maxWeight = Column(String)
    
    # Registration & Insurance
    registrationState = Column(String)
    registrationExpiry = Column(DateTime)
    insuranceProvider = Column(String)
    insurancePolicyNumber = Column(String)
    insuranceExpiry = Column(DateTime)
    dotNumber = Column(String)
    mcNumber = Column(String)
    
    # Financial & Operations
    purchasePrice = Column(Numeric)
    monthlyPayment = Column(Numeric)
    assignedDriverId = Column(String, ForeignKey("drivers.id"))
    homeTerminal = Column(String)
    operationalStatus = Column(String, default="active")  # active, maintenance, inactive, sold
    
    # Special Equipment & Features (JSON field for flexibility)
    specialFeatures = Column(JSON)  # APU, Inverter, Refrigeration, Lift Gate, etc.
    additionalNotes = Column(Text)
    
    # Status and tracking
    status = Column(String, default="available")  # available, in_transit, maintenance, out_of_service
    currentLocation = Column(String)
    
    # Timestamps
    createdAt = Column(DateTime, server_default=func.now())
    updatedAt = Column(DateTime, server_default=func.now(), onupdate=func.now())
    isActive = Column(Boolean, default=True)

# -------- Maintenance Schedule Table --------
class MaintenanceSchedule(Base):
    __tablename__ = "maintenance_schedule"

    id = Column(String, primary_key=True, nullable=False, default=lambda: str(uuid.uuid4()))
    companyId = Column(String, ForeignKey("companies.id"), nullable=False)
    equipmentId = Column(String, ForeignKey("equipment.id"), nullable=False)
    
    # Maintenance Details
    title = Column(String, nullable=False)
    description = Column(Text)
    maintenanceType = Column(String, nullable=False)  # preventive, corrective, emergency, inspection
    priority = Column(String, default="medium")  # low, medium, high, critical
    
    # Scheduling
    scheduledDate = Column(DateTime, nullable=False)
    estimatedDuration = Column(Integer)  # in hours
    estimatedCost = Column(Numeric)
    
    # Recurring Maintenance
    isRecurring = Column(Boolean, default=False)
    recurrenceType = Column(String)  # daily, weekly, monthly, yearly, mileage
    recurrenceInterval = Column(Integer)  # every X days/weeks/months/years/miles
    nextOccurrence = Column(DateTime)
    
    # Status and Progress
    status = Column(String, default="scheduled")  # scheduled, in_progress, completed, cancelled, overdue
    actualStartDate = Column(DateTime)
    actualEndDate = Column(DateTime)
    actualCost = Column(Numeric)
    
    # Assignment
    assignedTechnician = Column(String)
    assignedVendor = Column(String)
    vendorContact = Column(String)
    vendorPhone = Column(String)
    
    # Location and Notes
    location = Column(String)
    notes = Column(Text)
    attachments = Column(JSON)  # URLs to documents, photos, etc.
    
    # Timestamps
    createdAt = Column(DateTime, server_default=func.now())
    updatedAt = Column(DateTime, server_default=func.now(), onupdate=func.now())
    createdBy = Column(String, ForeignKey("users.id"))
    isActive = Column(Boolean, default=True)

# -------- ELD Alerts Table --------
class ELDAlert(Base):
    __tablename__ = "eld_alerts"

    id = Column(String, primary_key=True, nullable=False, default=lambda: str(uuid.uuid4()))
    companyId = Column(String, ForeignKey("companies.id"), nullable=False)
    equipmentId = Column(String, ForeignKey("equipment.id"), nullable=False)
    driverId = Column(String, ForeignKey("drivers.id"))
    
    # Alert Details
    alertType = Column(String, nullable=False)  # hours_of_service, vehicle_inspection, eld_malfunction, data_transfer
    severity = Column(String, default="medium")  # low, medium, high, critical
    title = Column(String, nullable=False)
    description = Column(Text)
    
    # Alert Data
    alertData = Column(JSON)  # Additional data specific to alert type
    location = Column(String)
    
    # Status
    status = Column(String, default="active")  # active, acknowledged, resolved, dismissed
    acknowledgedBy = Column(String, ForeignKey("users.id"))
    acknowledgedAt = Column(DateTime)
    resolvedBy = Column(String, ForeignKey("users.id"))
    resolvedAt = Column(DateTime)
    
    # Timestamps
    createdAt = Column(DateTime, server_default=func.now())
    updatedAt = Column(DateTime, server_default=func.now(), onupdate=func.now())
    isActive = Column(Boolean, default=True)

# -------- Road Services Table --------
class RoadService(Base):
    __tablename__ = "road_services"

    id = Column(String, primary_key=True, nullable=False, default=lambda: str(uuid.uuid4()))
    companyId = Column(String, ForeignKey("companies.id"), nullable=False)
    equipmentId = Column(String, ForeignKey("equipment.id"), nullable=False)
    driverId = Column(String, ForeignKey("drivers.id"))
    
    # Service Details
    serviceType = Column(String, nullable=False)  # towing, fuel, tire_repair, mechanical, medical, accident
    priority = Column(String, default="medium")  # low, medium, high, emergency
    title = Column(String, nullable=False)
    description = Column(Text)
    
    # Location and Contact
    location = Column(String, nullable=False)
    latitude = Column(Numeric)
    longitude = Column(Numeric)
    contactName = Column(String)
    contactPhone = Column(String)
    
    # Service Provider
    serviceProvider = Column(String)
    providerPhone = Column(String)
    estimatedArrival = Column(DateTime)
    estimatedCost = Column(Numeric)
    
    # Status and Progress
    status = Column(String, default="requested")  # requested, dispatched, en_route, on_site, completed, cancelled
    requestedAt = Column(DateTime, server_default=func.now())
    dispatchedAt = Column(DateTime)
    arrivedAt = Column(DateTime)
    completedAt = Column(DateTime)
    actualCost = Column(Numeric)
    
    # Additional Details
    notes = Column(Text)
    photos = Column(JSON)  # URLs to photos
    documents = Column(JSON)  # URLs to documents
    
    # Timestamps
    createdAt = Column(DateTime, server_default=func.now())
    updatedAt = Column(DateTime, server_default=func.now(), onupdate=func.now())
    createdBy = Column(String, ForeignKey("users.id"))
    isActive = Column(Boolean, default=True)

# -------- ELD Compliance Table --------
class ELDCompliance(Base):
    __tablename__ = "eld_compliance"

    id = Column(String, primary_key=True, nullable=False, default=lambda: str(uuid.uuid4()))
    companyId = Column(String, ForeignKey("companies.id"), nullable=False)
    driverId = Column(String, ForeignKey("drivers.id"), nullable=False)
    equipmentId = Column(String, ForeignKey("equipment.id"), nullable=False)
    
    # ELD Data
    date = Column(Date, nullable=False)
    totalDrivingTime = Column(Integer)  # in minutes
    totalOnDutyTime = Column(Integer)  # in minutes
    totalOffDutyTime = Column(Integer)  # in minutes
    totalSleeperTime = Column(Integer)  # in minutes
    
    # Violations
    hasViolations = Column(Boolean, default=False)
    violations = Column(JSON)  # Array of violation details
    violationTypes = Column(JSON)  # Types of violations found
    
    # Compliance Status
    isCompliant = Column(Boolean, default=True)
    complianceScore = Column(Integer)  # 0-100
    auditStatus = Column(String, default="pending")  # pending, reviewed, approved, flagged
    
    # AI Audit Results
    aiAuditResults = Column(JSON)  # AI analysis results
    aiRecommendations = Column(Text)
    aiConfidence = Column(Numeric)  # 0-1 confidence score
    
    # Export Data
    exportedAt = Column(DateTime)
    exportFormat = Column(String)  # pdf, csv, xml
    exportUrl = Column(String)
    
    # Timestamps
    createdAt = Column(DateTime, server_default=func.now())
    updatedAt = Column(DateTime, server_default=func.now(), onupdate=func.now())
    isActive = Column(Boolean, default=True)

# -------- SAFER Data Table --------
class SAFERData(Base):
    __tablename__ = "safer_data"

    id = Column(String, primary_key=True, nullable=False, default=lambda: str(uuid.uuid4()))
    companyId = Column(String, ForeignKey("companies.id"), nullable=False)
    
    # Company Information
    dotNumber = Column(String, nullable=False)
    legalName = Column(String, nullable=False)
    dbaName = Column(String)
    address = Column(String)
    city = Column(String)
    state = Column(String)
    zipCode = Column(String)
    country = Column(String, default="US")
    
    # Safety Ratings
    safetyRating = Column(String)  # Satisfactory, Conditional, Unsatisfactory
    safetyRatingDate = Column(Date)
    previousSafetyRating = Column(String)
    
    # Inspection Data
    totalInspections = Column(Integer, default=0)
    totalInspectionsWithViolations = Column(Integer, default=0)
    totalViolations = Column(Integer, default=0)
    totalOutOfServiceViolations = Column(Integer, default=0)
    totalOutOfServiceViolationsPercentage = Column(Numeric)
    
    # Crash Data
    totalCrashes = Column(Integer, default=0)
    fatalCrashes = Column(Integer, default=0)
    injuryCrashes = Column(Integer, default=0)
    towAwayCrashes = Column(Integer, default=0)
    
    # Vehicle Information
    totalVehicles = Column(Integer, default=0)
    totalDrivers = Column(Integer, default=0)
    
    # Report Data
    lastReportGenerated = Column(DateTime)
    reportUrl = Column(String)
    portalUrl = Column(String)
    
    # Timestamps
    createdAt = Column(DateTime, server_default=func.now())
    updatedAt = Column(DateTime, server_default=func.now(), onupdate=func.now())
    isActive = Column(Boolean, default=True)

# -------- Insurance Policies Table --------
class InsurancePolicy(Base):
    __tablename__ = "insurance_policies"

    id = Column(String, primary_key=True, nullable=False, default=lambda: str(uuid.uuid4()))
    companyId = Column(String, ForeignKey("companies.id"), nullable=False)
    
    # Policy Information
    policyNumber = Column(String, nullable=False)
    policyType = Column(String, nullable=False)  # auto_liability, cargo, general_liability, workers_comp
    insuranceProvider = Column(String, nullable=False)
    agentName = Column(String)
    agentPhone = Column(String)
    agentEmail = Column(String)
    
    # Coverage Details
    coverageAmount = Column(Numeric, nullable=False)
    deductible = Column(Numeric)
    premium = Column(Numeric, nullable=False)
    paymentFrequency = Column(String)  # monthly, quarterly, annually
    
    # Dates
    effectiveDate = Column(Date, nullable=False)
    expirationDate = Column(Date, nullable=False)
    renewalDate = Column(Date)
    
    # Status
    status = Column(String, default="active")  # active, expired, cancelled, pending_renewal
    isRenewed = Column(Boolean, default=False)
    
    # Documents
    policyDocument = Column(String)  # URL to policy document
    certificateOfInsurance = Column(String)  # URL to COI
    
    # Notes
    notes = Column(Text)
    
    # Timestamps
    createdAt = Column(DateTime, server_default=func.now())
    updatedAt = Column(DateTime, server_default=func.now(), onupdate=func.now())
    createdBy = Column(String, ForeignKey("users.id"))
    isActive = Column(Boolean, default=True)

# -------- Permit Books Table --------
class PermitBook(Base):
    __tablename__ = "permit_books"

    id = Column(String, primary_key=True, nullable=False, default=lambda: str(uuid.uuid4()))
    companyId = Column(String, ForeignKey("companies.id"), nullable=False)
    equipmentId = Column(String, ForeignKey("equipment.id"))
    
    # Permit Information
    permitNumber = Column(String, nullable=False)
    permitType = Column(String, nullable=False)  # oversize, overweight, hazmat, special
    issuingAuthority = Column(String, nullable=False)  # State DOT, etc.
    state = Column(String, nullable=False)
    
    # Permit Details
    description = Column(Text)
    route = Column(Text)  # Allowed route
    restrictions = Column(Text)  # Any restrictions
    specialConditions = Column(Text)
    
    # Dates
    issueDate = Column(Date, nullable=False)
    expirationDate = Column(Date, nullable=False)
    renewalDate = Column(Date)
    
    # Fees
    permitFee = Column(Numeric)
    processingFee = Column(Numeric)
    totalFee = Column(Numeric)
    
    # Status
    status = Column(String, default="active")  # active, expired, suspended, cancelled
    isRenewed = Column(Boolean, default=False)
    
    # Documents
    permitDocument = Column(String)  # URL to permit document
    applicationDocument = Column(String)  # URL to application
    
    # Notes
    notes = Column(Text)
    
    # Timestamps
    createdAt = Column(DateTime, server_default=func.now())
    updatedAt = Column(DateTime, server_default=func.now(), onupdate=func.now())
    createdBy = Column(String, ForeignKey("users.id"))
    isActive = Column(Boolean, default=True)

# -------- Driver HOS Logs Table --------
class DriverHOSLog(Base):
    __tablename__ = "driver_hos_logs"

    id = Column(String, primary_key=True, nullable=False, default=lambda: str(uuid.uuid4()))
    companyId = Column(String, ForeignKey("companies.id"), nullable=False)
    driverId = Column(String, ForeignKey("drivers.id"), nullable=False)
    equipmentId = Column(String, ForeignKey("equipment.id"), nullable=False)
    
    # Log Date
    logDate = Column(Date, nullable=False)
    
    # Time Breakdown (in minutes)
    drivingTime = Column(Integer, default=0)
    onDutyTime = Column(Integer, default=0)
    offDutyTime = Column(Integer, default=0)
    sleeperTime = Column(Integer, default=0)
    
    # Break Compliance
    hasRequiredBreaks = Column(Boolean, default=True)
    breakViolations = Column(JSON)  # Array of break violations
    
    # 11-Hour Rule
    elevenHourCompliant = Column(Boolean, default=True)
    elevenHourViolations = Column(JSON)
    
    # 14-Hour Rule
    fourteenHourCompliant = Column(Boolean, default=True)
    fourteenHourViolations = Column(JSON)
    
    # 70-Hour Rule (8-day)
    seventyHourCompliant = Column(Boolean, default=True)
    seventyHourViolations = Column(JSON)
    
    # 34-Hour Restart
    thirtyFourHourCompliant = Column(Boolean, default=True)
    thirtyFourHourViolations = Column(JSON)
    
    # ELD Data
    eldDeviceId = Column(String)
    eldProvider = Column(String)
    dataTransferStatus = Column(String)  # successful, failed, pending
    
    # Compliance Status
    isCompliant = Column(Boolean, default=True)
    violations = Column(JSON)  # All violations for the day
    violationCount = Column(Integer, default=0)
    
    # Notes
    notes = Column(Text)
    
    # Timestamps
    createdAt = Column(DateTime, server_default=func.now())
    updatedAt = Column(DateTime, server_default=func.now(), onupdate=func.now())
    isActive = Column(Boolean, default=True)

# -------- Loads Table --------
class Loads(Base):
    __tablename__ = "loads"

    id = Column(String, primary_key=True, nullable=False)
    companyId = Column(String, ForeignKey("companies.id"), nullable=False)
    loadNumber = Column(String, nullable=False)
    status = Column(String, default="available")
    priority = Column(String, default="standard")
  
    # Customer Information
    customerName = Column(String, nullable=False)
    customerContact = Column(String, nullable=False)
    customerPhone = Column(String, nullable=False)
    customerEmail = Column(String, nullable=False)
  
    # Pickup Information
    pickupLocation = Column(String, nullable=False)
    pickupAddress = Column(String, nullable=False)
    pickupCity = Column(String, nullable=False)
    pickupState = Column(String, nullable=False)
    pickupZip = Column(String, nullable=False)
    pickupDate = Column(String, nullable=False)
    pickupTime = Column(String, nullable=False)
    pickupWindow = Column(String, nullable=False)
    pickupContact = Column(String, nullable=False)
    pickupPhone = Column(String, nullable=False)
    pickupInstructions = Column(String, nullable=False)
  
    # Delivery Information
    deliveryLocation = Column(String, nullable=False)
    deliveryAddress = Column(String, nullable=False)
    deliveryCity = Column(String, nullable=False)
    deliveryState = Column(String, nullable=False)
    deliveryZip = Column(String, nullable=False)
    deliveryDate = Column(String, nullable=False)
    deliveryTime = Column(String, nullable=False)
    deliveryWindow = Column(String, nullable=False)
    deliveryContact = Column(String, nullable=False)
    deliveryPhone = Column(String, nullable=False)
    deliveryInstructions = Column(String, nullable=False)
  
    # Load Details
    commodity = Column(String, nullable=False)
    commodityType = Column(String, default="general_freight") # general_freight, hazmat, refrigerated, oversized, livestock, automotive
    weight = Column(Integer, nullable=False)
    pieces = Column(Integer, nullable=False)
    length = Column(Numeric, nullable=False)
    width = Column(Numeric, nullable=False)
    height = Column(Numeric, nullable=False)
    specialRequirements = Column(String, nullable=False)
  
    # Financial
    rate = Column(Numeric, nullable=False)
    rateType = Column(String, default="flat") # flat, per_mile, percentage
    fuelSurcharge = Column(Numeric, default="0")
    accessorialCharges = Column(Numeric, default="0")
    totalRate = Column(Numeric, nullable=False)
    fuelCost = Column(Numeric, default="0")
    driverPay = Column(Numeric, default="0")
    accessorials = Column(JSON, nullable=True)  # Store accessorial charges as JSON

    # Operational
    distance = Column(Integer, nullable=False)
    estimatedMiles = Column(Integer, nullable=False)
    estimatedDuration = Column(Integer, nullable=False) # in hours
    assignedDriverId = Column(String, ForeignKey("drivers.id"), nullable=False)
    assignedTruckId = Column(String, ForeignKey("trucks.id"), nullable=False)
    dispatchNotes = Column(String, nullable=False)
  
    # Tracking
    lastUpdate = Column(String, nullable=False)
    estimatedArrival = Column(String, nullable=False)
    proofOfDelivery = Column(String, nullable=False)
    
    # Smart Load Creation Fields
    trailerType = Column(String, nullable=False) # container, reefer, tanker, flatbed, dryvan
    loadCommodity = Column(String, nullable=False)
    
    # Container Load Fields
    isContainerLoad = Column(Boolean, default=False)
    containerNumber = Column(String)
    bolNumber = Column(String)
    lfsNumber = Column(String)
    ssl = Column(String) # Steamship Line
    vesselName = Column(String)
    portOfLoading = Column(String)
    portOfDischarge = Column(String)
    containerSize = Column(String) # 20ft, 40ft, 45ft
    grossWeight = Column(Integer)
    hazmat = Column(Boolean, default=False)
    containerCurrentLocation = Column(String)
    isCustomerHold = Column(Boolean, default=False)
    isAvailableForPickup = Column(Boolean, default=True)
    chassisRequired = Column(Boolean, default=False)
    chassisId = Column(String)
    chassisType = Column(String) # Standard, Triaxle, Tank
    chassisProvider = Column(String) # TRAC, FlexiVan, DCLI
    chassisFreeDays = Column(Integer, default=3)
    chassisPerDiemRate = Column(Numeric, default="0")
    containerFreeDays = Column(Integer, default=5)
    containerDemurrageRate = Column(Numeric, default="0")
    expressPassRequired = Column(Boolean, default=False)
    terminal = Column(String)
    
    # Reefer Load Fields
    temperature = Column(Integer)
    isFSMACompliant = Column(Boolean, default=False)
    preloadChecklistComplete = Column(Boolean, default=False)
    
    # Tanker Load Fields
    liquidType = Column(String) # Fuel, Milk, Water, Chemicals
    washType = Column(String) # Pre-clean type
    volume = Column(Integer) # gallons or liters
    
    # Flatbed Load Fields
    loadLength = Column(Numeric)
    loadWidth = Column(Numeric)
    loadHeight = Column(Numeric)
    tarpRequired = Column(Boolean, default=False)
    securementType = Column(String) # Chains, Straps, Coil Racks
    
    # Dry Van Load Fields
    palletCount = Column(Integer)
    isStackable = Column(Boolean, default=True)
    sealNumber = Column(String)
    
    # Legacy Intermodal Fields (maintained for compatibility)
    railCarNumber = Column(String)
    portCode = Column(String)
    railroad = Column(String)
    chassisNumber = Column(String)
    steamshipLine = Column(String)
    bookingNumber = Column(String)
    billOfLading = Column(String)
    containerType = Column(String)
    temperatureSettings = Column(String)
    intermodalTracking = Column(String)
    lastPortUpdate = Column(String)
    lastRailUpdate = Column(String)
    
    # Dispatch Integration
    isMultiDriverLoad = Column(Boolean, default=False)
    dispatchStatus = Column(String, default="planning") # planning, assigned, in_progress, completed
    pickupLocationId = Column("pickup_location_id", Integer, ForeignKey("locations.id"), nullable=True)
    deliveryLocationId = Column("delivery_location_id", Integer, ForeignKey("locations.id"), nullable=True)
    
    # Timestamps
    createdAt = Column(DateTime, server_default=func.now())
    updatedAt = Column(DateTime, server_default=func.now(), onupdate=func.now())
    dispatchedAt = Column(DateTime)
    pickedUpAt = Column(DateTime)
    deliveredAt = Column(DateTime)
    
    # Relationships
    company = relationship("Companies", back_populates="loads")
    pickup_location = relationship("Location", foreign_keys=[pickupLocationId], back_populates="loads_pickup")
    delivery_location = relationship("Location", foreign_keys=[deliveryLocationId], back_populates="loads_delivery")
    stops = relationship("LoadStop", back_populates="load")
    # legs = relationship("LoadLeg", back_populates="load")  # LoadLeg references SimpleLoad, not Loads

# -------- Dispatch Legs Table --------
class DispatchLeg(Base):
    __tablename__ = "dispatch_legs"

    id = Column(String, primary_key=True, nullable=False)
    load_id = Column(String, ForeignKey("loads.id"), nullable=False)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    driver_id = Column(String, ForeignKey("drivers.id"))
    truck_id = Column(String, ForeignKey("trucks.id"))
    trailer_id = Column(String)
    chassis_id = Column(String)
    action_type = Column(String, nullable=False)  # pickup, dropoff, move, return
    location = Column(Text, nullable=False)
    eta = Column(DateTime)
    etd = Column(DateTime)
    actual_arrival = Column(DateTime)
    actual_departure = Column(DateTime)
    completed = Column(Boolean, default=False)
    leg_order = Column(Integer, nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# -------- Load Assignments Table --------
class LoadAssignment(Base):
    __tablename__ = "load_assignments"

    id = Column(String, primary_key=True, nullable=False)
    load_id = Column(String, ForeignKey("loads.id"), nullable=False)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    driver_id = Column(String, ForeignKey("drivers.id"), nullable=False)
    truck_id = Column(String, ForeignKey("trucks.id"))
    trailer_id = Column(String)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    assignment_notes = Column(Text)
    status = Column(String, default="assigned")  # assigned, active, completed, cancelled
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# -------- Load Billing Table --------
class LoadBilling(Base):
    __tablename__ = "load_billing"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    load_id = Column(String, ForeignKey("loads.id"), nullable=False)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)

    # Base Rate
    base_rate = Column(Numeric(10, 2), nullable=False)
    rate_type = Column(String, default="flat")  # flat, per_mile, percentage
    rate_per_mile = Column(Numeric(8, 2))
    total_miles = Column(Integer)

    # Billing Status
    billing_status = Column(String, default="pending")  # pending, invoiced, paid, disputed
    invoice_number = Column(String)
    invoice_date = Column(DateTime)
    due_date = Column(DateTime)
    paid_date = Column(DateTime)

    # Customer Info
    customer_name = Column(String, nullable=False)
    customer_address = Column(Text)
    customer_terms = Column(String, default="NET30")  # NET15, NET30, NET45, COD

    # Totals
    subtotal = Column(Numeric(10, 2), default=0)
    total_accessorials = Column(Numeric(10, 2), default=0)
    total_expenses = Column(Numeric(10, 2), default=0)
    tax_amount = Column(Numeric(10, 2), default=0)
    total_amount = Column(Numeric(10, 2), default=0)

    # Payment Info
    payment_method = Column(String)  # check, ach, wire, factoring
    factor_company = Column(String)
    factor_rate = Column(Numeric(5, 2))

    # Notes & Docs
    billing_notes = Column(Text)
    internal_notes = Column(Text)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by = Column(String, ForeignKey("users.id"))
    last_modified_by = Column(String, ForeignKey("users.id"))


# -------- Load Accessorials Table --------
class LoadAccessorial(Base):
    __tablename__ = "load_accessorials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    load_id = Column(String, ForeignKey("loads.id"), nullable=False)
    billing_id = Column(UUID(as_uuid=True), ForeignKey("load_billing.id"), nullable=False)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)

    # Accessorial Details
    type = Column(String, nullable=False)  # detention, layover, etc.
    description = Column(Text, nullable=False)
    amount = Column(Numeric(8, 2), nullable=False)
    quantity = Column(Numeric(8, 2), default=1)
    rate = Column(Numeric(8, 2))

    # Billing Info
    is_billable = Column(Boolean, default=True)
    customer_approved = Column(Boolean, default=False)
    approval_date = Column(DateTime)
    approved_by = Column(String)

    # Documentation
    documentation = Column(JSON)
    notes = Column(Text)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by = Column(String, ForeignKey("users.id"))

# Pydantic Models for API
class UserBase(BaseModel):
    email: str
    firstName: str
    lastName: str
    phone: Optional[str] = None
    role: str = "user"
    companyId: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    isActive: Optional[bool] = None

class UserResponse(UserBase):
    id: str
    isActive: bool
    lastLogin: Optional[datetime]
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True

class CompanyBase(BaseModel):
    name: str
    email: str
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

class CompanyCreate(CompanyBase):
    pass

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
    walletBalance: Optional[float] = None
    subscriptionStatus: Optional[str] = None
    subscriptionPlan: Optional[str] = None

class CompanyResponse(CompanyBase):
    id: str
    walletBalance: float
    subscriptionStatus: str
    subscriptionPlan: str
    isActive: bool
    handlesContainers: bool
    containerTrackingEnabled: bool
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True

# Equipment Pydantic Models
class EquipmentBase(BaseModel):
    equipmentNumber: str
    equipmentType: str
    make: str
    model: str
    year: str
    vinNumber: str
    plateNumber: Optional[str] = None
    currentMileage: Optional[int] = None
    engineType: Optional[str] = None
    fuelType: Optional[str] = "Diesel"
    eldProvider: Optional[str] = None
    eldDeviceId: Optional[str] = None
    trailerType: Optional[str] = None
    trailerLength: Optional[str] = None
    maxWeight: Optional[str] = None
    registrationState: Optional[str] = None
    registrationExpiry: Optional[datetime] = None
    insuranceProvider: Optional[str] = None
    insurancePolicyNumber: Optional[str] = None
    insuranceExpiry: Optional[datetime] = None
    dotNumber: Optional[str] = None
    mcNumber: Optional[str] = None
    purchasePrice: Optional[float] = None
    monthlyPayment: Optional[float] = None
    assignedDriverId: Optional[str] = None
    homeTerminal: Optional[str] = None
    operationalStatus: Optional[str] = "active"
    specialFeatures: Optional[dict] = None
    additionalNotes: Optional[str] = None
    status: Optional[str] = "available"
    currentLocation: Optional[str] = None

class EquipmentCreate(EquipmentBase):
    pass

class EquipmentUpdate(BaseModel):
    equipmentNumber: Optional[str] = None
    equipmentType: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[str] = None
    vinNumber: Optional[str] = None
    plateNumber: Optional[str] = None
    currentMileage: Optional[int] = None
    engineType: Optional[str] = None
    fuelType: Optional[str] = None
    eldProvider: Optional[str] = None
    eldDeviceId: Optional[str] = None
    trailerType: Optional[str] = None
    trailerLength: Optional[str] = None
    maxWeight: Optional[str] = None
    registrationState: Optional[str] = None
    registrationExpiry: Optional[datetime] = None
    insuranceProvider: Optional[str] = None
    insurancePolicyNumber: Optional[str] = None
    insuranceExpiry: Optional[datetime] = None
    dotNumber: Optional[str] = None
    mcNumber: Optional[str] = None
    purchasePrice: Optional[float] = None
    monthlyPayment: Optional[float] = None
    assignedDriverId: Optional[str] = None
    homeTerminal: Optional[str] = None
    operationalStatus: Optional[str] = None
    specialFeatures: Optional[dict] = None
    additionalNotes: Optional[str] = None
    status: Optional[str] = None
    currentLocation: Optional[str] = None

class EquipmentResponse(EquipmentBase):
    id: str
    companyId: str
    createdAt: datetime
    updatedAt: datetime
    isActive: bool

    class Config:
        from_attributes = True

# Maintenance Pydantic Models
class MaintenanceScheduleBase(BaseModel):
    equipmentId: str
    title: str
    description: Optional[str] = None
    maintenanceType: str  # preventive, corrective, emergency, inspection
    priority: Optional[str] = "medium"
    scheduledDate: datetime
    estimatedDuration: Optional[int] = None
    estimatedCost: Optional[float] = None
    isRecurring: Optional[bool] = False
    recurrenceType: Optional[str] = None
    recurrenceInterval: Optional[int] = None
    assignedTechnician: Optional[str] = None
    assignedVendor: Optional[str] = None
    vendorContact: Optional[str] = None
    vendorPhone: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None

class MaintenanceScheduleCreate(MaintenanceScheduleBase):
    pass

class MaintenanceScheduleUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    maintenanceType: Optional[str] = None
    priority: Optional[str] = None
    scheduledDate: Optional[datetime] = None
    estimatedDuration: Optional[int] = None
    estimatedCost: Optional[float] = None
    status: Optional[str] = None
    actualStartDate: Optional[datetime] = None
    actualEndDate: Optional[datetime] = None
    actualCost: Optional[float] = None
    assignedTechnician: Optional[str] = None
    assignedVendor: Optional[str] = None
    vendorContact: Optional[str] = None
    vendorPhone: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None

class MaintenanceScheduleResponse(MaintenanceScheduleBase):
    id: str
    companyId: str
    status: str
    actualStartDate: Optional[datetime] = None
    actualEndDate: Optional[datetime] = None
    actualCost: Optional[float] = None
    nextOccurrence: Optional[datetime] = None
    attachments: Optional[dict] = None
    createdAt: datetime
    updatedAt: datetime
    createdBy: Optional[str] = None
    isActive: bool

    class Config:
        from_attributes = True

# ELD Alert Pydantic Models
class ELDAlertBase(BaseModel):
    equipmentId: str
    driverId: Optional[str] = None
    alertType: str  # hours_of_service, vehicle_inspection, eld_malfunction, data_transfer
    severity: Optional[str] = "medium"
    title: str
    description: Optional[str] = None
    alertData: Optional[dict] = None
    location: Optional[str] = None

class ELDAlertCreate(ELDAlertBase):
    pass

class ELDAlertUpdate(BaseModel):
    status: Optional[str] = None
    acknowledgedBy: Optional[str] = None
    resolvedBy: Optional[str] = None

class ELDAlertResponse(ELDAlertBase):
    id: str
    companyId: str
    status: str
    acknowledgedBy: Optional[str] = None
    acknowledgedAt: Optional[datetime] = None
    resolvedBy: Optional[str] = None
    resolvedAt: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime
    isActive: bool

    class Config:
        from_attributes = True

# Road Service Pydantic Models
class RoadServiceBase(BaseModel):
    equipmentId: str
    driverId: Optional[str] = None
    serviceType: str  # towing, fuel, tire_repair, mechanical, medical, accident
    priority: Optional[str] = "medium"
    title: str
    description: Optional[str] = None
    location: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    contactName: Optional[str] = None
    contactPhone: Optional[str] = None
    serviceProvider: Optional[str] = None
    providerPhone: Optional[str] = None
    estimatedArrival: Optional[datetime] = None
    estimatedCost: Optional[float] = None
    notes: Optional[str] = None

class RoadServiceCreate(RoadServiceBase):
    pass

class RoadServiceUpdate(BaseModel):
    status: Optional[str] = None
    serviceProvider: Optional[str] = None
    providerPhone: Optional[str] = None
    estimatedArrival: Optional[datetime] = None
    estimatedCost: Optional[float] = None
    actualCost: Optional[float] = None
    notes: Optional[str] = None

class RoadServiceResponse(RoadServiceBase):
    id: str
    companyId: str
    status: str
    requestedAt: datetime
    dispatchedAt: Optional[datetime] = None
    arrivedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    actualCost: Optional[float] = None
    photos: Optional[dict] = None
    documents: Optional[dict] = None
    createdAt: datetime
    updatedAt: datetime
    createdBy: Optional[str] = None
    isActive: bool

    class Config:
        from_attributes = True

# Compliance Pydantic Models
class ELDComplianceBase(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    driverId: str
    equipmentId: str
    date: date
    totalDrivingTime: Optional[int] = None
    totalOnDutyTime: Optional[int] = None
    totalOffDutyTime: Optional[int] = None
    totalSleeperTime: Optional[int] = None
    hasViolations: Optional[bool] = False
    violations: Optional[dict] = None
    violationTypes: Optional[list] = None
    isCompliant: Optional[bool] = True
    complianceScore: Optional[int] = None
    auditStatus: Optional[str] = "pending"
    aiAuditResults: Optional[dict] = None
    aiRecommendations: Optional[str] = None
    aiConfidence: Optional[float] = None

class ELDComplianceCreate(ELDComplianceBase):
    pass

class ELDComplianceUpdate(BaseModel):
    totalDrivingTime: Optional[int] = None
    totalOnDutyTime: Optional[int] = None
    totalOffDutyTime: Optional[int] = None
    totalSleeperTime: Optional[int] = None
    hasViolations: Optional[bool] = None
    violations: Optional[dict] = None
    violationTypes: Optional[list] = None
    isCompliant: Optional[bool] = None
    complianceScore: Optional[int] = None
    auditStatus: Optional[str] = None
    aiAuditResults: Optional[dict] = None
    aiRecommendations: Optional[str] = None
    aiConfidence: Optional[float] = None

class ELDComplianceResponse(ELDComplianceBase):
    id: str
    companyId: str
    exportedAt: Optional[datetime] = None
    exportFormat: Optional[str] = None
    exportUrl: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
    isActive: bool

    class Config:
        from_attributes = True

class SAFERDataBase(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    dotNumber: str
    legalName: str
    dbaName: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipCode: Optional[str] = None
    country: Optional[str] = "US"
    safetyRating: Optional[str] = None
    safetyRatingDate: Optional[date] = None
    previousSafetyRating: Optional[str] = None
    totalInspections: Optional[int] = 0
    totalInspectionsWithViolations: Optional[int] = 0
    totalViolations: Optional[int] = 0
    totalOutOfServiceViolations: Optional[int] = 0
    totalOutOfServiceViolationsPercentage: Optional[float] = None
    totalCrashes: Optional[int] = 0
    fatalCrashes: Optional[int] = 0
    injuryCrashes: Optional[int] = 0
    towAwayCrashes: Optional[int] = 0
    totalVehicles: Optional[int] = 0
    totalDrivers: Optional[int] = 0

class SAFERDataCreate(SAFERDataBase):
    pass

class SAFERDataUpdate(BaseModel):
    safetyRating: Optional[str] = None
    safetyRatingDate: Optional[date] = None
    totalInspections: Optional[int] = None
    totalInspectionsWithViolations: Optional[int] = None
    totalViolations: Optional[int] = None
    totalOutOfServiceViolations: Optional[int] = None
    totalOutOfServiceViolationsPercentage: Optional[float] = None
    totalCrashes: Optional[int] = None
    fatalCrashes: Optional[int] = None
    injuryCrashes: Optional[int] = None
    towAwayCrashes: Optional[int] = None
    totalVehicles: Optional[int] = None
    totalDrivers: Optional[int] = None
    lastReportGenerated: Optional[datetime] = None
    reportUrl: Optional[str] = None
    portalUrl: Optional[str] = None

class SAFERDataResponse(SAFERDataBase):
    id: str
    companyId: str
    lastReportGenerated: Optional[datetime] = None
    reportUrl: Optional[str] = None
    portalUrl: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
    isActive: bool

    class Config:
        from_attributes = True

class InsurancePolicyBase(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    policyNumber: str
    policyType: str  # auto_liability, cargo, general_liability, workers_comp
    insuranceProvider: str
    agentName: Optional[str] = None
    agentPhone: Optional[str] = None
    agentEmail: Optional[str] = None
    coverageAmount: float
    deductible: Optional[float] = None
    premium: float
    paymentFrequency: Optional[str] = None  # monthly, quarterly, annually
    effectiveDate: date
    expirationDate: date
    renewalDate: Optional[date] = None
    status: Optional[str] = "active"
    isRenewed: Optional[bool] = False
    policyDocument: Optional[str] = None
    certificateOfInsurance: Optional[str] = None
    notes: Optional[str] = None

class InsurancePolicyCreate(InsurancePolicyBase):
    pass

class InsurancePolicyUpdate(BaseModel):
    policyType: Optional[str] = None
    insuranceProvider: Optional[str] = None
    agentName: Optional[str] = None
    agentPhone: Optional[str] = None
    agentEmail: Optional[str] = None
    coverageAmount: Optional[float] = None
    deductible: Optional[float] = None
    premium: Optional[float] = None
    paymentFrequency: Optional[str] = None
    effectiveDate: Optional[date] = None
    expirationDate: Optional[date] = None
    renewalDate: Optional[date] = None
    status: Optional[str] = None
    isRenewed: Optional[bool] = None
    policyDocument: Optional[str] = None
    certificateOfInsurance: Optional[str] = None
    notes: Optional[str] = None

class InsurancePolicyResponse(InsurancePolicyBase):
    id: str
    companyId: str
    createdAt: datetime
    updatedAt: datetime
    createdBy: Optional[str] = None
    isActive: bool

    class Config:
        from_attributes = True

class PermitBookBase(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    permitNumber: str
    permitType: str  # oversize, overweight, hazmat, special
    issuingAuthority: str
    state: str
    description: Optional[str] = None
    route: Optional[str] = None
    restrictions: Optional[str] = None
    specialConditions: Optional[str] = None
    issueDate: date
    expirationDate: date
    renewalDate: Optional[date] = None
    permitFee: Optional[float] = None
    processingFee: Optional[float] = None
    totalFee: Optional[float] = None
    status: Optional[str] = "active"
    isRenewed: Optional[bool] = False
    permitDocument: Optional[str] = None
    applicationDocument: Optional[str] = None
    notes: Optional[str] = None
    equipmentId: Optional[str] = None

class PermitBookCreate(PermitBookBase):
    pass

class PermitBookUpdate(BaseModel):
    permitType: Optional[str] = None
    issuingAuthority: Optional[str] = None
    state: Optional[str] = None
    description: Optional[str] = None
    route: Optional[str] = None
    restrictions: Optional[str] = None
    specialConditions: Optional[str] = None
    issueDate: Optional[date] = None
    expirationDate: Optional[date] = None
    renewalDate: Optional[date] = None
    permitFee: Optional[float] = None
    processingFee: Optional[float] = None
    totalFee: Optional[float] = None
    status: Optional[str] = None
    isRenewed: Optional[bool] = None
    permitDocument: Optional[str] = None
    applicationDocument: Optional[str] = None
    notes: Optional[str] = None
    equipmentId: Optional[str] = None

class PermitBookResponse(PermitBookBase):
    id: str
    companyId: str
    createdAt: datetime
    updatedAt: datetime
    createdBy: Optional[str] = None
    isActive: bool

    class Config:
        from_attributes = True

class DriverHOSLogBase(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    driverId: str
    equipmentId: str
    logDate: date
    drivingTime: Optional[int] = 0
    onDutyTime: Optional[int] = 0
    offDutyTime: Optional[int] = 0
    sleeperTime: Optional[int] = 0
    hasRequiredBreaks: Optional[bool] = True
    breakViolations: Optional[dict] = None
    elevenHourCompliant: Optional[bool] = True
    elevenHourViolations: Optional[dict] = None
    fourteenHourCompliant: Optional[bool] = True
    fourteenHourViolations: Optional[dict] = None
    seventyHourCompliant: Optional[bool] = True
    seventyHourViolations: Optional[dict] = None
    thirtyFourHourCompliant: Optional[bool] = True
    thirtyFourHourViolations: Optional[dict] = None
    eldDeviceId: Optional[str] = None
    eldProvider: Optional[str] = None
    dataTransferStatus: Optional[str] = None
    isCompliant: Optional[bool] = True
    violations: Optional[dict] = None
    violationCount: Optional[int] = 0
    notes: Optional[str] = None

class DriverHOSLogCreate(DriverHOSLogBase):
    pass

class DriverHOSLogUpdate(BaseModel):
    drivingTime: Optional[int] = None
    onDutyTime: Optional[int] = None
    offDutyTime: Optional[int] = None
    sleeperTime: Optional[int] = None
    hasRequiredBreaks: Optional[bool] = None
    breakViolations: Optional[dict] = None
    elevenHourCompliant: Optional[bool] = None
    elevenHourViolations: Optional[dict] = None
    fourteenHourCompliant: Optional[bool] = None
    fourteenHourViolations: Optional[dict] = None
    seventyHourCompliant: Optional[bool] = None
    seventyHourViolations: Optional[dict] = None
    thirtyFourHourCompliant: Optional[bool] = None
    thirtyFourHourViolations: Optional[dict] = None
    eldDeviceId: Optional[str] = None
    eldProvider: Optional[str] = None
    dataTransferStatus: Optional[str] = None
    isCompliant: Optional[bool] = None
    violations: Optional[dict] = None
    violationCount: Optional[int] = None
    notes: Optional[str] = None

class DriverHOSLogResponse(DriverHOSLogBase):
    id: str
    companyId: str
    createdAt: datetime
    updatedAt: datetime
    isActive: bool

    class Config:
        from_attributes = True
