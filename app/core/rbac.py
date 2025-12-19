"""
RBAC (Role-Based Access Control) Definitions

This module defines all system roles and permissions.
These are used to seed the database and for permission checking.
"""

from enum import Enum
from typing import Dict, List, Set


class SystemRole(str, Enum):
    """
    System-wide roles available to all tenants.
    These roles are created during database seeding and cannot be deleted.
    """
    HQ_ADMIN = "HQ_ADMIN"  # FreightOps platform administrator (super admin)
    TENANT_ADMIN = "TENANT_ADMIN"  # Company administrator (full tenant access)
    DISPATCHER = "DISPATCHER"  # Manages loads and drivers
    DRIVER = "DRIVER"  # Limited access for drivers
    ACCOUNTANT = "ACCOUNTANT"  # Financial operations
    HR_SPECIALIST = "HR_SPECIALIST"  # HR and payroll operations
    SALES_AGENT = "SALES_AGENT"  # Sales operations
    SALES_MANAGER = "SALES_MANAGER"  # Sales management
    OPERATIONS_MANAGER = "OPERATIONS_MANAGER"  # Operations oversight


class Resource(str, Enum):
    """
    Resources that can be protected by permissions.
    """
    # Dispatch & Operations
    LOADS = "loads"
    DISPATCH = "dispatch"
    DRIVERS = "drivers"
    EQUIPMENT = "equipment"
    FLEET = "fleet"

    # Finance
    BANKING = "banking"
    ACCOUNTING = "accounting"
    INVOICES = "invoices"
    SETTLEMENTS = "settlements"

    # HR & Payroll
    HR = "hr"
    WORKERS = "workers"
    PAYROLL = "payroll"

    # CRM & Sales
    CRM = "crm"
    CUSTOMERS = "customers"
    SALES = "sales"

    # Administration
    SETTINGS = "settings"
    USERS = "users"
    ROLES = "roles"
    INTEGRATIONS = "integrations"
    REPORTS = "reports"

    # System (HQ only)
    ADMIN = "admin"
    TENANTS = "tenants"


class Action(str, Enum):
    """
    Actions that can be performed on resources.
    """
    VIEW = "view"  # Read access
    CREATE = "create"  # Create new records
    UPDATE = "update"  # Modify existing records
    DELETE = "delete"  # Remove records
    MANAGE = "manage"  # Full CRUD access
    APPROVE = "approve"  # Approve workflows
    EXPORT = "export"  # Export data
    ALL = "*"  # All actions


# Role display names and descriptions
ROLE_METADATA: Dict[str, Dict[str, str]] = {
    SystemRole.HQ_ADMIN: {
        "display_name": "Platform Administrator",
        "description": "Full access to FreightOps platform administration, including tenant management and system configuration.",
    },
    SystemRole.TENANT_ADMIN: {
        "display_name": "Company Administrator",
        "description": "Full access to all company features, user management, and settings.",
    },
    SystemRole.DISPATCHER: {
        "display_name": "Dispatcher",
        "description": "Manages loads, driver assignments, and dispatch operations.",
    },
    SystemRole.DRIVER: {
        "display_name": "Driver",
        "description": "View assigned loads, update status, and upload documents.",
    },
    SystemRole.ACCOUNTANT: {
        "display_name": "Accountant",
        "description": "Manages invoices, payments, banking, and financial reports.",
    },
    SystemRole.HR_SPECIALIST: {
        "display_name": "HR Specialist",
        "description": "Manages employees, payroll, and HR documentation.",
    },
    SystemRole.SALES_AGENT: {
        "display_name": "Sales Agent",
        "description": "Manages customer relationships and sales activities.",
    },
    SystemRole.SALES_MANAGER: {
        "display_name": "Sales Manager",
        "description": "Oversees sales team and has elevated CRM access.",
    },
    SystemRole.OPERATIONS_MANAGER: {
        "display_name": "Operations Manager",
        "description": "Oversees dispatch operations with read access to financials.",
    },
}


# Permission definitions: (resource, action, description, category)
PERMISSIONS: List[tuple] = [
    # Dispatch & Operations
    (Resource.LOADS, Action.VIEW, "View load information", "Dispatch"),
    (Resource.LOADS, Action.CREATE, "Create new loads", "Dispatch"),
    (Resource.LOADS, Action.UPDATE, "Update load details", "Dispatch"),
    (Resource.LOADS, Action.DELETE, "Delete loads", "Dispatch"),
    (Resource.LOADS, Action.MANAGE, "Full load management", "Dispatch"),

    (Resource.DISPATCH, Action.VIEW, "View dispatch board", "Dispatch"),
    (Resource.DISPATCH, Action.MANAGE, "Manage dispatch operations", "Dispatch"),

    (Resource.DRIVERS, Action.VIEW, "View driver information", "Fleet"),
    (Resource.DRIVERS, Action.CREATE, "Onboard new drivers", "Fleet"),
    (Resource.DRIVERS, Action.UPDATE, "Update driver records", "Fleet"),
    (Resource.DRIVERS, Action.DELETE, "Remove drivers", "Fleet"),
    (Resource.DRIVERS, Action.MANAGE, "Full driver management", "Fleet"),

    (Resource.EQUIPMENT, Action.VIEW, "View equipment", "Fleet"),
    (Resource.EQUIPMENT, Action.CREATE, "Add new equipment", "Fleet"),
    (Resource.EQUIPMENT, Action.UPDATE, "Update equipment records", "Fleet"),
    (Resource.EQUIPMENT, Action.DELETE, "Remove equipment", "Fleet"),
    (Resource.EQUIPMENT, Action.MANAGE, "Full equipment management", "Fleet"),

    (Resource.FLEET, Action.VIEW, "View fleet dashboard", "Fleet"),
    (Resource.FLEET, Action.MANAGE, "Manage fleet operations", "Fleet"),

    # Finance
    (Resource.BANKING, Action.VIEW, "View banking dashboard", "Finance"),
    (Resource.BANKING, Action.CREATE, "Initiate transfers", "Finance"),
    (Resource.BANKING, Action.APPROVE, "Approve transactions", "Finance"),
    (Resource.BANKING, Action.MANAGE, "Full banking access", "Finance"),

    (Resource.ACCOUNTING, Action.VIEW, "View accounting data", "Finance"),
    (Resource.ACCOUNTING, Action.MANAGE, "Manage accounting", "Finance"),

    (Resource.INVOICES, Action.VIEW, "View invoices", "Finance"),
    (Resource.INVOICES, Action.CREATE, "Create invoices", "Finance"),
    (Resource.INVOICES, Action.UPDATE, "Update invoices", "Finance"),
    (Resource.INVOICES, Action.DELETE, "Delete invoices", "Finance"),
    (Resource.INVOICES, Action.MANAGE, "Full invoice management", "Finance"),

    (Resource.SETTLEMENTS, Action.VIEW, "View settlements", "Finance"),
    (Resource.SETTLEMENTS, Action.CREATE, "Create settlements", "Finance"),
    (Resource.SETTLEMENTS, Action.APPROVE, "Approve settlements", "Finance"),
    (Resource.SETTLEMENTS, Action.MANAGE, "Full settlement management", "Finance"),

    # HR & Payroll
    (Resource.HR, Action.VIEW, "View HR dashboard", "HR"),
    (Resource.HR, Action.MANAGE, "Manage HR operations", "HR"),

    (Resource.WORKERS, Action.VIEW, "View worker records", "HR"),
    (Resource.WORKERS, Action.CREATE, "Add new workers", "HR"),
    (Resource.WORKERS, Action.UPDATE, "Update worker records", "HR"),
    (Resource.WORKERS, Action.DELETE, "Remove workers", "HR"),
    (Resource.WORKERS, Action.MANAGE, "Full worker management", "HR"),

    (Resource.PAYROLL, Action.VIEW, "View payroll data", "HR"),
    (Resource.PAYROLL, Action.CREATE, "Run payroll", "HR"),
    (Resource.PAYROLL, Action.APPROVE, "Approve payroll", "HR"),
    (Resource.PAYROLL, Action.MANAGE, "Full payroll management", "HR"),

    # CRM & Sales
    (Resource.CRM, Action.VIEW, "View CRM dashboard", "Sales"),
    (Resource.CRM, Action.MANAGE, "Manage CRM operations", "Sales"),

    (Resource.CUSTOMERS, Action.VIEW, "View customer information", "Sales"),
    (Resource.CUSTOMERS, Action.CREATE, "Add new customers", "Sales"),
    (Resource.CUSTOMERS, Action.UPDATE, "Update customer records", "Sales"),
    (Resource.CUSTOMERS, Action.DELETE, "Remove customers", "Sales"),
    (Resource.CUSTOMERS, Action.MANAGE, "Full customer management", "Sales"),

    (Resource.SALES, Action.VIEW, "View sales data", "Sales"),
    (Resource.SALES, Action.MANAGE, "Manage sales operations", "Sales"),

    # Administration
    (Resource.SETTINGS, Action.VIEW, "View settings", "Admin"),
    (Resource.SETTINGS, Action.MANAGE, "Manage settings", "Admin"),

    (Resource.USERS, Action.VIEW, "View users", "Admin"),
    (Resource.USERS, Action.CREATE, "Create users", "Admin"),
    (Resource.USERS, Action.UPDATE, "Update users", "Admin"),
    (Resource.USERS, Action.DELETE, "Delete users", "Admin"),
    (Resource.USERS, Action.MANAGE, "Full user management", "Admin"),

    (Resource.ROLES, Action.VIEW, "View roles", "Admin"),
    (Resource.ROLES, Action.MANAGE, "Manage roles and permissions", "Admin"),

    (Resource.INTEGRATIONS, Action.VIEW, "View integrations", "Admin"),
    (Resource.INTEGRATIONS, Action.MANAGE, "Manage integrations", "Admin"),

    (Resource.REPORTS, Action.VIEW, "View reports", "Reports"),
    (Resource.REPORTS, Action.EXPORT, "Export reports", "Reports"),

    # HQ Admin only
    (Resource.ADMIN, Action.ALL, "Full platform administration", "System"),
    (Resource.TENANTS, Action.VIEW, "View tenant list", "System"),
    (Resource.TENANTS, Action.MANAGE, "Manage tenants", "System"),
]


# Role to permissions mapping
ROLE_PERMISSIONS: Dict[SystemRole, Set[str]] = {
    SystemRole.HQ_ADMIN: {
        # HQ Admin has access to everything
        f"{Resource.ADMIN.value}:{Action.ALL.value}",
        f"{Resource.TENANTS.value}:{Action.MANAGE.value}",
    },

    SystemRole.TENANT_ADMIN: {
        # Full access to all tenant resources
        f"{Resource.LOADS.value}:{Action.MANAGE.value}",
        f"{Resource.DISPATCH.value}:{Action.MANAGE.value}",
        f"{Resource.DRIVERS.value}:{Action.MANAGE.value}",
        f"{Resource.EQUIPMENT.value}:{Action.MANAGE.value}",
        f"{Resource.FLEET.value}:{Action.MANAGE.value}",
        f"{Resource.BANKING.value}:{Action.MANAGE.value}",
        f"{Resource.ACCOUNTING.value}:{Action.MANAGE.value}",
        f"{Resource.INVOICES.value}:{Action.MANAGE.value}",
        f"{Resource.SETTLEMENTS.value}:{Action.MANAGE.value}",
        f"{Resource.HR.value}:{Action.MANAGE.value}",
        f"{Resource.WORKERS.value}:{Action.MANAGE.value}",
        f"{Resource.PAYROLL.value}:{Action.MANAGE.value}",
        f"{Resource.CRM.value}:{Action.MANAGE.value}",
        f"{Resource.CUSTOMERS.value}:{Action.MANAGE.value}",
        f"{Resource.SALES.value}:{Action.MANAGE.value}",
        f"{Resource.SETTINGS.value}:{Action.MANAGE.value}",
        f"{Resource.USERS.value}:{Action.MANAGE.value}",
        f"{Resource.ROLES.value}:{Action.MANAGE.value}",
        f"{Resource.INTEGRATIONS.value}:{Action.MANAGE.value}",
        f"{Resource.REPORTS.value}:{Action.VIEW.value}",
        f"{Resource.REPORTS.value}:{Action.EXPORT.value}",
    },

    SystemRole.DISPATCHER: {
        f"{Resource.LOADS.value}:{Action.MANAGE.value}",
        f"{Resource.DISPATCH.value}:{Action.MANAGE.value}",
        f"{Resource.DRIVERS.value}:{Action.VIEW.value}",
        f"{Resource.DRIVERS.value}:{Action.UPDATE.value}",
        f"{Resource.EQUIPMENT.value}:{Action.VIEW.value}",
        f"{Resource.FLEET.value}:{Action.VIEW.value}",
        f"{Resource.CUSTOMERS.value}:{Action.VIEW.value}",
        f"{Resource.REPORTS.value}:{Action.VIEW.value}",
    },

    SystemRole.DRIVER: {
        f"{Resource.LOADS.value}:{Action.VIEW.value}",
        f"{Resource.LOADS.value}:{Action.UPDATE.value}",  # Update status
        f"{Resource.DISPATCH.value}:{Action.VIEW.value}",
        f"{Resource.EQUIPMENT.value}:{Action.VIEW.value}",
    },

    SystemRole.ACCOUNTANT: {
        f"{Resource.BANKING.value}:{Action.MANAGE.value}",
        f"{Resource.ACCOUNTING.value}:{Action.MANAGE.value}",
        f"{Resource.INVOICES.value}:{Action.MANAGE.value}",
        f"{Resource.SETTLEMENTS.value}:{Action.MANAGE.value}",
        f"{Resource.CUSTOMERS.value}:{Action.VIEW.value}",
        f"{Resource.LOADS.value}:{Action.VIEW.value}",
        f"{Resource.REPORTS.value}:{Action.VIEW.value}",
        f"{Resource.REPORTS.value}:{Action.EXPORT.value}",
    },

    SystemRole.HR_SPECIALIST: {
        f"{Resource.HR.value}:{Action.MANAGE.value}",
        f"{Resource.WORKERS.value}:{Action.MANAGE.value}",
        f"{Resource.PAYROLL.value}:{Action.MANAGE.value}",
        f"{Resource.DRIVERS.value}:{Action.VIEW.value}",
        f"{Resource.REPORTS.value}:{Action.VIEW.value}",
    },

    SystemRole.SALES_AGENT: {
        f"{Resource.CRM.value}:{Action.VIEW.value}",
        f"{Resource.CUSTOMERS.value}:{Action.VIEW.value}",
        f"{Resource.CUSTOMERS.value}:{Action.CREATE.value}",
        f"{Resource.CUSTOMERS.value}:{Action.UPDATE.value}",
        f"{Resource.SALES.value}:{Action.VIEW.value}",
        f"{Resource.LOADS.value}:{Action.VIEW.value}",
        f"{Resource.REPORTS.value}:{Action.VIEW.value}",
    },

    SystemRole.SALES_MANAGER: {
        f"{Resource.CRM.value}:{Action.MANAGE.value}",
        f"{Resource.CUSTOMERS.value}:{Action.MANAGE.value}",
        f"{Resource.SALES.value}:{Action.MANAGE.value}",
        f"{Resource.LOADS.value}:{Action.VIEW.value}",
        f"{Resource.REPORTS.value}:{Action.VIEW.value}",
        f"{Resource.REPORTS.value}:{Action.EXPORT.value}",
    },

    SystemRole.OPERATIONS_MANAGER: {
        f"{Resource.LOADS.value}:{Action.MANAGE.value}",
        f"{Resource.DISPATCH.value}:{Action.MANAGE.value}",
        f"{Resource.DRIVERS.value}:{Action.MANAGE.value}",
        f"{Resource.EQUIPMENT.value}:{Action.MANAGE.value}",
        f"{Resource.FLEET.value}:{Action.MANAGE.value}",
        f"{Resource.ACCOUNTING.value}:{Action.VIEW.value}",
        f"{Resource.INVOICES.value}:{Action.VIEW.value}",
        f"{Resource.CUSTOMERS.value}:{Action.VIEW.value}",
        f"{Resource.REPORTS.value}:{Action.VIEW.value}",
        f"{Resource.REPORTS.value}:{Action.EXPORT.value}",
    },
}


def get_permission_key(resource: Resource | str, action: Action | str) -> str:
    """Generate a permission key from resource and action."""
    r = resource.value if isinstance(resource, Resource) else resource
    a = action.value if isinstance(action, Action) else action
    return f"{r}:{a}"


def get_role_permissions(role: SystemRole | str) -> Set[str]:
    """Get all permissions for a role."""
    if isinstance(role, str):
        try:
            role = SystemRole(role)
        except ValueError:
            return set()
    return ROLE_PERMISSIONS.get(role, set())
