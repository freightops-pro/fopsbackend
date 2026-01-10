"""
EU (European Union) Compliance Engine

Handles freight compliance for EU member states including:
- e-CMR (Electronic Consignment Note) - Digital alternative to paper CMR
- Mobility Package I (2020) - Driver posting, return home, cabotage rules
- Cabotage Restrictions - Limited domestic operations in foreign countries
- Posted Workers Directive - Driver accommodation and pay requirements
- Digital Tachograph - Driver hours and rest period tracking
- Cross-border operations - Multiple jurisdiction handling

Key EU Freight Regulations:
- Regulation (EC) No 1072/2009 - Road transport market access
- Regulation (EU) 2020/1054 - Mobility Package I
- Regulation (EU) 2020/1055 - Posted workers in road transport
- Convention on the Contract for the International Carriage of Goods by Road (CMR)

Complexity: High (8/10)
- Multi-country operations with varying national rules
- Complex cabotage tracking (3 operations in 7 days rule)
- Driver posting requirements after 3 days in country
- Mandatory return-to-base every 4 weeks
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.compliance.base import (
    BaseComplianceEngine,
    ComplianceStatus,
    ComplianceValidationResult,
    DocumentGenerationResult,
)


class EUComplianceEngine(BaseComplianceEngine):
    """
    EU compliance engine for cross-border freight operations in European Union
    """

    def __init__(self, region_code: str = "eu"):
        super().__init__(region_code)

    # EU Member States (as of 2024)
    EU_MEMBER_STATES = {
        "AT": "Austria",
        "BE": "Belgium",
        "BG": "Bulgaria",
        "HR": "Croatia",
        "CY": "Cyprus",
        "CZ": "Czech Republic",
        "DK": "Denmark",
        "EE": "Estonia",
        "FI": "Finland",
        "FR": "France",
        "DE": "Germany",
        "GR": "Greece",
        "HU": "Hungary",
        "IE": "Ireland",
        "IT": "Italy",
        "LV": "Latvia",
        "LT": "Lithuania",
        "LU": "Luxembourg",
        "MT": "Malta",
        "NL": "Netherlands",
        "PL": "Poland",
        "PT": "Portugal",
        "RO": "Romania",
        "SK": "Slovakia",
        "SI": "Slovenia",
        "ES": "Spain",
        "SE": "Sweden",
    }

    # Countries where cabotage is highly restricted
    HIGH_CABOTAGE_ENFORCEMENT = ["FR", "DE", "IT", "ES", "PL"]

    async def validate_load_before_dispatch(
        self, load_data: Dict[str, Any], company_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        Validate load meets EU cross-border requirements before dispatch
        """
        errors = []
        warnings = []
        details = {}

        # 1. Company Registration Validation
        if not company_data.get("eu_license_number"):
            errors.append(
                "EU Community License required for international transport operations"
            )

        # 2. e-CMR Validation
        if not company_data.get("ecmr_enabled"):
            warnings.append(
                "e-CMR not enabled. Consider digital CMR for faster border crossings"
            )

        # 3. Cross-border Operation Validation
        origin_country = load_data.get("origin_country_code", "")
        destination_country = load_data.get("destination_country_code", "")

        if origin_country != destination_country:
            # International operation
            details["operation_type"] = "international"

            # Check if operation crosses EU external border
            if origin_country not in self.EU_MEMBER_STATES or destination_country not in self.EU_MEMBER_STATES:
                warnings.append(
                    "Operation crosses EU external border - additional customs documentation required"
                )
        else:
            # Cabotage operation (domestic in foreign country)
            carrier_country = company_data.get("country_code", "")
            if carrier_country != origin_country:
                details["operation_type"] = "cabotage"
                errors_from_cabotage = await self._validate_cabotage(
                    company_data, load_data, origin_country
                )
                errors.extend(errors_from_cabotage)

        # 4. Driver Assignment Validation
        driver_data = load_data.get("driver", {})
        if driver_data:
            driver_errors = await self._validate_driver_for_eu(
                driver_data, load_data, company_data
            )
            errors.extend(driver_errors)

        # 5. Dangerous Goods Validation
        if load_data.get("is_dangerous_goods"):
            if not driver_data.get("adr_certificate"):
                errors.append(
                    "Driver must have valid ADR certificate for dangerous goods transport"
                )
            if not load_data.get("adr_classification"):
                errors.append(
                    "Dangerous goods must have ADR classification (UN number)"
                )

        # 6. Temperature-Controlled Goods
        if load_data.get("requires_temperature_control"):
            if not load_data.get("atp_certificate"):
                errors.append(
                    "ATP certificate required for temperature-controlled transport"
                )

        # Determine status
        if errors:
            status = ComplianceStatus.ERROR
            message = f"Load validation failed with {len(errors)} error(s)"
        elif warnings:
            status = ComplianceStatus.WARNING
            message = f"Load validated with {len(warnings)} warning(s)"
        else:
            status = ComplianceStatus.VALID
            message = "Load meets all EU compliance requirements"

        return ComplianceValidationResult(
            status=status,
            message=message,
            errors=errors if errors else None,
            warnings=warnings if warnings else None,
            details=details,
        )

    async def _validate_cabotage(
        self, company_data: Dict[str, Any], load_data: Dict[str, Any], country_code: str
    ) -> List[str]:
        """
        Validate cabotage operation meets 3-in-7 rule

        Cabotage Rule (EU Regulation 1072/2009 amended by Mobility Package):
        - After international transport, carrier may perform max 3 cabotage operations
        - Within 7 days after unloading from international transport
        - Must leave country for 4 days before next cabotage
        """
        errors = []

        # Check recent cabotage operations in this country
        recent_cabotage = load_data.get("recent_cabotage_in_country", [])

        if len(recent_cabotage) >= 3:
            errors.append(
                f"Cabotage limit reached: Max 3 operations in 7 days in {country_code}"
            )

        # Check if 7-day window has passed since first cabotage
        if recent_cabotage:
            first_cabotage_date = recent_cabotage[0].get("date")
            if first_cabotage_date:
                days_since_first = (datetime.utcnow() - first_cabotage_date).days
                if days_since_first > 7:
                    errors.append(
                        "Cabotage window expired. Must perform international transport before more cabotage"
                    )

        # High enforcement countries - additional checks
        if country_code in self.HIGH_CABOTAGE_ENFORCEMENT:
            warnings.append(
                f"{self.EU_MEMBER_STATES[country_code]} has strict cabotage enforcement - ensure all documentation is in order"
            )

        return errors

    async def _validate_driver_for_eu(
        self, driver_data: Dict[str, Any], load_data: Dict[str, Any], company_data: Dict[str, Any]
    ) -> List[str]:
        """
        Validate driver meets EU requirements including Mobility Package
        """
        errors = []

        # 1. Digital Tachograph Check
        if not driver_data.get("tachograph_card_number"):
            errors.append("Driver must have valid digital tachograph card")

        # 2. Driver CPC (Certificate of Professional Competence)
        if not driver_data.get("cpc_valid_until"):
            errors.append("Driver must have valid CPC qualification")
        else:
            cpc_expiry = driver_data.get("cpc_valid_until")
            if isinstance(cpc_expiry, str):
                cpc_expiry = datetime.fromisoformat(cpc_expiry)
            if cpc_expiry < datetime.utcnow():
                errors.append("Driver CPC has expired")

        # 3. Mobility Package - Posted Worker Requirements
        carrier_country = company_data.get("country_code", "")
        operation_country = load_data.get("origin_country_code", "")

        if carrier_country != operation_country:
            # Driver operating in foreign country
            days_in_country = load_data.get("driver_days_in_country", 0)

            if days_in_country >= 3:
                # Posted worker rules apply after 3 days
                if not driver_data.get("posted_worker_declaration_submitted"):
                    errors.append(
                        "Posted Worker Declaration required after 3 days in foreign country"
                    )

                # Driver must have accommodation details
                if not load_data.get("driver_accommodation_address"):
                    errors.append(
                        "Driver accommodation address required (Mobility Package requirement)"
                    )

        # 4. Mobility Package - Return Home Requirement
        last_return_home = driver_data.get("last_return_to_base_date")
        if last_return_home:
            if isinstance(last_return_home, str):
                last_return_home = datetime.fromisoformat(last_return_home)

            days_since_return = (datetime.utcnow() - last_return_home).days

            if days_since_return >= 28:
                errors.append(
                    "Driver must return to base/home every 4 weeks (Mobility Package requirement)"
                )
            elif days_since_return >= 21:
                errors.append(
                    "WARNING: Driver approaching 4-week limit - plan return home soon"
                )

        # 5. Rest Period Validation
        hours_driven_today = driver_data.get("hours_driven_today", 0)
        if hours_driven_today >= 9:
            errors.append(
                "Driver has reached daily driving limit (9 hours, or 10 hours twice per week)"
            )

        return errors

    async def generate_shipping_document(
        self,
        load_data: Dict[str, Any],
        company_data: Dict[str, Any],
        db: AsyncSession,
    ) -> DocumentGenerationResult:
        """
        Generate e-CMR (Electronic Consignment Note) for EU transport
        """
        errors = []

        # Check if company has e-CMR enabled
        if not company_data.get("ecmr_enabled"):
            errors.append("e-CMR not enabled for this company")
            return DocumentGenerationResult(
                success=False,
                document_id=None,
                document_type="e-CMR",
                document_data=None,
                errors=errors,
            )

        # Build e-CMR document data
        ecmr_data = {
            "consignment_note_number": load_data.get("load_number"),
            "issue_date": datetime.utcnow().isoformat(),

            # Parties
            "sender": {
                "name": load_data.get("shipper_name"),
                "address": load_data.get("origin_address"),
                "country": load_data.get("origin_country_code"),
            },
            "carrier": {
                "name": company_data.get("company_name"),
                "license_number": company_data.get("eu_license_number"),
                "country": company_data.get("country_code"),
            },
            "consignee": {
                "name": load_data.get("consignee_name"),
                "address": load_data.get("destination_address"),
                "country": load_data.get("destination_country_code"),
            },

            # Goods description
            "goods": {
                "description": load_data.get("cargo_description"),
                "weight_kg": load_data.get("weight_kg"),
                "packages": load_data.get("package_count"),
                "dangerous_goods": load_data.get("is_dangerous_goods", False),
            },

            # Transport details
            "vehicle_registration": load_data.get("vehicle_registration"),
            "trailer_registration": load_data.get("trailer_registration"),
            "driver_name": load_data.get("driver", {}).get("name"),

            # Route
            "place_of_loading": load_data.get("origin_address"),
            "place_of_delivery": load_data.get("destination_address"),
            "loading_date": load_data.get("pickup_date"),

            # Instructions
            "special_instructions": load_data.get("special_instructions"),

            # Signatures (digital)
            "sender_signature": None,  # To be signed
            "carrier_signature": None,  # To be signed
            "consignee_signature": None,  # To be signed on delivery
        }

        # In production, this would integrate with e-CMR platform provider
        # (e.g., Transporeon, Timocom, or national e-CMR systems)

        return DocumentGenerationResult(
            success=True,
            document_id=f"ECMR-{load_data.get('load_number')}",
            document_type="e-CMR",
            document_data=ecmr_data,
            errors=None,
        )

    async def validate_driver_assignment(
        self, driver_data: Dict[str, Any], load_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        Validate driver can be assigned to this load
        """
        errors = []
        warnings = []

        # Basic validation
        driver_errors = await self._validate_driver_for_eu(
            driver_data, load_data, {}
        )
        errors.extend(driver_errors)

        # Check driver hours
        hours_available = driver_data.get("hours_available", 0)
        estimated_duration = load_data.get("estimated_duration_hours", 0)

        if hours_available < estimated_duration:
            errors.append(
                f"Insufficient driving hours: Need {estimated_duration}h, driver has {hours_available}h"
            )

        if errors:
            status = ComplianceStatus.ERROR
            message = "Driver cannot be assigned to this load"
        elif warnings:
            status = ComplianceStatus.WARNING
            message = "Driver can be assigned with warnings"
        else:
            status = ComplianceStatus.VALID
            message = "Driver meets all requirements"

        return ComplianceValidationResult(
            status=status,
            message=message,
            errors=errors if errors else None,
            warnings=warnings if warnings else None,
        )

    async def validate_equipment(
        self, equipment_data: Dict[str, Any], load_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        Validate equipment meets EU requirements
        """
        errors = []
        warnings = []

        # 1. Technical Inspection Certificate
        if not equipment_data.get("technical_inspection_valid_until"):
            errors.append("Valid technical inspection certificate required")
        else:
            inspection_expiry = equipment_data.get("technical_inspection_valid_until")
            if isinstance(inspection_expiry, str):
                inspection_expiry = datetime.fromisoformat(inspection_expiry)
            if inspection_expiry < datetime.utcnow():
                errors.append("Technical inspection has expired")

        # 2. Digital Tachograph
        if not equipment_data.get("has_digital_tachograph"):
            errors.append("Digital tachograph required for commercial vehicles")

        # 3. Temperature Control (if needed)
        if load_data.get("requires_temperature_control"):
            if not equipment_data.get("atp_certificate"):
                errors.append(
                    "ATP certificate required for refrigerated transport"
                )

        # 4. Emissions Standard
        emission_standard = equipment_data.get("emission_standard", "")
        if emission_standard and emission_standard < "EURO5":
            warnings.append(
                f"Vehicle emission standard is {emission_standard}. "
                "Some EU cities restrict access for older vehicles"
            )

        if errors:
            status = ComplianceStatus.ERROR
            message = "Equipment does not meet requirements"
        elif warnings:
            status = ComplianceStatus.WARNING
            message = "Equipment meets requirements with warnings"
        else:
            status = ComplianceStatus.VALID
            message = "Equipment meets all requirements"

        return ComplianceValidationResult(
            status=status,
            message=message,
            errors=errors if errors else None,
            warnings=warnings if warnings else None,
        )

    async def validate_payment(
        self, payment_data: Dict[str, Any], load_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        Validate payment meets EU cross-border requirements
        """
        errors = []
        warnings = []

        # EU uses EUR for most cross-border payments
        currency = payment_data.get("currency", "EUR")
        if currency != "EUR":
            warnings.append(
                f"Payment in {currency}. EUR recommended for EU cross-border payments"
            )

        # SEPA payment validation
        payment_method = payment_data.get("payment_method", "")
        if payment_method == "bank_transfer":
            if not payment_data.get("iban"):
                errors.append("IBAN required for SEPA bank transfers")
            if not payment_data.get("bic"):
                warnings.append("BIC/SWIFT code recommended for international transfers")

        # VAT validation for cross-border
        origin_country = load_data.get("origin_country_code", "")
        destination_country = load_data.get("destination_country_code", "")

        if origin_country != destination_country:
            if not payment_data.get("vat_number"):
                warnings.append(
                    "VAT number should be provided for cross-border invoicing"
                )

        if errors:
            status = ComplianceStatus.ERROR
            message = "Payment validation failed"
        elif warnings:
            status = ComplianceStatus.WARNING
            message = "Payment validated with warnings"
        else:
            status = ComplianceStatus.VALID
            message = "Payment meets all requirements"

        return ComplianceValidationResult(
            status=status,
            message=message,
            errors=errors if errors else None,
            warnings=warnings if warnings else None,
        )

    def get_route_optimization_rules(self) -> Dict[str, Any]:
        """
        EU-specific route optimization rules
        """
        return {
            "optimization_goal": "minimize_border_crossings",
            "distance_unit": "km",
            "driver_rules": {
                "max_daily_driving_hours": 9,
                "max_weekly_driving_hours": 56,
                "max_fortnightly_driving_hours": 90,
                "daily_rest_period_hours": 11,
                "weekly_rest_period_hours": 45,
                "mandatory_break_after_hours": 4.5,
            },
            "penalties": {
                "border_crossing": 120,  # minutes delay per border
                "low_emission_zone_incompatible": 300,  # avoid if vehicle not compliant
                "toll_road": 50,  # preference to avoid tolls
            },
            "preferences": {
                "prefer_eu_routes": True,
                "avoid_non_eu_countries": True,
                "prefer_major_corridors": True,  # Better infrastructure
            },
        }

    def get_required_company_fields(self) -> List[str]:
        """
        Required company fields for EU operations
        """
        return [
            "eu_license_number",  # EU Community License
            "country_code",
            "vat_number",
            "company_registration_number",
            "ecmr_enabled",
        ]

    def get_required_driver_fields(self) -> List[str]:
        """
        Required driver fields for EU operations
        """
        return [
            "tachograph_card_number",
            "cpc_valid_until",  # Certificate of Professional Competence
            "last_return_to_base_date",
            "hours_driven_today",
            "hours_driven_this_week",
        ]

    def get_required_load_fields(self) -> List[str]:
        """
        Required load fields for EU operations
        """
        return [
            "origin_country_code",
            "destination_country_code",
            "cargo_description",
            "weight_kg",
            "is_dangerous_goods",
        ]

    def requires_government_api(self) -> bool:
        """
        EU operations do not require real-time government API integration
        (e-CMR is handled through commercial platforms)
        """
        return False

    def get_complexity_level(self) -> int:
        """
        Complexity level: 8/10
        - Multi-country operations
        - Complex cabotage tracking
        - Mobility Package requirements
        - Multiple driver rules
        """
        return 8

    async def submit_tracking_data(
        self,
        location_data: Dict[str, Any],
        vehicle_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        EU doesn't require real-time tracking submission to central authority.

        Digital tachograph data is stored locally and available for roadside inspection.
        e-CMR platforms may track location for customer visibility.
        """
        return ComplianceValidationResult(
            status=ComplianceStatus.VALID,
            message="Tracking data logged via digital tachograph"
        )

    def get_currency_code(self) -> str:
        """EU primarily uses EUR for cross-border freight."""
        return "EUR"

    def get_distance_unit(self) -> str:
        """EU uses kilometers."""
        return "km"

    def get_weight_unit(self) -> str:
        """EU uses kilograms."""
        return "kg"

    def get_required_integrations(self) -> List[Dict[str, str]]:
        """
        Required integrations for EU operations
        """
        return [
            {
                "name": "e-CMR Platform",
                "type": "document_platform",
                "required": False,
                "description": "Digital consignment note platform (Transporeon, Timocom, national systems)",
                "options": "transporeon,timocom,national"
            },
            {
                "name": "Digital Tachograph",
                "type": "telemetry",
                "required": True,
                "description": "EU-compliant digital tachograph for driver hours tracking",
                "options": "vdo,stoneridge,actia"
            },
            {
                "name": "EORI Number",
                "type": "customs",
                "required": False,
                "description": "Economic Operators Registration and Identification for non-EU border crossings",
            }
        ]
