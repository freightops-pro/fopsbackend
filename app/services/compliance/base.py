"""
Base Compliance Engine

Abstract base class that all regional compliance engines must implement.
Defines the interface for validation, document generation, and API integrations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel


class ComplianceStatus(str, Enum):
    """Compliance validation status."""
    VALID = "valid"
    WARNING = "warning"
    ERROR = "error"
    PENDING = "pending"


class ComplianceValidationResult(BaseModel):
    """Result of compliance validation."""

    status: ComplianceStatus
    message: str
    details: Optional[Dict[str, Any]] = None
    errors: List[str] = []
    warnings: List[str] = []
    required_actions: List[str] = []


class DocumentGenerationResult(BaseModel):
    """Result of document generation."""

    success: bool
    document_type: str
    document_id: Optional[str] = None
    document_url: Optional[str] = None
    xml_content: Optional[str] = None
    pdf_content: Optional[bytes] = None
    errors: List[str] = []


class BaseComplianceEngine(ABC):
    """
    Base class for all regional compliance engines.

    Each region (Brazil, Mexico, EU, India, China, Japan, USA) implements this interface
    to provide region-specific compliance validation and document generation.
    """

    def __init__(self, region_code: str):
        self.region_code = region_code

    # ========== Load Validation ==========

    @abstractmethod
    async def validate_load_before_dispatch(
        self,
        load_data: Dict[str, Any],
        company_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        Validate a load before it can be dispatched.

        Examples:
        - Brazil: Check if CT-e and MDF-e can be generated
        - Mexico: Validate Carta de Porte requirements
        - India: Check if e-Way Bill threshold is met
        - EU: Validate cabotage rules, driver home time

        Returns validation result with errors/warnings.
        """
        pass

    # ========== Document Generation ==========

    @abstractmethod
    async def generate_shipping_document(
        self,
        load_data: Dict[str, Any],
        company_data: Dict[str, Any],
        driver_data: Optional[Dict[str, Any]] = None,
        vehicle_data: Optional[Dict[str, Any]] = None
    ) -> DocumentGenerationResult:
        """
        Generate region-specific shipping documents.

        Examples:
        - Brazil: Generate MDF-e XML and submit to SEFAZ
        - Mexico: Generate Carta de Porte complemento with digital seal
        - EU: Generate e-CMR with QR code
        - India: Generate e-Way Bill via NIC API
        - China: Submit to national freight platform

        Returns document data (XML, PDF, or URL).
        """
        pass

    # ========== Payment Validation ==========

    @abstractmethod
    async def validate_payment(
        self,
        payment_data: Dict[str, Any],
        load_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        Validate payment complies with regional requirements.

        Examples:
        - Brazil: Validate CIOT code exists and matches minimum freight rate
        - Mexico: Check payment method compliance
        - EU: Validate payment terms for posted workers

        Returns validation result.
        """
        pass

    # ========== Driver Compliance ==========

    @abstractmethod
    async def validate_driver_assignment(
        self,
        driver_data: Dict[str, Any],
        load_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        Validate driver can be assigned to this load.

        Examples:
        - EU: Check Mobility Package return-to-home rules (max 4 weeks away)
        - Japan: Check if assignment exceeds 960 hours/year limit
        - USA: Validate HOS (Hours of Service) compliance

        Returns validation result.
        """
        pass

    # ========== Route Optimization ==========

    @abstractmethod
    def get_route_optimization_rules(self) -> Dict[str, Any]:
        """
        Get region-specific rules for route optimization AI.

        Returns:
            Dict with:
            - optimization_goal: What to optimize (rate_per_mile, minimize_empty, security, etc.)
            - penalties: What to avoid (deadhead, return_to_home_violation, red_zones, overtime)
            - constraints: Hard constraints (cabotage_limit, driver_home_time, etc.)
        """
        pass

    # ========== Real-time Tracking ==========

    @abstractmethod
    async def submit_tracking_data(
        self,
        location_data: Dict[str, Any],
        vehicle_data: Dict[str, Any]
    ) -> ComplianceValidationResult:
        """
        Submit tracking data to regional authorities if required.

        Examples:
        - China: Submit Beidou location to national freight platform
        - Brazil: Submit tracking for cargo security
        - EU: Digital tachograph data submission

        Returns submission result.
        """
        pass

    # ========== Currency & Units ==========

    def get_currency_code(self) -> str:
        """Get regional currency code (USD, EUR, BRL, CNY, etc.)."""
        return "USD"  # Default, override in subclass

    def get_distance_unit(self) -> str:
        """Get regional distance unit preference (kilometers or miles)."""
        return "kilometers"  # Default, override in subclass

    def get_weight_unit(self) -> str:
        """Get regional weight unit preference (kg or lbs)."""
        return "kg"  # Default, override in subclass

    # ========== Helper Methods ==========

    def requires_government_api(self) -> bool:
        """Whether this region requires real-time government API integration."""
        return False  # Override in subclasses like Brazil, Mexico, India

    def supports_digital_documents(self) -> bool:
        """Whether this region supports digital/electronic documents."""
        return True  # Most modern regions do

    def get_required_company_fields(self) -> List[str]:
        """Get list of required company profile fields for this region."""
        return []  # Override in subclasses

    def get_required_integrations(self) -> List[Dict[str, str]]:
        """
        Get list of required third-party integrations.

        Returns list of dicts with:
        - name: Integration name (e.g., "SEFAZ API", "WeChat", "Beidou")
        - type: Integration type (government_api, payment_provider, mapping, communication)
        - required: Whether it's mandatory or optional
        """
        return []
