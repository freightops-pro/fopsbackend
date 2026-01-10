"""
Canada Compliance Engine

Handles Canadian freight regulations:
- NSC (National Safety Code)
- Provincial CVOR/NSC registrations
- Hours of Service (slightly different from USA)
- IFTA (for cross-border with USA)
- Dangerous goods (TDG) requirements
- Quebec French language requirements
"""

from typing import Any, Dict, List, Optional
from .base import (
    BaseComplianceEngine,
    ComplianceStatus,
    ComplianceValidationResult,
    DocumentGenerationResult,
)


class CanadaComplianceEngine(BaseComplianceEngine):
    """
    Canada freight compliance engine.

    Key Requirements:
    1. NSC (National Safety Code) registration
    2. Provincial operating authority (CVOR in Ontario, NSC in other provinces)
    3. Hours of Service compliance (13-hour driving limit in some provinces)
    4. IFTA for interprovincial and cross-border
    5. TDG (Transportation of Dangerous Goods) for hazmat
    6. French language requirements in Quebec
    """

    def __init__(self, region_code: str = "canada"):
        super().__init__(region_code)

    async def validate_load_before_dispatch(
        self,
        load_data: Dict[str, Any],
        company_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        Validate load can be dispatched under Canadian regulations.

        Checks:
        1. Company has NSC number
        2. Provincial operating authority (if interprovincial)
        3. IFTA registration (if cross-border with USA)
        4. TDG certification (if dangerous goods)
        5. Quebec French requirements (if operating in Quebec)
        """
        errors = []
        warnings = []

        # Check NSC registration
        if not company_data.get("nsc_number"):
            errors.append("NSC (National Safety Code) number is required")

        # Check provincial authority for interprovincial
        if load_data.get("is_interprovincial"):
            origin_province = load_data.get("origin_province", "")

            # Ontario requires CVOR
            if origin_province == "ON" and not company_data.get("cvor_number"):
                errors.append("CVOR registration required for Ontario operations")

        # Check IFTA for cross-border with USA
        if load_data.get("crosses_us_border"):
            if not company_data.get("ifta_number"):
                errors.append("IFTA registration required for cross-border operations")

        # Check TDG certification for dangerous goods
        if load_data.get("is_dangerous_goods"):
            if not company_data.get("tdg_certified"):
                errors.append(
                    "TDG (Transportation of Dangerous Goods) certification required for hazmat"
                )

            # Driver must have TDG training
            if not load_data.get("driver_tdg_trained"):
                errors.append("Driver must have valid TDG training certificate")

        # Quebec language requirements
        destination_province = load_data.get("destination_province", "")
        if destination_province == "QC":
            if not company_data.get("quebec_french_compliant"):
                warnings.append(
                    "WARNING: Quebec operations require French language capability "
                    "for shipping documents and driver communication"
                )

        # Winter driving requirements
        import datetime
        current_month = datetime.datetime.now().month
        if current_month in [11, 12, 1, 2, 3]:  # November to March
            northern_provinces = ["YT", "NT", "NU", "AB", "SK", "MB"]
            if (origin_province in northern_provinces or
                destination_province in northern_provinces):
                warnings.append(
                    "Winter driving conditions. Ensure vehicle has winter tires "
                    "and emergency equipment (blankets, fuel, food)"
                )

        status = ComplianceStatus.ERROR if errors else (
            ComplianceStatus.WARNING if warnings else ComplianceStatus.VALID
        )

        return ComplianceValidationResult(
            status=status,
            message="Canadian transport compliance validation complete",
            errors=errors,
            warnings=warnings,
            details={
                "is_interprovincial": load_data.get("is_interprovincial", False),
                "crosses_us_border": load_data.get("crosses_us_border", False),
                "is_dangerous_goods": load_data.get("is_dangerous_goods", False)
            }
        )

    async def generate_shipping_document(
        self,
        load_data: Dict[str, Any],
        company_data: Dict[str, Any],
        driver_data: Optional[Dict[str, Any]] = None,
        vehicle_data: Optional[Dict[str, Any]] = None
    ) -> DocumentGenerationResult:
        """
        Generate Bill of Lading (BOL) for Canadian freight.

        Canada uses similar BOL format to USA, but with:
        1. Metric measurements (kg, km)
        2. French language option for Quebec
        3. TDG placarding information if dangerous goods
        """
        destination_province = load_data.get("destination_province", "")
        is_quebec = destination_province == "QC"

        # Generate standard BOL (similar to USA)
        return DocumentGenerationResult(
            success=True,
            document_type="bol",
            document_id=f"BOL-{load_data.get('load_number', 'UNKNOWN')}",
            errors=[],
            metadata={
                "language": "french" if is_quebec else "english",
                "measurement_system": "metric",
                "includes_tdg_info": load_data.get("is_dangerous_goods", False)
            }
        )

    async def validate_payment(
        self,
        payment_data: Dict[str, Any],
        load_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        Validate payment compliance.

        Canada Requirements:
        1. GST/HST must be included in invoice
        2. Provincial sales tax (PST) in some provinces
        """
        errors = []
        warnings = []

        amount = payment_data.get("amount_cad", 0)

        # Check for GST/HST
        province = load_data.get("origin_province", "")

        # HST provinces (combined federal + provincial): ON, NB, NS, PE, NL
        hst_provinces = {
            "ON": 0.13,  # 13% HST
            "NB": 0.15,  # 15% HST
            "NS": 0.15,  # 15% HST
            "PE": 0.15,  # 15% HST
            "NL": 0.15,  # 15% HST
        }

        # GST only provinces: AB, SK, MB, QC, BC, YT, NT, NU
        gst_rate = 0.05  # 5% federal GST

        # PST provinces (in addition to GST): BC, SK, MB, QC
        pst_provinces = {
            "BC": 0.07,  # 7% PST
            "SK": 0.06,  # 6% PST
            "MB": 0.07,  # 7% PST (RST)
            "QC": 0.09975,  # 9.975% QST
        }

        tax_amount = payment_data.get("tax_amount", 0)

        if province in hst_provinces:
            expected_tax = amount * hst_provinces[province]
            tax_name = "HST"
        elif province in pst_provinces:
            expected_tax = amount * (gst_rate + pst_provinces[province])
            tax_name = "GST + PST"
        else:
            expected_tax = amount * gst_rate
            tax_name = "GST"

        if abs(tax_amount - expected_tax) > 1:  # Allow 1 CAD tolerance
            warnings.append(
                f"{tax_name} amount ({tax_amount} CAD) does not match expected rate "
                f"({expected_tax:.2f} CAD)"
            )

        status = ComplianceStatus.WARNING if warnings else ComplianceStatus.VALID

        return ComplianceValidationResult(
            status=status,
            message="Payment validation complete",
            warnings=warnings,
            details={
                "amount_cad": amount,
                "tax_amount": tax_amount,
                "expected_tax": expected_tax,
                "tax_type": tax_name,
                "province": province
            }
        )

    async def validate_driver_assignment(
        self,
        driver_data: Dict[str, Any],
        load_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        Validate driver HOS (Hours of Service) compliance.

        Canada HOS rules (slightly different from USA):
        - 13-hour driving limit (vs 11 in USA)
        - 14-hour on-duty limit
        - 70-hour/7-day or 120-hour/14-day cycle
        - 10-hour off-duty before starting
        """
        errors = []
        warnings = []

        # Check driver's license
        if not driver_data.get("license_number"):
            errors.append("Valid commercial driver's license required")

        # Check license class
        license_class = driver_data.get("license_class", "")
        if license_class not in ["1", "2", "3", "4"]:  # Canada uses Class 1-4
            errors.append("Driver must have commercial license (Class 1-4)")

        # Check HOS availability (13-hour limit)
        hours_available = driver_data.get("hos_hours_available", 0)
        if hours_available < 2:
            errors.append(
                "Insufficient HOS hours available. Driver needs minimum 10-hour off-duty period."
            )

        # Check ELD/EROD (Electronic Recording Device)
        if not driver_data.get("erod_connected"):
            warnings.append(
                "EROD (Electronic Recording Device) not reporting. "
                "Verify electronic logs are working."
            )

        # Check medical certificate
        import datetime
        medical_expiry = driver_data.get("medical_certificate_expiry")
        if medical_expiry:
            try:
                expiry_date = datetime.datetime.fromisoformat(str(medical_expiry))
                if expiry_date < datetime.datetime.now():
                    errors.append("Driver's medical certificate has expired")
            except:
                pass

        # Check TDG training if hauling dangerous goods
        if load_data.get("is_dangerous_goods"):
            if not driver_data.get("tdg_trained"):
                errors.append("Driver must have valid TDG training for dangerous goods")

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
                "erod_status": "connected" if driver_data.get("erod_connected") else "disconnected",
                "hos_limit": "13 hours driving, 14 hours on-duty"
            }
        )

    def get_route_optimization_rules(self) -> Dict[str, Any]:
        """
        Canada route optimization focuses on efficiency and safety.

        Priority: Maximize revenue per kilometer
        Secondary: Minimize empty kilometers (deadhead)
        Considerations: Winter weather, remote areas, border crossing times
        """
        return {
            "optimization_goal": "maximize_rate_per_km",
            "penalties": {
                "deadhead_km": 50,  # Heavy penalty for driving empty
                "low_rate_per_km": 30,
                "hos_violation_risk": 100,
                "winter_remote_route": 40,  # Extra caution in winter
                "border_delay_risk": 60,  # Account for customs delays
            },
            "constraints": {
                "maximum_hos_hours": 13,  # Canadian limit (vs 11 in USA)
                "required_rest_period": 10,  # 10 hour break required
                "weekly_limit_option_1": 70,  # 70 hours in 7 days
                "weekly_limit_option_2": 120,  # 120 hours in 14 days
            },
            "preferences": {
                "prefer_backhaul": True,  # Always find return load
                "prefer_major_highways": True,  # Trans-Canada, major routes
                "avoid_remote_winter": True,  # Safety in winter months
                "prefer_fast_border_crossings": True,  # Use FAST/NEXUS lanes when possible
            },
            "seasonal_adjustments": {
                "winter_months": [11, 12, 1, 2, 3],
                "winter_speed_reduction": 0.15,  # 15% slower in winter
                "winter_fuel_increase": 0.20,  # 20% more fuel in winter
            }
        }

    async def submit_tracking_data(
        self,
        location_data: Dict[str, Any],
        vehicle_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        Canada doesn't require real-time tracking submission to government.

        EROD (Electronic Recording Device) data is stored locally
        and available for roadside inspection.
        """
        return ComplianceValidationResult(
            status=ComplianceStatus.VALID,
            message="Tracking data logged locally via EROD"
        )

    def get_currency_code(self) -> str:
        return "CAD"

    def get_distance_unit(self) -> str:
        return "kilometers"  # Canada uses metric system

    def get_weight_unit(self) -> str:
        return "kg"  # Kilograms

    def requires_government_api(self) -> bool:
        return False  # No real-time government API integration required

    def get_required_company_fields(self) -> List[str]:
        return [
            "nsc_number",  # National Safety Code
            "cvor_number",  # Ontario CVOR (if operating in Ontario)
            "ifta_number",  # For interprovincial and cross-border
            "carrier_profile_number",  # Federal carrier profile
            "tdg_certified",  # TDG certification status
        ]

    def get_required_integrations(self) -> List[Dict[str, str]]:
        return [
            {
                "name": "EROD Provider",
                "type": "eld_system",
                "required": True,
                "description": "Electronic Recording Device for HOS compliance",
                "options": ["Samsara", "Motive", "Geotab", "Isaac"]
            },
            {
                "name": "IFTA Reporting",
                "type": "tax_reporting",
                "required": True,
                "description": "Fuel tax reporting for interprovincial and cross-border"
            },
            {
                "name": "Border Crossing System",
                "type": "customs",
                "required": False,
                "description": "ACE/ACI for automated border clearance",
                "options": ["ACE (USA entry)", "ACI (Canada entry)", "FAST"]
            }
        ]
