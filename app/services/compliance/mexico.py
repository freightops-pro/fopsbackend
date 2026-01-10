"""
Mexico Compliance Engine

Handles Mexican freight regulations:
- Carta de Porte 3.0 (Digital Waybill)
- SAT (Tax Authority) digital sealing
- RFC (Tax ID) validation
- SCT (Transport Ministry) permits
- GPS jammer detection requirements
- High-security route optimization
"""

from typing import Any, Dict, List, Optional
from .base import (
    BaseComplianceEngine,
    ComplianceStatus,
    ComplianceValidationResult,
    DocumentGenerationResult,
)


class MexicoComplianceEngine(BaseComplianceEngine):
    """
    Mexico freight compliance engine.

    Key Requirements:
    1. RFC (Registro Federal de Contribuyentes) - Tax ID
    2. SCT (Secretaría de Comunicaciones y Transportes) permit
    3. Carta de Porte 3.0 - Digital waybill with UUID seal from SAT
    4. GPS jammer detection for high-value cargo
    5. Security routing to avoid cartel-controlled areas
    """

    def __init__(self, region_code: str = "mexico"):
        super().__init__(region_code)

    async def validate_load_before_dispatch(
        self,
        load_data: Dict[str, Any],
        company_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        Validate load can be dispatched under Mexican regulations.

        Checks:
        1. Company has valid RFC (Tax ID)
        2. SCT transport permit is active
        3. Route security assessment
        4. GPS jammer detection requirement for high-value loads
        """
        errors = []
        warnings = []

        # Check RFC registration
        if not company_data.get("rfc"):
            errors.append("RFC (Tax ID) is required for freight operations in Mexico")

        # Check SCT permit
        if not company_data.get("sct_permit"):
            errors.append("SCT transport permit is required")

        # Check for high-value cargo requiring GPS jammer detection
        cargo_value = load_data.get("cargo_value_mxn", 0)
        if cargo_value > 500000:  # 500,000 MXN threshold
            if not load_data.get("gps_jammer_detector_installed"):
                warnings.append(
                    "WARNING: High-value cargo (>500K MXN) recommended to have GPS jammer detector"
                )

        # Security risk assessment
        origin_state = load_data.get("origin_state", "")
        destination_state = load_data.get("destination_state", "")

        high_risk_states = [
            "Guerrero", "Michoacán", "Tamaulipas", "Sinaloa",
            "Chihuahua", "Durango", "Zacatecas"
        ]

        if origin_state in high_risk_states or destination_state in high_risk_states:
            warnings.append(
                f"WARNING: Route passes through high-risk security zone. "
                f"Consider security escort and convoy travel during daylight hours."
            )

        # Check insurance for cargo value
        if cargo_value > 100000 and not company_data.get("cargo_insurance_active"):
            warnings.append("Cargo insurance recommended for loads over 100K MXN")

        status = ComplianceStatus.ERROR if errors else (
            ComplianceStatus.WARNING if warnings else ComplianceStatus.VALID
        )

        return ComplianceValidationResult(
            status=status,
            message="Mexican transport compliance validation complete",
            errors=errors,
            warnings=warnings,
            details={
                "cargo_value_mxn": cargo_value,
                "high_risk_route": bool(
                    origin_state in high_risk_states or destination_state in high_risk_states
                )
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
        Generate Carta de Porte 3.0 (Digital Waybill).

        The Carta de Porte is a CFDI (Comprobante Fiscal Digital por Internet)
        document that must be digitally sealed by SAT before transport begins.

        Components:
        1. Operator details (driver)
        2. Vehicle/trailer identification
        3. Origin and destination locations
        4. Cargo details and customs info
        5. SAT digital seal (UUID)
        """
        # Build Carta de Porte XML structure
        xml_content = self._generate_carta_porte_xml(
            load_data, company_data, driver_data, vehicle_data
        )

        # In production: Submit to SAT for digital sealing
        # For now, return unsigned XML
        return DocumentGenerationResult(
            success=True,
            document_type="carta_de_porte",
            document_id=f"CP-{load_data.get('load_number', 'UNKNOWN')}",
            xml_content=xml_content,
            errors=[],
            metadata={
                "version": "3.0",
                "cfdi_type": "T",  # Traslado (Transport)
                "requires_sat_seal": True,
                "sat_environment": company_data.get("sat_environment", "production")
            }
        )

    def _generate_carta_porte_xml(
        self,
        load_data: Dict[str, Any],
        company_data: Dict[str, Any],
        driver_data: Optional[Dict[str, Any]],
        vehicle_data: Optional[Dict[str, Any]]
    ) -> str:
        """
        Generate Carta de Porte 3.0 XML structure.

        Official specification: SAT Anexo 20 - Complemento Carta Porte
        """
        rfc = company_data.get("rfc", "UNKNOWN")
        company_name = company_data.get("company_name", "Unknown")
        load_number = load_data.get("load_number", "UNKNOWN")

        # Driver info
        driver_name = driver_data.get("name", "Unknown") if driver_data else "Unknown"
        driver_license = driver_data.get("license_number", "") if driver_data else ""

        # Vehicle info
        vehicle_plate = vehicle_data.get("plate", "") if vehicle_data else ""
        vehicle_year = vehicle_data.get("year", "") if vehicle_data else ""

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante
    xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    xmlns:cartaporte30="http://www.sat.gob.mx/CartaPorte30"
    Version="4.0"
    Serie="CP"
    Folio="{load_number}"
    Fecha="{load_data.get('pickup_date', '')}"
    TipoDeComprobante="T"
    LugarExpedicion="{load_data.get('origin_postal_code', '00000')}"
    Moneda="MXN"
    SubTotal="0"
    Total="0">

    <!-- Emisor (Carrier) -->
    <cfdi:Emisor Rfc="{rfc}" Nombre="{company_name}"/>

    <!-- Receptor (Shipper/Receiver) -->
    <cfdi:Receptor
        Rfc="{load_data.get('shipper_rfc', 'XAXX010101000')}"
        Nombre="{load_data.get('shipper_name', 'PUBLICO EN GENERAL')}"
        UsoCFDI="S01"/>

    <!-- Conceptos (always 1 for transport) -->
    <cfdi:Conceptos>
        <cfdi:Concepto
            ClaveProdServ="78101800"
            Cantidad="1"
            ClaveUnidad="E48"
            Descripcion="Servicio de transporte de carga"
            ValorUnitario="0"
            Importe="0"/>
    </cfdi:Conceptos>

    <!-- Complemento: Carta de Porte -->
    <cfdi:Complemento>
        <cartaporte30:CartaPorte
            Version="3.0"
            TranspInternac="No"
            TotalDistRec="{load_data.get('distance_km', 0)}">

            <!-- Ubicaciones (Origin and Destination) -->
            <cartaporte30:Ubicaciones>
                <cartaporte30:Ubicacion
                    TipoUbicacion="Origen"
                    RFCRemitenteDestinatario="{load_data.get('shipper_rfc', 'XAXX010101000')}"
                    FechaHoraSalidaLlegada="{load_data.get('pickup_date', '')}"
                    DistanciaRecorrida="0"/>

                <cartaporte30:Ubicacion
                    TipoUbicacion="Destino"
                    RFCRemitenteDestinatario="{load_data.get('receiver_rfc', 'XAXX010101000')}"
                    FechaHoraSalidaLlegada="{load_data.get('delivery_date', '')}"
                    DistanciaRecorrida="{load_data.get('distance_km', 0)}"/>
            </cartaporte30:Ubicaciones>

            <!-- Mercancias (Cargo) -->
            <cartaporte30:Mercancias
                UnidadPeso="KGM"
                PesoBrutoTotal="{load_data.get('weight_kg', 0)}"
                NumTotalMercancias="1">

                <cartaporte30:Mercancia
                    BienesTransp="{load_data.get('cargo_sat_code', '01010101')}"
                    Descripcion="{load_data.get('cargo_description', 'Carga general')}"
                    Cantidad="{load_data.get('quantity', 1)}"
                    ClaveUnidad="KGM"
                    PesoEnKg="{load_data.get('weight_kg', 0)}"
                    ValorMercancia="{load_data.get('cargo_value_mxn', 0)}"
                    Moneda="MXN"/>

                <cartaporte30:Autotransporte
                    PermSCT="{company_data.get('sct_permit_type', 'TPAF01')}"
                    NumPermisoSCT="{company_data.get('sct_permit', '')}">

                    <cartaporte30:IdentificacionVehicular
                        ConfigVehicular="C2"
                        PlacaVM="{vehicle_plate}"
                        AnioModeloVM="{vehicle_year}"/>

                    <cartaporte30:Seguros
                        AseguraRespCivil="{company_data.get('insurance_company', 'Unknown')}"
                        PolizaRespCivil="{company_data.get('insurance_policy', '')}"/>
                </cartaporte30:Autotransporte>
            </cartaporte30:Mercancias>

            <!-- Figura Transporte (Driver) -->
            <cartaporte30:FiguraTransporte>
                <cartaporte30:TiposFigura
                    TipoFigura="01"
                    RFCFigura="{driver_data.get('rfc', '') if driver_data else ''}"
                    NombreFigura="{driver_name}"
                    NumLicencia="{driver_license}"/>
            </cartaporte30:FiguraTransporte>

        </cartaporte30:CartaPorte>
    </cfdi:Complemento>

</cfdi:Comprobante>"""

        return xml

    async def validate_payment(
        self,
        payment_data: Dict[str, Any],
        load_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        Validate payment compliance.

        Mexico Requirements:
        1. VAT (IVA) must be included in invoice
        2. Payment must be via CFDI (digital invoice)
        """
        errors = []
        warnings = []

        # Check for VAT (16% in Mexico)
        amount = payment_data.get("amount_mxn", 0)
        vat_amount = payment_data.get("vat_amount", 0)
        expected_vat = amount * 0.16

        if abs(vat_amount - expected_vat) > 1:  # Allow 1 peso tolerance
            warnings.append(
                f"VAT amount ({vat_amount} MXN) does not match expected 16% rate ({expected_vat:.2f} MXN)"
            )

        # Check if CFDI invoice was issued
        if not payment_data.get("cfdi_uuid"):
            errors.append("CFDI (digital invoice) is required for payment")

        status = ComplianceStatus.ERROR if errors else (
            ComplianceStatus.WARNING if warnings else ComplianceStatus.VALID
        )

        return ComplianceValidationResult(
            status=status,
            message="Payment validation complete",
            errors=errors,
            warnings=warnings,
            details={
                "amount_mxn": amount,
                "vat_amount": vat_amount,
                "expected_vat": expected_vat
            }
        )

    async def validate_driver_assignment(
        self,
        driver_data: Dict[str, Any],
        load_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        Validate driver can be assigned to load.

        Mexico Requirements:
        1. Valid Mexican driver's license (Licencia Federal)
        2. Medical certificate current
        3. Security clearance for high-risk routes
        """
        errors = []
        warnings = []

        # Check driver's license
        if not driver_data.get("license_number"):
            errors.append("Valid driver's license (Licencia Federal) required")

        # Check license type
        license_type = driver_data.get("license_type", "")
        if license_type not in ["A", "B", "C", "D", "E"]:
            errors.append("Driver must have commercial license (Type A-E)")

        # Check medical certificate
        import datetime
        medical_expiry = driver_data.get("medical_certificate_expiry")
        if medical_expiry:
            try:
                expiry_date = datetime.datetime.fromisoformat(str(medical_expiry))
                if expiry_date < datetime.datetime.now():
                    errors.append("Driver's medical certificate has expired")
            except:
                warnings.append("Unable to validate medical certificate expiry date")
        else:
            warnings.append("Medical certificate expiry date not provided")

        # Check security clearance for high-risk routes
        origin_state = load_data.get("origin_state", "")
        destination_state = load_data.get("destination_state", "")
        high_risk_states = [
            "Guerrero", "Michoacán", "Tamaulipas", "Sinaloa",
            "Chihuahua", "Durango", "Zacatecas"
        ]

        if origin_state in high_risk_states or destination_state in high_risk_states:
            if not driver_data.get("security_clearance"):
                warnings.append(
                    "Driver should have security clearance for high-risk route"
                )

        status = ComplianceStatus.ERROR if errors else (
            ComplianceStatus.WARNING if warnings else ComplianceStatus.VALID
        )

        return ComplianceValidationResult(
            status=status,
            message="Driver validation complete",
            errors=errors,
            warnings=warnings
        )

    def get_route_optimization_rules(self) -> Dict[str, Any]:
        """
        Mexico route optimization focuses on security and efficiency.

        Similar to Brazil, cargo theft is a major concern.
        Route optimization must balance:
        1. Security (avoid cartel-controlled areas)
        2. Efficiency (minimize distance/fuel)
        3. Compliance (use authorized SCT routes)
        """
        return {
            "optimization_goal": "balance_security_efficiency",
            "penalties": {
                "high_risk_zones": 800,  # Heavy penalty for cartel areas
                "night_driving_risk_zones": 500,
                "unauthorized_routes": 300,
                "excessive_distance": 50,
            },
            "constraints": {
                "avoid_guerrero_night": True,
                "avoid_tamaulipas_border": True,
                "require_toll_highways_high_value": True,
                "max_driving_hours_per_day": 12,
            },
            "preferences": {
                "prefer_cuota_highways": True,  # Toll highways are safer
                "prefer_convoy_travel": True,  # Group travel in high-risk areas
                "prefer_daylight_driving": True,
                "prefer_federal_highways": True,  # SCT-authorized routes
            }
        }

    async def submit_tracking_data(
        self,
        location_data: Dict[str, Any],
        vehicle_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        Mexico doesn't require real-time government tracking submission.

        However, GPS tracking is recommended for security and insurance purposes.
        GPS jammer detection is required for high-value cargo.
        """
        warnings = []

        # Check if GPS jammer detector is active for high-value cargo
        if vehicle_data.get("cargo_value_mxn", 0) > 500000:
            if not vehicle_data.get("gps_jammer_detector_active"):
                warnings.append(
                    "GPS jammer detector should be active for high-value cargo"
                )

        return ComplianceValidationResult(
            status=ComplianceStatus.WARNING if warnings else ComplianceStatus.VALID,
            message="Tracking data logged",
            warnings=warnings
        )

    def get_currency_code(self) -> str:
        return "MXN"

    def get_distance_unit(self) -> str:
        return "kilometers"  # Mexico uses metric system

    def get_weight_unit(self) -> str:
        return "kg"  # Kilograms

    def requires_government_api(self) -> bool:
        return True  # Requires SAT API for Carta de Porte sealing

    def get_required_company_fields(self) -> List[str]:
        return [
            "rfc",  # Tax ID (Registro Federal de Contribuyentes)
            "sct_permit",  # Transport permit number
            "sct_permit_type",  # Permit type (TPAF01, etc.)
            "insurance_company",  # Liability insurance provider
            "insurance_policy",  # Insurance policy number
        ]

    def get_required_integrations(self) -> List[Dict[str, str]]:
        return [
            {
                "name": "SAT API",
                "type": "government_api",
                "required": True,
                "description": "Tax authority API for CFDI/Carta de Porte digital sealing"
            },
            {
                "name": "GPS Tracking",
                "type": "telemetry",
                "required": False,
                "description": "GPS tracking for security and insurance purposes"
            },
            {
                "name": "GPS Jammer Detector",
                "type": "hardware",
                "required": False,
                "description": "Required for high-value cargo (>500K MXN)"
            }
        ]
