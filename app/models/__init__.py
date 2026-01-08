"""SQLAlchemy models for FreightOps backend v2."""

from app.models.automation import AutomationRule  # noqa: F401
from app.models.company import Company  # noqa: F401
from app.models.driver import Driver, DriverIncident, DriverTraining, DriverDocument  # noqa: F401
from app.models.fuel import FuelTransaction, JurisdictionRollup  # noqa: F401
from app.models.notification import NotificationLog  # noqa: F401
from app.models.user_notification import UserNotification  # noqa: F401
from app.models.load import Load, LoadStop  # noqa: F401
from app.models.location import Location  # noqa: F401
from app.models.accounting import Customer, Invoice, LedgerEntry, Settlement  # noqa: F401
from app.models.factoring import FactoringProvider, FactoringTransaction  # noqa: F401
from app.models.banking import BankingAccount, BankingCard, BankingCustomer, BankingTransaction  # noqa: F401
from app.models.collaboration import Channel, Message, Presence  # noqa: F401
from app.models.document import DocumentProcessingJob  # noqa: F401
from app.models.ai_usage import AIUsageLog, AIUsageQuota  # noqa: F401
from app.models.ai_chat import AIConversation, AIMessage, AIContext  # noqa: F401
from app.models.ai_task import AITask, AIToolExecution, AILearning  # noqa: F401
from app.models.equipment import (  # noqa: F401
    Equipment,
    EquipmentMaintenanceEvent,
    EquipmentMaintenanceForecast,
    EquipmentUsageEvent,
)
from app.models.user import User  # noqa: F401
from app.models.rbac import Role, Permission, RolePermission, UserRole  # noqa: F401
from app.models.port import Port, PortIntegration, ContainerTracking, ContainerTrackingEvent  # noqa: F401
from app.models.integration import Integration, CompanyIntegration  # noqa: F401
from app.models.carrier_compliance import (  # noqa: F401
    CompanyInsurance,
    CarrierCredential,
    VehicleRegistration,
    ELDAuditItem,
    CSAScore,
    CarrierSAFERSnapshot,
)
from app.models.worker import (  # noqa: F401
    Worker,
    WorkerDocument,
    PayRule,
    Deduction,
    PayrollRun,
    PayItem,
    PayrollSettlement,
    GustoSync,
)

# HQ Models
from app.models.hq_employee import HQEmployee, HQRole  # noqa: F401
from app.models.hq_tenant import HQTenant, TenantStatus, SubscriptionTier  # noqa: F401
from app.models.hq_contract import HQContract, ContractStatus, ContractType  # noqa: F401
from app.models.hq_quote import HQQuote, QuoteStatus  # noqa: F401
from app.models.hq_credit import HQCredit, CreditType, CreditStatus  # noqa: F401
from app.models.hq_payout import HQPayout, PayoutStatus  # noqa: F401
from app.models.hq_system_module import HQSystemModule, ModuleStatus  # noqa: F401
from app.models.hq_banking import HQFraudAlert, HQBankingAuditLog, FraudAlertSeverity, FraudAlertStatus, BankingAuditAction  # noqa: F401

# HQ CRM Models
from app.models.hq_lead_activity import HQLeadActivity, HQEmailTemplate, HQEmailConfig, ActivityType, FollowUpStatus  # noqa: F401
from app.models.hq_lead import HQLead, LeadStatus, LeadSource  # noqa: F401
from app.models.hq_opportunity import HQOpportunity, OpportunityStage  # noqa: F401
from app.models.hq_sales_rep_commission import HQSalesRepCommission, CommissionTier  # noqa: F401
from app.models.hq_commission_record import HQCommissionRecord, CommissionRecordStatus  # noqa: F401
from app.models.hq_commission_payment import HQCommissionPayment, CommissionPaymentStatus  # noqa: F401
from app.models.hq_contractor_settlement import HQContractorSettlement, SettlementStatus  # noqa: F401
from app.models.hq_deal import HQDeal, HQDealActivity, DealStage, DealSource  # noqa: F401
from app.models.hq_subscription import HQSubscription, HQSubscriptionRateChange, HQSubscriptionStatus, HQBillingInterval  # noqa: F401

# Billing Models
from app.models.billing import Subscription, SubscriptionAddOn, PaymentMethod, StripeInvoice, StripeWebhookEvent  # noqa: F401

# HQ Accounting Models
from app.models.hq_accounting import (  # noqa: F401
    HQCustomer, CustomerStatus, CustomerType,
    HQInvoice, InvoiceStatus, InvoiceType,
    HQVendor, VendorStatus, VendorType,
    HQBill, BillStatus, BillType,
    HQPayment, PaymentType, PaymentDirection,
)

# HQ HR Models
from app.models.hq_hr import (  # noqa: F401
    HQHREmployee, HQPayrollRun, HQPayrollItem,
    EmploymentType, HREmployeeStatus, PayFrequency, PayrollStatus,
)

# HQ General Ledger Models
from app.models.hq_general_ledger import (  # noqa: F401
    HQChartOfAccounts, HQJournalEntry, HQGeneralLedgerEntry,
    HQUsageLog, HQRecurringBilling,
    AccountType, AccountSubtype, JournalEntryStatus,
    UsageMetricType, BillingFrequency,
)

# HQ AI Queue Models
from app.models.hq_ai_queue import (  # noqa: F401
    HQAIAction, HQAIAutonomyRule,
    AIActionType, AIActionRisk, AIActionStatus,
)

# HQ Chat Models
from app.models.hq_chat import HQChatChannel, HQChatMessage, HQChatParticipant  # noqa: F401

# HQ Presence Models
from app.models.hq_presence import HQPresence  # noqa: F401

