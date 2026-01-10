"""
Regional Configuration Service

Provides region-specific requirements, fields, and compliance rules
for motor carriers based on their operating region/country.
"""

from typing import Dict, List, Optional
from enum import Enum


class OperatingRegion(str, Enum):
    """Supported operating regions."""

    # North America
    USA = "usa"
    CANADA = "canada"
    MEXICO = "mexico"

    # Europe
    EU_GENERAL = "eu"
    UK = "uk"
    GERMANY = "germany"
    FRANCE = "france"
    POLAND = "poland"
    NETHERLANDS = "netherlands"
    SPAIN = "spain"
    ITALY = "italy"

    # Middle East
    UAE = "uae"
    SAUDI_ARABIA = "saudi_arabia"

    # Asia-Pacific
    CHINA = "china"
    INDIA = "india"
    JAPAN = "japan"
    SOUTH_KOREA = "south_korea"
    AUSTRALIA = "australia"

    # South America
    BRAZIL = "brazil"
    ARGENTINA = "argentina"


class RegionalField:
    """Represents a region-specific field."""

    def __init__(
        self,
        field_name: str,
        label: str,
        required: bool = False,
        field_type: str = "text",
        description: Optional[str] = None,
        validation_pattern: Optional[str] = None,
    ):
        self.field_name = field_name
        self.label = label
        self.required = required
        self.field_type = field_type
        self.description = description
        self.validation_pattern = validation_pattern


class RegionalRequirement:
    """Represents a region-specific compliance requirement."""

    def __init__(
        self,
        requirement_id: str,
        name: str,
        description: str,
        category: str,
        mandatory: bool = True,
    ):
        self.requirement_id = requirement_id
        self.name = name
        self.description = description
        self.category = category
        self.mandatory = mandatory


# Regional Configuration Data
REGIONAL_CONFIGS = {
    # ===== NORTH AMERICA =====
    OperatingRegion.USA: {
        "name": "United States",
        "fields": [
            RegionalField("dot_number", "DOT Number", required=True,
                         description="US Department of Transportation number for interstate commerce"),
            RegionalField("mc_number", "MC Number", required=False,
                         description="Motor Carrier authority number for for-hire operations"),
            RegionalField("scac_code", "SCAC Code", required=False,
                         description="Standard Carrier Alpha Code (2-4 characters)"),
            RegionalField("ucr_number", "UCR Number", required=False,
                         description="Unified Carrier Registration"),
            RegionalField("ifta_number", "IFTA Account", required=True,
                         description="International Fuel Tax Agreement account"),
            RegionalField("irp_number", "IRP Number", required=False,
                         description="International Registration Plan number"),
        ],
        "requirements": [
            RegionalRequirement("eld_mandate", "ELD Compliance",
                              "Electronic Logging Device mandate compliance", "safety"),
            RegionalRequirement("csa_rating", "CSA/SMS Safety Rating",
                              "FMCSA Compliance, Safety, Accountability program", "safety"),
            RegionalRequirement("boc3", "BOC-3 Filing",
                              "Process agents designation for all 50 states", "legal"),
        ],
        "documents": ["BOL", "Rate Confirmation", "POD", "Driver Logs (ELD)", "IFTA Reports"],
        "currency": "USD",
        "distance_unit": "miles",
        "weight_unit": "lbs",
    },

    OperatingRegion.CANADA: {
        "name": "Canada",
        "fields": [
            RegionalField("nsc_number", "NSC Number", required=True,
                         description="National Safety Code carrier profile number"),
            RegionalField("cvor_number", "CVOR Number", required=False,
                         description="Commercial Vehicle Operator's Registration (Ontario)"),
            RegionalField("ifta_number", "IFTA Account", required=True,
                         description="International Fuel Tax Agreement account"),
            RegionalField("irp_number", "IRP Number", required=False,
                         description="International Registration Plan number"),
            RegionalField("fast_number", "FAST Number", required=False,
                         description="Free and Secure Trade program for cross-border"),
        ],
        "requirements": [
            RegionalRequirement("safety_fitness", "Safety Fitness Certificate",
                              "Provincial safety fitness certificate", "safety"),
            RegionalRequirement("pip", "PIP Program",
                              "Partners in Protection security program", "security"),
        ],
        "documents": ["BOL", "Rate Confirmation", "POD", "Customs Documents", "IFTA Reports"],
        "currency": "CAD",
        "distance_unit": "kilometers",
        "weight_unit": "kg",
    },

    OperatingRegion.MEXICO: {
        "name": "Mexico",
        "fields": [
            RegionalField("sct_permit", "SCT Permit", required=True,
                         description="Secretaría de Comunicaciones y Transportes permit"),
            RegionalField("rfc_number", "RFC Number", required=True,
                         description="Registro Federal de Contribuyentes (Tax ID)"),
            RegionalField("autotransporte_permit", "Autotransporte Federal", required=True,
                         description="Federal transport permit"),
        ],
        "requirements": [
            RegionalRequirement("caat", "CAAT (Carta de Porte)",
                              "Electronic waybill requirement", "compliance"),
        ],
        "documents": ["Carta de Porte", "Factura", "Proof of Delivery"],
        "currency": "MXN",
        "distance_unit": "kilometers",
        "weight_unit": "kg",
    },

    # ===== EUROPE =====
    OperatingRegion.EU_GENERAL: {
        "name": "European Union",
        "fields": [
            RegionalField("eu_license_number", "EU Operating License", required=True,
                         description="Community License for international road haulage"),
            RegionalField("eori_number", "EORI Number", required=True,
                         description="Economic Operators Registration and Identification"),
            RegionalField("vat_number", "VAT Number", required=True,
                         description="Value Added Tax registration number"),
        ],
        "requirements": [
            RegionalRequirement("digital_tacho", "Digital Tachograph",
                              "Digital tachograph compliance", "safety"),
            RegionalRequirement("cmr", "CMR Convention",
                              "International road transport convention compliance", "legal"),
            RegionalRequirement("cabotage", "Cabotage Rules",
                              "Compliance with EU cabotage restrictions", "legal"),
            RegionalRequirement("posted_workers", "Posted Worker Directive",
                              "Posted worker directive compliance", "legal"),
        ],
        "documents": ["CMR", "Invoice", "POD", "Tachograph Records"],
        "currency": "EUR",
        "distance_unit": "kilometers",
        "weight_unit": "kg",
    },

    OperatingRegion.UK: {
        "name": "United Kingdom",
        "fields": [
            RegionalField("operator_license", "Operator's License", required=True,
                         description="O-License (Goods Vehicle Operator License)"),
            RegionalField("gb_eori_number", "GB EORI Number", required=True,
                         description="GB Economic Operators Registration"),
            RegionalField("vat_number", "VAT Number", required=True,
                         description="UK VAT registration number"),
        ],
        "requirements": [
            RegionalRequirement("traffic_commissioner", "Traffic Commissioner Compliance",
                              "Compliance with Traffic Commissioner requirements", "legal"),
            RegionalRequirement("kent_access", "Kent Access Permit",
                              "Kent Access Permit for EU transport (if applicable)", "border"),
        ],
        "documents": ["CMR", "Invoice", "POD", "Customs Declaration"],
        "currency": "GBP",
        "distance_unit": "miles",
        "weight_unit": "kg",
    },

    # ===== MIDDLE EAST =====
    OperatingRegion.UAE: {
        "name": "United Arab Emirates",
        "fields": [
            RegionalField("rta_license", "RTA License", required=True,
                         description="Roads and Transport Authority license"),
            RegionalField("trade_license", "Trade License", required=True,
                         description="Dubai/Abu Dhabi trade license"),
            RegionalField("tin", "TIN", required=True,
                         description="Tax Identification Number"),
            RegionalField("salik_account", "Salik Account", required=False,
                         description="Dubai toll system account"),
        ],
        "requirements": [
            RegionalRequirement("vat_compliance", "VAT Compliance",
                              "UAE VAT (5%) compliance", "tax"),
        ],
        "documents": ["Invoice", "Delivery Note", "Customs Documents"],
        "currency": "AED",
        "distance_unit": "kilometers",
        "weight_unit": "kg",
    },

    # ===== ASIA-PACIFIC =====
    OperatingRegion.CHINA: {
        "name": "China",
        "fields": [
            RegionalField("road_transport_license", "Road Transport License", required=True,
                         description="道路运输经营许可证"),
            RegionalField("business_license", "Business License", required=True,
                         description="营业执照"),
            RegionalField("organization_code", "Organization Code", required=True,
                         description="组织机构代码证"),
            RegionalField("tax_registration", "Tax Registration", required=True,
                         description="税务登记证"),
        ],
        "requirements": [
            RegionalRequirement("gps_tracking", "GPS/BeiDou Tracking",
                              "Mandatory GPS/BeiDou satellite tracking", "technology"),
        ],
        "documents": ["Waybill (运单)", "Invoice (发票)", "POD"],
        "currency": "CNY",
        "distance_unit": "kilometers",
        "weight_unit": "kg",
    },

    OperatingRegion.INDIA: {
        "name": "India",
        "fields": [
            RegionalField("pan_number", "PAN Number", required=True,
                         description="Permanent Account Number"),
            RegionalField("gst_number", "GST Number", required=True,
                         description="Goods and Services Tax registration"),
            RegionalField("national_permit", "National Permit", required=False,
                         description="All-India permit for inter-state operations"),
        ],
        "requirements": [
            RegionalRequirement("eway_bill", "E-Way Bill System",
                              "Electronic waybill for goods movement", "compliance"),
            RegionalRequirement("fastag", "FASTag",
                              "Electronic toll collection system", "technology"),
        ],
        "documents": ["E-Way Bill", "GST Invoice", "LR (Lorry Receipt)", "POD"],
        "currency": "INR",
        "distance_unit": "kilometers",
        "weight_unit": "kg",
    },

    OperatingRegion.JAPAN: {
        "name": "Japan",
        "fields": [
            RegionalField("transport_license", "Transport Business License", required=True,
                         description="運送業許可"),
            RegionalField("corporate_number", "Corporate Number", required=True,
                         description="法人番号"),
        ],
        "requirements": [
            RegionalRequirement("digital_tacho_jp", "Digital Tachograph",
                              "Digital tachograph requirement", "safety"),
            RegionalRequirement("green_mgmt", "Green Management",
                              "Environmental management certification", "environment"),
        ],
        "documents": ["Delivery Slip (配送伝票)", "Invoice (請求書)", "POD"],
        "currency": "JPY",
        "distance_unit": "kilometers",
        "weight_unit": "kg",
    },

    OperatingRegion.AUSTRALIA: {
        "name": "Australia",
        "fields": [
            RegionalField("abn", "ABN", required=True,
                         description="Australian Business Number"),
            RegionalField("nhvas_accreditation", "NHVAS Accreditation", required=False,
                         description="National Heavy Vehicle Accreditation Scheme"),
        ],
        "requirements": [
            RegionalRequirement("hvnl", "Heavy Vehicle National Law",
                              "HVNL compliance", "legal"),
            RegionalRequirement("cor", "Chain of Responsibility",
                              "Chain of Responsibility compliance", "legal"),
        ],
        "documents": ["Consignment Note", "Invoice", "POD"],
        "currency": "AUD",
        "distance_unit": "kilometers",
        "weight_unit": "kg",
    },

    # ===== SOUTH AMERICA =====
    OperatingRegion.BRAZIL: {
        "name": "Brazil",
        "fields": [
            RegionalField("antt_registration", "ANTT Registration", required=True,
                         description="National Land Transport Agency registration"),
            RegionalField("cnpj", "CNPJ", required=True,
                         description="Cadastro Nacional da Pessoa Jurídica (Corporate Tax ID)"),
            RegionalField("rntrc", "RNTRC", required=True,
                         description="National Registry of Road Cargo Transporters"),
            RegionalField("ie_number", "IE Number", required=True,
                         description="Inscrição Estadual (State Tax Registration)"),
        ],
        "requirements": [
            RegionalRequirement("cte", "CT-e System",
                              "Electronic Transport Document system", "compliance"),
            RegionalRequirement("mdfe", "MDF-e System",
                              "Electronic Cargo Manifest system", "compliance"),
        ],
        "documents": ["CT-e", "MDF-e", "DACTE", "Nota Fiscal"],
        "currency": "BRL",
        "distance_unit": "kilometers",
        "weight_unit": "kg",
    },
}


class RegionConfigService:
    """Service for retrieving region-specific configurations."""

    @staticmethod
    def get_config(region: OperatingRegion) -> Dict:
        """Get configuration for a specific region."""
        return REGIONAL_CONFIGS.get(region, {})

    @staticmethod
    def get_required_fields(region: OperatingRegion) -> List[RegionalField]:
        """Get required fields for a region."""
        config = REGIONAL_CONFIGS.get(region, {})
        fields = config.get("fields", [])
        return [field for field in fields if field.required]

    @staticmethod
    def get_all_fields(region: OperatingRegion) -> List[RegionalField]:
        """Get all fields for a region."""
        config = REGIONAL_CONFIGS.get(region, {})
        return config.get("fields", [])

    @staticmethod
    def get_requirements(region: OperatingRegion) -> List[RegionalRequirement]:
        """Get compliance requirements for a region."""
        config = REGIONAL_CONFIGS.get(region, {})
        return config.get("requirements", [])

    @staticmethod
    def get_document_types(region: OperatingRegion) -> List[str]:
        """Get required document types for a region."""
        config = REGIONAL_CONFIGS.get(region, {})
        return config.get("documents", [])

    @staticmethod
    def get_regional_settings(region: OperatingRegion) -> Dict[str, str]:
        """Get regional settings (currency, units, etc.)."""
        config = REGIONAL_CONFIGS.get(region, {})
        return {
            "currency": config.get("currency", "USD"),
            "distance_unit": config.get("distance_unit", "miles"),
            "weight_unit": config.get("weight_unit", "lbs"),
        }

    @staticmethod
    def get_all_regions() -> List[Dict[str, str]]:
        """Get list of all supported regions."""
        return [
            {"code": region.value, "name": config.get("name", region.value)}
            for region, config in REGIONAL_CONFIGS.items()
        ]
