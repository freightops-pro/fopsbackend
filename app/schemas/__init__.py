"""Pydantic schemas."""

from app.schemas.automation import AutomationRuleCreate, AutomationRuleResponse, AutomationRuleUpdate  # noqa: F401
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse  # noqa: F401
from app.schemas.driver import (
    DriverComplianceResponse,
    DriverIncidentCreate,
    DriverResponse,
    DriverTrainingCreate,
)  # noqa: F401
from app.schemas.fuel import FuelImportRequest, FuelSummaryResponse, JurisdictionSummaryResponse  # noqa: F401
from app.schemas.accounting import (  # noqa: F401
    CustomerCreate,
    CustomerResponse,
    CustomerSummary,
    CustomerUpdate,
    CustomersSummaryResponse,
    InvoiceCreate,
    InvoiceResponse,
    LedgerEntryResponse,
    LedgerSummaryResponse,
    SettlementCreate,
    SettlementResponse,
)
from app.schemas.banking import (  # noqa: F401
    BankingAccountCreate,
    BankingAccountResponse,
    BankingCardCreate,
    BankingCardResponse,
    BankingCustomerCreate,
    BankingCustomerResponse,
    BankingTransactionResponse,
)
from app.schemas.collaboration import (  # noqa: F401
    ChannelCreate,
    ChannelDetailResponse,
    ChannelResponse,
    MessageCreate,
    MessageResponse,
)
from app.schemas.reporting import DashboardMetrics  # noqa: F401
from app.schemas.presence import PresenceState, PresenceUpdate  # noqa: F401
from app.schemas.equipment import (  # noqa: F401
    EquipmentMaintenanceCreate,
    EquipmentMaintenanceEventResponse,
    EquipmentMaintenanceForecastResponse,
    EquipmentResponse,
    EquipmentUsageEventCreate,
    EquipmentUsageEventResponse,
)
from app.schemas.carrier_compliance import (  # noqa: F401
    CarrierComplianceDashboardResponse,
    CarrierCredentialCreate,
    CarrierCredentialResponse,
    CarrierCredentialUpdate,
    CarrierSAFERDataResponse,
    CompanyInsuranceCreate,
    CompanyInsuranceResponse,
    CompanyInsuranceUpdate,
    CSAScoreCreate,
    CSAScoreResponse,
    ELDAuditItemCreate,
    ELDAuditItemResolve,
    ELDAuditItemResponse,
    ELDAuditItemUpdate,
    ELDAuditSummaryResponse,
    VehicleRegistrationCreate,
    VehicleRegistrationResponse,
    VehicleRegistrationUpdate,
)

