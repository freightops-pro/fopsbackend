from fastapi import APIRouter

from app.routers import (
    accounting,
    admin,
    ai_usage,
    ai_tasks,
    ai_chat,
    automation,
    auth,
    background_checks,
    banking,
    billing,
    carrier_compliance,
    check,
    company,
    collaboration,
    dashboard,
    dqf,
    documents,
    dispatch,
    drayage,
    drivers,
    equipment,
    fuel,
    fleet,
    health,
    hq,
    hr,
    integrations,
    loads,
    onboarding,
    payroll,
    ports,
    reporting,
    roles,
    settlements,
    tenant,
    usage_ledger,
    webhooks,
    websocket,
    wex,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(automation.router, prefix="/automation", tags=["Automation"])
api_router.include_router(company.router, tags=["Companies"])
api_router.include_router(dispatch.router, prefix="/dispatch", tags=["Dispatch"])
api_router.include_router(loads.router, prefix="/dispatch/loads", tags=["Dispatch"])  # Mount loads under dispatch
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(ai_usage.router, prefix="/ai", tags=["AI Usage"])
api_router.include_router(ai_tasks.router, prefix="/ai", tags=["AI Agents"])
api_router.include_router(ai_chat.router, tags=["AI Chat"])
api_router.include_router(drivers.router, prefix="/drivers", tags=["Drivers"])
api_router.include_router(fuel.router, prefix="/fuel", tags=["Fuel"])
api_router.include_router(accounting.router, prefix="/accounting", tags=["Accounting"])
api_router.include_router(banking.router, prefix="/banking", tags=["Banking"])
api_router.include_router(billing.router, tags=["Billing"])
api_router.include_router(collaboration.router, prefix="/collaboration", tags=["Collaboration"])
api_router.include_router(reporting.router, prefix="/reporting", tags=["Reporting"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(usage_ledger.router, prefix="/usage-ledger", tags=["Usage Ledger"])
api_router.include_router(hr.router, prefix="/hr", tags=["HR"])
api_router.include_router(payroll.router, prefix="/payroll", tags=["Payroll"])
api_router.include_router(fleet.router, prefix="/fleet", tags=["Fleet"])
api_router.include_router(equipment.router, prefix="/fleet", tags=["Fleet"])
api_router.include_router(carrier_compliance.router, prefix="/fleet/carrier-compliance", tags=["Carrier Compliance"])
api_router.include_router(check.router, prefix="/check", tags=["Check Payroll"])
api_router.include_router(ports.router, prefix="/ports", tags=["Ports"])
api_router.include_router(drayage.router, prefix="/drayage", tags=["Drayage"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["Integrations"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
api_router.include_router(wex.router, prefix="/wex", tags=["WEX Fuel Cards"])
api_router.include_router(admin.router, prefix="/admin", tags=["HQ Admin"])
api_router.include_router(hq.router, prefix="/hq", tags=["HQ Portal"])
api_router.include_router(tenant.router, prefix="/tenant", tags=["Tenant"])
api_router.include_router(roles.router, prefix="/rbac", tags=["Roles & Permissions"])
api_router.include_router(settlements.router, prefix="/settlements", tags=["Settlements"])
api_router.include_router(websocket.router, tags=["WebSocket"])

# Onboarding & DQF System
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["Onboarding"])
api_router.include_router(background_checks.router, prefix="/background-checks", tags=["Background Checks"])
api_router.include_router(dqf.router, prefix="/dqf", tags=["DQF"])

