"""
Compliance API Endpoints

Regional compliance validation endpoints that route to appropriate compliance engines.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.company import Company
from app.services.compliance.registry import ComplianceEngineRegistry
from app.services.compliance.base import ComplianceStatus
from pydantic import BaseModel, Field


router = APIRouter()


# ========== Request/Response Models ==========

class LoadValidationRequest(BaseModel):
    """Request to validate a load before dispatch."""
    company_id: str
    load_data: Dict[str, Any] = Field(..., description="Load details (origin, destination, weight, etc.)")


class DocumentGenerationRequest(BaseModel):
    """Request to generate shipping document."""
    company_id: str
    load_data: Dict[str, Any]
    driver_data: Optional[Dict[str, Any]] = None
    vehicle_data: Optional[Dict[str, Any]] = None


class PaymentValidationRequest(BaseModel):
    """Request to validate payment compliance."""
    company_id: str
    payment_data: Dict[str, Any]
    load_data: Dict[str, Any]


class DriverValidationRequest(BaseModel):
    """Request to validate driver assignment."""
    company_id: str
    driver_data: Dict[str, Any]
    load_data: Dict[str, Any]


class ComplianceValidationResponse(BaseModel):
    """Response from compliance validation."""
    status: str
    message: str
    errors: List[str] = []
    warnings: List[str] = []
    details: Optional[Dict[str, Any]] = None


class DocumentGenerationResponse(BaseModel):
    """Response from document generation."""
    success: bool
    document_type: str
    document_id: str
    document_url: Optional[str] = None
    xml_content: Optional[str] = None
    errors: List[str] = []


class RegionInfo(BaseModel):
    """Information about a supported region."""
    code: str
    name: str
    description: str
    currency_code: str
    distance_unit: str
    weight_unit: str
    requires_government_api: bool
    complexity_level: int


class RegionRequirements(BaseModel):
    """Detailed requirements for a region."""
    region_code: str
    required_company_fields: List[str]
    required_integrations: List[Dict[str, str]]
    optimization_goal: str
    key_regulations: List[str]


# ========== Helper Functions ==========

async def get_company_with_region(
    company_id: str,
    db: AsyncSession
) -> tuple[Company, str, Dict[str, Any]]:
    """
    Get company and extract regional data.

    Returns:
        tuple: (company, region_code, regional_data)
    """
    from sqlalchemy import select

    result = await db.execute(
        select(Company).where(Company.id == company_id)
    )
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found"
        )

    region_code = company.operating_region or "usa"
    regional_data = company.regional_data or {}

    return company, region_code, regional_data


def build_company_data(company: Company, regional_data: Dict[str, Any]) -> Dict[str, Any]:
    """Build company data dict for compliance engine."""
    return {
        "company_id": company.id,
        "company_name": company.name,
        "operating_region": company.operating_region,
        "dot_number": company.dot_number,
        "mc_number": company.mc_number,
        "business_type": getattr(company, "business_type", None),
        **regional_data  # Merge in region-specific fields
    }


# ========== Endpoints ==========

@router.post("/validate-load", response_model=ComplianceValidationResponse)
async def validate_load_before_dispatch(
    request: LoadValidationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Validate a load can be dispatched under regional regulations.

    This endpoint:
    1. Looks up the company's operating region
    2. Loads the appropriate compliance engine
    3. Validates the load against regional requirements

    Examples:
    - USA: Checks DOT/MC/IFTA registration
    - Brazil: Validates CNPJ, RNTRC, checks for high-theft routes
    - Mexico: Validates RFC, SCT permit
    """
    # Get company and regional data
    company, region_code, regional_data = await get_company_with_region(
        request.company_id, db
    )

    # Get compliance engine for region
    try:
        engine = ComplianceEngineRegistry.get_engine(region_code)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Build company data
    company_data = build_company_data(company, regional_data)

    # Validate load
    result = await engine.validate_load_before_dispatch(
        load_data=request.load_data,
        company_data=company_data
    )

    return ComplianceValidationResponse(
        status=result.status.value,
        message=result.message,
        errors=result.errors,
        warnings=result.warnings,
        details=result.details
    )


@router.post("/generate-document", response_model=DocumentGenerationResponse)
async def generate_shipping_document(
    request: DocumentGenerationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate region-specific shipping document.

    Examples:
    - USA: Bill of Lading (BOL)
    - Brazil: MDF-e XML with digital signature
    - Mexico: Carta de Porte with SAT seal
    - EU: e-CMR with QR code
    - India: e-Way Bill via NIC API
    """
    # Get company and regional data
    company, region_code, regional_data = await get_company_with_region(
        request.company_id, db
    )

    # Get compliance engine
    try:
        engine = ComplianceEngineRegistry.get_engine(region_code)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Build company data
    company_data = build_company_data(company, regional_data)

    # Generate document
    result = await engine.generate_shipping_document(
        load_data=request.load_data,
        company_data=company_data,
        driver_data=request.driver_data,
        vehicle_data=request.vehicle_data
    )

    return DocumentGenerationResponse(
        success=result.success,
        document_type=result.document_type,
        document_id=result.document_id,
        document_url=result.document_url,
        xml_content=result.xml_content,
        errors=result.errors
    )


@router.post("/validate-payment", response_model=ComplianceValidationResponse)
async def validate_payment_compliance(
    request: PaymentValidationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Validate payment meets regional requirements.

    Examples:
    - USA: No government requirements (just validates payment terms)
    - Brazil: Requires CIOT code from approved provider, validates minimum rate
    - Mexico: Validates VAT compliance
    """
    # Get company and regional data
    company, region_code, regional_data = await get_company_with_region(
        request.company_id, db
    )

    # Get compliance engine
    try:
        engine = ComplianceEngineRegistry.get_engine(region_code)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Build company data
    company_data = build_company_data(company, regional_data)

    # Validate payment
    result = await engine.validate_payment(
        payment_data=request.payment_data,
        load_data=request.load_data
    )

    return ComplianceValidationResponse(
        status=result.status.value,
        message=result.message,
        errors=result.errors,
        warnings=result.warnings,
        details=result.details
    )


@router.post("/validate-driver", response_model=ComplianceValidationResponse)
async def validate_driver_assignment(
    request: DriverValidationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Validate driver can be assigned to load under regional rules.

    Examples:
    - USA: HOS (11-hour limit), CDL validation, ELD requirement
    - Brazil: CNH validation, checks if driver has security clearance for route
    - EU: Mobility Package (return-to-home), digital tachograph
    - Japan: 960 hour/year overtime limit check
    """
    # Get company and regional data
    company, region_code, regional_data = await get_company_with_region(
        request.company_id, db
    )

    # Get compliance engine
    try:
        engine = ComplianceEngineRegistry.get_engine(region_code)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Build company data
    company_data = build_company_data(company, regional_data)

    # Validate driver
    result = await engine.validate_driver_assignment(
        driver_data=request.driver_data,
        load_data=request.load_data
    )

    return ComplianceValidationResponse(
        status=result.status.value,
        message=result.message,
        errors=result.errors,
        warnings=result.warnings,
        details=result.details
    )


@router.get("/regions", response_model=List[RegionInfo])
async def list_supported_regions():
    """
    List all supported regions with their basic configuration.

    Returns metadata about each region including:
    - Currency code
    - Unit system (metric vs imperial)
    - Whether government API integration is required
    - Complexity level (1-5 stars)
    """
    regions = ComplianceEngineRegistry.get_all_regions()

    result = []
    for region_code in regions:
        engine = ComplianceEngineRegistry.get_engine(region_code)

        # Map region codes to friendly names
        region_names = {
            "usa": "United States",
            "brazil": "Brazil",
            "mexico": "Mexico",
            "eu": "European Union",
            "india": "India",
            "china": "China",
            "japan": "Japan",
        }

        region_descriptions = {
            "usa": "HOS compliance, ELD mandate, IFTA reporting",
            "brazil": "MDF-e/CT-e, SEFAZ integration, CIOT payment validation",
            "mexico": "Carta de Porte 3.0, SAT digital sealing",
            "eu": "Mobility Package, Cabotage (3-in-7 rule), e-CMR, Posted Workers",
            "india": "e-Way Bill, GST compliance, NIC API integration",
            "china": "Beidou positioning, WeChat integration, National Freight Platform",
            "japan": "Relay trucking, 960 hour/year limit, Zenrin navigation",
        }

        result.append(RegionInfo(
            code=region_code,
            name=region_names.get(region_code, region_code.upper()),
            description=region_descriptions.get(region_code, ""),
            currency_code=engine.get_currency_code(),
            distance_unit=engine.get_distance_unit(),
            weight_unit=engine.get_weight_unit(),
            requires_government_api=engine.requires_government_api(),
            complexity_level=engine.get_complexity_level()
        ))

    return result


@router.get("/regions/{region_code}", response_model=RegionInfo)
async def get_region_info(region_code: str):
    """Get detailed information about a specific region."""
    try:
        engine = ComplianceEngineRegistry.get_engine(region_code)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region '{region_code}' not supported"
        )

    # Use same mapping as list endpoint
    region_names = {
        "usa": "United States",
        "brazil": "Brazil",
        "mexico": "Mexico",
        "eu": "European Union",
        "india": "India",
        "china": "China",
        "japan": "Japan",
    }

    region_descriptions = {
        "usa": "HOS compliance, ELD mandate, IFTA reporting",
        "brazil": "MDF-e/CT-e, SEFAZ integration, CIOT payment validation",
        "mexico": "Carta de Porte 3.0, SAT digital sealing",
        "eu": "Mobility Package, Cabotage (3-in-7 rule), e-CMR, Posted Workers",
        "india": "e-Way Bill, GST compliance, NIC API integration",
        "china": "Beidou positioning, WeChat integration, National Freight Platform",
        "japan": "Relay trucking, 960 hour/year limit, Zenrin navigation",
    }

    return RegionInfo(
        code=region_code,
        name=region_names.get(region_code, region_code.upper()),
        description=region_descriptions.get(region_code, ""),
        currency_code=engine.get_currency_code(),
        distance_unit=engine.get_distance_unit(),
        weight_unit=engine.get_weight_unit(),
        requires_government_api=engine.requires_government_api(),
        complexity_level=engine.get_complexity_level()
    )


@router.get("/regions/{region_code}/requirements", response_model=RegionRequirements)
async def get_region_requirements(region_code: str):
    """
    Get detailed compliance requirements for a region.

    Returns:
    - Required company registration fields
    - Required integrations (ELD, payment providers, government APIs)
    - Route optimization goal
    - Key regulations
    """
    try:
        engine = ComplianceEngineRegistry.get_engine(region_code)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region '{region_code}' not supported"
        )

    # Get route optimization rules
    route_rules = engine.get_route_optimization_rules()

    # Build key regulations list
    key_regulations_map = {
        "usa": [
            "DOT/MC registration required",
            "HOS: 11-hour driving limit, 70 hours in 8 days",
            "ELD mandate for electronic driver logs",
            "IFTA fuel tax reporting for interstate",
        ],
        "brazil": [
            "CNPJ (corporate tax ID) required",
            "RNTRC (road cargo transporter registry) required",
            "MDF-e electronic manifest submitted to SEFAZ before trip",
            "CIOT payment code from approved provider mandatory",
            "ANTT minimum freight rate validation",
        ],
        "mexico": [
            "RFC (tax ID) required",
            "SCT transport permit required",
            "Carta de Porte 3.0 digital waybill with SAT seal",
            "GPS jammer detection for security",
        ],
        "eu": [
            "Mobility Package: Max 4 weeks away from home base",
            "Cabotage: Track internal moves per country",
            "e-CMR digital consignment note",
            "CO2 emissions reporting per GLEC Framework",
            "Digital tachograph for driver hours",
        ],
        "india": [
            "PAN number required",
            "GST registration required",
            "e-Way Bill via NIC API for loads >₹50,000",
            "Part A & Part B forms (invoice + vehicle details)",
        ],
        "china": [
            "Business license required",
            "Beidou satellite positioning (not GPS)",
            "WeChat Mini-Program for driver interface",
            "National Freight Platform mandatory position reporting",
        ],
        "japan": [
            "Operating license required",
            "960 hour/year overtime limit per driver",
            "Relay trucking: 8-hour shift maximum",
            "Zenrin maps for narrow street routing",
        ],
    }

    return RegionRequirements(
        region_code=region_code,
        required_company_fields=engine.get_required_company_fields(),
        required_integrations=engine.get_required_integrations(),
        optimization_goal=route_rules.get("optimization_goal", "unknown"),
        key_regulations=key_regulations_map.get(region_code, [])
    )


@router.get("/regions/{region_code}/optimization-rules")
async def get_route_optimization_rules(region_code: str):
    """
    Get AI route optimization rules for a region.

    Different regions optimize for different goals:
    - USA: Maximize rate per mile, minimize deadhead
    - Brazil: Maximize security, avoid red zones at night
    - EU: Minimize empty return, respect return-to-home rules
    - Japan: Minimize driver overtime
    """
    try:
        engine = ComplianceEngineRegistry.get_engine(region_code)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Region '{region_code}' not supported"
        )

    return engine.get_route_optimization_rules()
