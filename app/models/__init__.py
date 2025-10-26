"""Models package.

Explicit imports to ensure models are registered before table creation.
"""

# Core models first
from .userModels import Users, Companies, Driver, Truck, Loads  # noqa: F401

from .employee import Employee  # noqa: F401
from .onboarding import OnboardingFlow, OnboardingTask  # noqa: F401
# Payroll related models
from .payroll import (
	PayrollRun, PayrollEntry, OvertimeApproval, BonusPayment, DriverSettlement  # noqa: F401
)
# Benefits
from .benefits import EmployeeBenefits  # noqa: F401
# Documents
from .document import Document  # noqa: F401
from .bill import Bill  # noqa: F401
from .vendor import Vendor  # noqa: F401
from .invoice import Invoice  # noqa: F401
# Existing models are imported dynamically elsewhere
from .customer import Customer  # noqa: F401
from .simple_load import SimpleLoad  # noqa: F401
# Banking models
from .banking import (
    BankingCustomer, BankingAccount, BankingCard, 
    BankingTransaction, BankingTransfer  # noqa: F401
)
# Chat models
from .chat import (
    Conversation, ConversationReadStatus, Message  # noqa: F401
)
# HQ Admin models
from .hqModels import HQAdmin  # noqa: F401
# Stripe models
from .stripeModels import (
    StripeCustomer, SubscriptionPlan, CompanySubscription,
    PaymentMethod, StripeInvoice, StripeWebhookEvent  # noqa: F401
)

# Team models for Enterprise messaging
from .team import Team, TeamMember  # noqa: F401

# Port credential models
from .port import (
    Port, PortCredential, CompanyPortAddon, PortAPIUsage,
    PortAuditLog, PortHealthCheck  # noqa: F401
)

# Multi-authority models
from .multi_authority import (
    Authority, AuthorityUser, AuthorityFinancials,
    AuthorityCustomer, AuthorityIntegration, AuthorityAuditLog  # noqa: F401
)

# Company-User relationship models
from .company_user import CompanyUser  # noqa: F401

# Load board models
from .load_board import LoadBoard, LoadBooking  # noqa: F401

# Broker commission models
from .broker_commission import BrokerCommission  # noqa: F401

# Subscriber and messenger models
from .subscriber import Subscriber  # noqa: F401
from .messenger_permissions import MessengerAdmin  # noqa: F401
from .message_attachments import MessageAttachment  # noqa: F401
from .ai_insights import AIInsight  # noqa: F401

# Enterprise models
from .enterprise import (
    WhiteLabelConfig, Webhook, CustomWorkflow, EnterpriseIntegration  # noqa: F401
)

# Load leg models (multi-leg loads with transloading)
from .load_leg import LoadLeg, TransloadOperation, TransloadFacility  # noqa: F401

# Load stop models (multi-stop loads)
from .load_stop import LoadStop  # noqa: F401

# Multi-location models
from .multi_location import (
    Location, LocationUser, LocationEquipment, InterLocationTransfer  # noqa: F401
)

# Collaboration models
from .collaboration import (
    WriteLock, WriteLockRequest, RecordViewer, RecordVersion, CollaborationMessage  # noqa: F401
)
