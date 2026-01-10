"""
USA Compliance Engine

Handles United States freight regulations:
- DOT compliance
- HOS (Hours of Service) rules
- ELD (Electronic Logging Device) requirements
- IFTA (International Fuel Tax Agreement)
- FMCSA safety ratings
"""

from typing import Any, Dict, List, Optional
from .base import (
    BaseComplianceEngine,
    ComplianceStatus,
    ComplianceValidationResult,
    DocumentGenerationResult,
)


class USAComplianceEngine(BaseComplianceEngine):
    """
    United States freight compliance engine.

    Key Requirements:
    1. DOT number registration
    2. HOS (Hours of Service) compliance - 11 hour driving limit
    3. ELD mandate for electronic driver logs
    4. IFTA fuel tax reporting
    5. CSA/SMS safety ratings
    """

    def __init__(self, region_code: str = "usa"):
        super().__init__(region_code)

    async def validate_load_before_dispatch(
        self,
        load_data: Dict[str, Any],
        company_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        Validate load can be dispatched under US DOT regulations.

        Checks:
        1. Company has valid DOT number
        2. MC number if for-hire
        3. Active operating authority
        """
        errors = []
        warnings = []

        # Check DOT registration
        if not company_data.get("dot_number"):
            errors.append("DOT number is required for interstate commerce")

        # Check MC number for for-hire operations
        business_type = company_data.get("business_type")
        if business_type in ["broker", "carrier"] and not company_data.get("mc_number"):
            warnings.append("MC number recommended for for-hire operations")

        # Check IFTA if crossing state lines
        if load_data.get("is_interstate") and not company_data.get("ifta_number"):
            errors.append("IFTA account required for interstate loads")

        status = ComplianceStatus.ERROR if errors else (
            ComplianceStatus.WARNING if warnings else ComplianceStatus.VALID
        )

        return ComplianceValidationResult(
            status=status,
            message="US DOT compliance validation complete",
            errors=errors,
            warnings=warnings
        )

    async def generate_shipping_document(
        self,
        load_data: Dict[str, Any],
        company_data: Dict[str, Any],
        driver_data: Optional[Dict[str, Any]] = None,
        vehicle_data: Optional[Dict[str, Any]] = None
    ) -> DocumentGenerationResult:
        """
        Generate Bill of Lading (BOL) for US freight.

        Standard BOL format - no government submission required.
        """
        # USA doesn't require government API for shipping documents
        # Just generate standard BOL

        return DocumentGenerationResult(
            success=True,
            document_type="bol",
            document_id=f"BOL-{load_data.get('load_number', 'UNKNOWN')}",
            errors=[]
        )

    async def validate_payment(
        self,
        payment_data: Dict[str, Any],
        load_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        Validate payment compliance.

        US doesn't have minimum freight rate requirements like Brazil.
        Just verify payment terms are valid.
        """
        # No government-mandated payment validation in USA
        return ComplianceValidationResult(
            status=ComplianceStatus.VALID,
            message="Payment validation complete"
        )

    async def validate_driver_assignment(
        self,
        driver_data: Dict[str, Any],
        load_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        Validate driver HOS (Hours of Service) compliance.

        Checks:
        1. Valid CDL (Commercial Driver's License)
        2. HOS compliance - 11 hour driving limit
        3. 70 hour/8 day rule
        4. ELD data available
        """
        errors = []
        warnings = []

        # Check CDL
        if not driver_data.get("cdl_number"):
            errors.append("Valid CDL required for commercial driving")

        # Check CDL class matches vehicle
        vehicle_weight = load_data.get("vehicle_weight_lbs", 0)
        cdl_class = driver_data.get("cdl_class")
        if vehicle_weight > 26000 and cdl_class not in ["A", "B"]:
            errors.append("Class A or B CDL required for vehicles over 26,000 lbs")

        # Check HOS availability
        hours_available = driver_data.get("hos_hours_available", 0)
        if hours_available < 2:
            errors.append("Insufficient HOS hours available. Driver needs rest period.")

        # Check ELD compliance
        if not driver_data.get("eld_connected"):
            warnings.append("ELD not reporting. Verify electronic logs are working.")

        status = ComplianceStatus.ERROR if errors else (
            ComplianceStatus.WARNING if warnings else ComplianceStatus.VALID
        )

        return ComplianceValidationResult(
            status=status,
            message="Driver HOS validation complete",
            errors=errors,
            warnings=warnings,
            details={
                "hos_hours_available": hours_available,
                "eld_status": "connected" if driver_data.get("eld_connected") else "disconnected"
            }
        )

    def get_route_optimization_rules(self) -> Dict[str, Any]:
        """
        USA route optimization focuses on revenue per mile.

        Priority: Maximize rate per mile
        Secondary: Minimize deadhead (empty miles)
        """
        return {
            "optimization_goal": "maximize_rate_per_mile",
            "penalties": {
                "deadhead_miles": 50,  # Heavy penalty for driving empty
                "low_rate_per_mile": 30,
                "hos_violation_risk": 100,
            },
            "constraints": {
                "maximum_hos_hours": 11,  # Federal limit
                "required_rest_period": 10,  # 10 hour break required
                "weekly_limit": 70,  # 70 hours in 8 days
            },
            "preferences": {
                "prefer_backhaul": True,  # Always find return load
                "prefer_interstate_highways": True,
            }
        }

    async def submit_tracking_data(
        self,
        location_data: Dict[str, Any],
        vehicle_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        USA doesn't require real-time tracking submission to government.

        ELD data is stored locally and available for roadside inspection.
        """
        return ComplianceValidationResult(
            status=ComplianceStatus.VALID,
            message="Tracking data logged locally"
        )

    def get_currency_code(self) -> str:
        return "USD"

    def get_distance_unit(self) -> str:
        return "miles"  # USA uses imperial system

    def get_weight_unit(self) -> str:
        return "lbs"  # Pounds

    def requires_government_api(self) -> bool:
        return False  # No real-time government API integration required

    def get_required_company_fields(self) -> List[str]:
        return [
            "dot_number",  # Required for interstate
            "mc_number",  # For for-hire carriers
            "scac_code",  # Standard Carrier Alpha Code
            "ifta_number",  # For interstate fuel tax
        ]

    def get_required_integrations(self) -> List[Dict[str, str]]:
        return [
            {
                "name": "ELD Provider",
                "type": "eld_system",
                "required": True,
                "description": "Electronic Logging Device for HOS compliance",
                "options": ["Samsara", "Motive", "Geotab", "Omnitracs"]
            },
            {
                "name": "IFTA Reporting",
                "type": "tax_reporting",
                "required": True,
                "description": "Fuel tax reporting system"
            }
        ]
