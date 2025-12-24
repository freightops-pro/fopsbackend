"""Standard SaaS Chart of Accounts - Optimized for B2B AI Company.

This is the dictionary that categorizes every financial transaction.
Based on standard GAAP accounting with SaaS/AI-specific accounts.
"""

from decimal import Decimal
from typing import List, Dict, Any

# ============================================================================
# Standard SaaS Chart of Accounts
# ============================================================================

STANDARD_CHART_OF_ACCOUNTS: List[Dict[str, Any]] = [
    # =========================================================================
    # 1000-1999: ASSETS (Debit Balance)
    # =========================================================================

    # Current Assets (1000-1499)
    {
        "account_number": "1000",
        "account_name": "Cash - Operating",
        "account_type": "asset",
        "account_subtype": "cash",
        "description": "Primary operating bank account (Synctera)",
        "is_system": True,
    },
    {
        "account_number": "1010",
        "account_name": "Cash - Payroll",
        "account_type": "asset",
        "account_subtype": "cash",
        "description": "Payroll funding account",
        "is_system": True,
    },
    {
        "account_number": "1020",
        "account_name": "Cash - Reserve",
        "account_type": "asset",
        "account_subtype": "cash",
        "description": "Emergency reserve fund",
        "is_system": False,
    },
    {
        "account_number": "1100",
        "account_name": "Stripe Clearing",
        "account_type": "asset",
        "account_subtype": "cash",
        "description": "Stripe pending payouts (clears to 1000)",
        "is_system": True,
    },
    {
        "account_number": "1200",
        "account_name": "Accounts Receivable",
        "account_type": "asset",
        "account_subtype": "accounts_receivable",
        "description": "Money owed by customers",
        "is_system": True,
    },
    {
        "account_number": "1210",
        "account_name": "Unbilled Revenue",
        "account_type": "asset",
        "account_subtype": "accounts_receivable",
        "description": "Revenue earned but not yet invoiced",
        "is_system": False,
    },
    {
        "account_number": "1300",
        "account_name": "Prepaid Expenses",
        "account_type": "asset",
        "account_subtype": "prepaid_expense",
        "description": "Expenses paid in advance",
        "is_system": False,
    },
    {
        "account_number": "1310",
        "account_name": "Prepaid Insurance",
        "account_type": "asset",
        "account_subtype": "prepaid_expense",
        "description": "Annual insurance paid upfront",
        "is_system": False,
    },
    {
        "account_number": "1320",
        "account_name": "Prepaid Software",
        "account_type": "asset",
        "account_subtype": "prepaid_expense",
        "description": "Annual SaaS subscriptions paid upfront",
        "is_system": False,
    },

    # Fixed Assets (1500-1999)
    {
        "account_number": "1500",
        "account_name": "Computer Equipment",
        "account_type": "asset",
        "account_subtype": "fixed_asset",
        "description": "Laptops, servers, monitors",
        "is_system": False,
    },
    {
        "account_number": "1510",
        "account_name": "Accumulated Depreciation - Equipment",
        "account_type": "asset",
        "account_subtype": "fixed_asset",
        "description": "Contra account for equipment depreciation",
        "is_system": False,
    },
    {
        "account_number": "1600",
        "account_name": "Office Furniture",
        "account_type": "asset",
        "account_subtype": "fixed_asset",
        "description": "Desks, chairs, office equipment",
        "is_system": False,
    },

    # =========================================================================
    # 2000-2999: LIABILITIES (Credit Balance)
    # =========================================================================

    # Current Liabilities (2000-2499)
    {
        "account_number": "2000",
        "account_name": "Accounts Payable",
        "account_type": "liability",
        "account_subtype": "accounts_payable",
        "description": "Money owed to vendors",
        "is_system": True,
    },
    {
        "account_number": "2100",
        "account_name": "Accounts Payable - AI Providers",
        "account_type": "liability",
        "account_subtype": "accounts_payable",
        "description": "OpenAI, Anthropic, AWS Bedrock bills",
        "is_system": True,
    },
    {
        "account_number": "2110",
        "account_name": "Accounts Payable - Cloud Providers",
        "account_type": "liability",
        "account_subtype": "accounts_payable",
        "description": "AWS, GCP, Railway hosting bills",
        "is_system": True,
    },
    {
        "account_number": "2200",
        "account_name": "Credit Card Payable",
        "account_type": "liability",
        "account_subtype": "credit_card",
        "description": "Corporate credit card balance",
        "is_system": False,
    },
    {
        "account_number": "2300",
        "account_name": "Deferred Revenue",
        "account_type": "liability",
        "account_subtype": "deferred_revenue",
        "description": "Prepaid subscriptions not yet earned",
        "is_system": True,
    },
    {
        "account_number": "2310",
        "account_name": "Deferred Revenue - Annual Contracts",
        "account_type": "liability",
        "account_subtype": "deferred_revenue",
        "description": "Annual contract prepayments",
        "is_system": False,
    },
    {
        "account_number": "2400",
        "account_name": "Accrued Payroll",
        "account_type": "liability",
        "account_subtype": "payroll_liability",
        "description": "Payroll earned but not yet paid",
        "is_system": True,
    },
    {
        "account_number": "2410",
        "account_name": "Payroll Tax Payable",
        "account_type": "liability",
        "account_subtype": "payroll_liability",
        "description": "FICA, FUTA, state taxes withheld",
        "is_system": True,
    },
    {
        "account_number": "2420",
        "account_name": "401(k) Payable",
        "account_type": "liability",
        "account_subtype": "payroll_liability",
        "description": "Employee 401(k) contributions pending remit",
        "is_system": False,
    },
    {
        "account_number": "2500",
        "account_name": "Sales Tax Payable",
        "account_type": "liability",
        "account_subtype": "accounts_payable",
        "description": "Collected sales tax to remit",
        "is_system": False,
    },

    # Long-Term Liabilities (2500-2999)
    {
        "account_number": "2600",
        "account_name": "Notes Payable",
        "account_type": "liability",
        "account_subtype": "accounts_payable",
        "description": "Loans and notes payable",
        "is_system": False,
    },
    {
        "account_number": "2700",
        "account_name": "Convertible Notes",
        "account_type": "liability",
        "account_subtype": "accounts_payable",
        "description": "SAFE notes or convertible debt",
        "is_system": False,
    },

    # =========================================================================
    # 3000-3999: EQUITY (Credit Balance)
    # =========================================================================
    {
        "account_number": "3000",
        "account_name": "Common Stock",
        "account_type": "equity",
        "account_subtype": "owner_equity",
        "description": "Issued common shares at par value",
        "is_system": True,
    },
    {
        "account_number": "3100",
        "account_name": "Additional Paid-In Capital",
        "account_type": "equity",
        "account_subtype": "owner_equity",
        "description": "Investment above par value (VC funding)",
        "is_system": True,
    },
    {
        "account_number": "3200",
        "account_name": "Retained Earnings",
        "account_type": "equity",
        "account_subtype": "retained_earnings",
        "description": "Accumulated profits/losses from prior periods",
        "is_system": True,
    },
    {
        "account_number": "3300",
        "account_name": "Current Year Earnings",
        "account_type": "equity",
        "account_subtype": "retained_earnings",
        "description": "Net income for current fiscal year",
        "is_system": True,
    },
    {
        "account_number": "3400",
        "account_name": "Owner's Draw",
        "account_type": "equity",
        "account_subtype": "owner_equity",
        "description": "Distributions to owners",
        "is_system": False,
    },

    # =========================================================================
    # 4000-4999: REVENUE (Credit Balance)
    # =========================================================================

    # SaaS Revenue (4000-4099)
    {
        "account_number": "4000",
        "account_name": "SaaS Revenue",
        "account_type": "revenue",
        "account_subtype": "saas_revenue",
        "description": "Parent account for all SaaS revenue",
        "is_system": True,
    },
    {
        "account_number": "4010",
        "account_name": "SaaS Revenue - Subscription",
        "account_type": "revenue",
        "account_subtype": "saas_revenue",
        "description": "Monthly/annual subscription fees",
        "is_system": True,
    },
    {
        "account_number": "4020",
        "account_name": "SaaS Revenue - Usage",
        "account_type": "revenue",
        "account_subtype": "saas_revenue",
        "description": "Per-truck, per-user usage fees",
        "is_system": True,
    },
    {
        "account_number": "4030",
        "account_name": "SaaS Revenue - Add-ons",
        "account_type": "revenue",
        "account_subtype": "saas_revenue",
        "description": "Additional modules (AI Copilot, Banking)",
        "is_system": True,
    },
    {
        "account_number": "4040",
        "account_name": "SaaS Revenue - Enterprise",
        "account_type": "revenue",
        "account_subtype": "saas_revenue",
        "description": "Enterprise tier custom contracts",
        "is_system": False,
    },

    # Service Revenue (4100-4199)
    {
        "account_number": "4100",
        "account_name": "Service Revenue",
        "account_type": "revenue",
        "account_subtype": "service_revenue",
        "description": "Professional services revenue",
        "is_system": True,
    },
    {
        "account_number": "4110",
        "account_name": "Implementation Services",
        "account_type": "revenue",
        "account_subtype": "service_revenue",
        "description": "Onboarding and setup fees",
        "is_system": False,
    },
    {
        "account_number": "4120",
        "account_name": "Training Services",
        "account_type": "revenue",
        "account_subtype": "service_revenue",
        "description": "Customer training fees",
        "is_system": False,
    },
    {
        "account_number": "4130",
        "account_name": "Consulting Services",
        "account_type": "revenue",
        "account_subtype": "service_revenue",
        "description": "Custom development and consulting",
        "is_system": False,
    },

    # Other Revenue (4200-4999)
    {
        "account_number": "4200",
        "account_name": "Interchange Revenue",
        "account_type": "revenue",
        "account_subtype": "other_income",
        "description": "Card transaction interchange fees",
        "is_system": True,
    },
    {
        "account_number": "4300",
        "account_name": "Interest Income",
        "account_type": "revenue",
        "account_subtype": "other_income",
        "description": "Interest earned on deposits",
        "is_system": False,
    },
    {
        "account_number": "4900",
        "account_name": "Other Revenue",
        "account_type": "revenue",
        "account_subtype": "other_income",
        "description": "Miscellaneous revenue",
        "is_system": False,
    },

    # =========================================================================
    # 5000-5999: COST OF GOODS SOLD / COST OF REVENUE (Debit Balance)
    # =========================================================================

    # AI Costs (5000-5099) - Critical for SaaS AI company
    {
        "account_number": "5000",
        "account_name": "Cost of Revenue",
        "account_type": "cost_of_revenue",
        "account_subtype": "ai_compute",
        "description": "Parent account for all COGS",
        "is_system": True,
    },
    {
        "account_number": "5010",
        "account_name": "AI Compute Costs",
        "account_type": "cost_of_revenue",
        "account_subtype": "ai_compute",
        "description": "LLM API costs (OpenAI, Anthropic, Groq)",
        "is_system": True,
    },
    {
        "account_number": "5011",
        "account_name": "AI Compute - OpenAI",
        "account_type": "cost_of_revenue",
        "account_subtype": "ai_compute",
        "description": "OpenAI GPT-4 API costs",
        "is_system": True,
    },
    {
        "account_number": "5012",
        "account_name": "AI Compute - Anthropic",
        "account_type": "cost_of_revenue",
        "account_subtype": "ai_compute",
        "description": "Anthropic Claude API costs",
        "is_system": True,
    },
    {
        "account_number": "5013",
        "account_name": "AI Compute - Groq/Llama",
        "account_type": "cost_of_revenue",
        "account_subtype": "ai_compute",
        "description": "Groq Llama 4 API costs",
        "is_system": True,
    },
    {
        "account_number": "5014",
        "account_name": "AI Compute - AWS Bedrock",
        "account_type": "cost_of_revenue",
        "account_subtype": "ai_compute",
        "description": "AWS Bedrock foundation models",
        "is_system": True,
    },
    {
        "account_number": "5020",
        "account_name": "AI Embeddings & Vector DB",
        "account_type": "cost_of_revenue",
        "account_subtype": "ai_compute",
        "description": "Pinecone, Chroma, embedding costs",
        "is_system": True,
    },

    # Hosting Costs (5100-5199)
    {
        "account_number": "5100",
        "account_name": "Cloud Hosting",
        "account_type": "cost_of_revenue",
        "account_subtype": "hosting",
        "description": "Server and infrastructure costs",
        "is_system": True,
    },
    {
        "account_number": "5110",
        "account_name": "Cloud Hosting - Railway",
        "account_type": "cost_of_revenue",
        "account_subtype": "hosting",
        "description": "Railway deployment costs",
        "is_system": True,
    },
    {
        "account_number": "5120",
        "account_name": "Cloud Hosting - AWS",
        "account_type": "cost_of_revenue",
        "account_subtype": "hosting",
        "description": "AWS EC2, RDS, S3 costs",
        "is_system": True,
    },
    {
        "account_number": "5130",
        "account_name": "Database Hosting",
        "account_type": "cost_of_revenue",
        "account_subtype": "hosting",
        "description": "Supabase, RDS, managed DB costs",
        "is_system": True,
    },
    {
        "account_number": "5140",
        "account_name": "CDN & Bandwidth",
        "account_type": "cost_of_revenue",
        "account_subtype": "hosting",
        "description": "CloudFlare, bandwidth costs",
        "is_system": False,
    },

    # Payment Processing (5200-5299)
    {
        "account_number": "5200",
        "account_name": "Payment Processing Fees",
        "account_type": "cost_of_revenue",
        "account_subtype": "payment_processing",
        "description": "Credit card and ACH fees",
        "is_system": True,
    },
    {
        "account_number": "5210",
        "account_name": "Stripe Fees",
        "account_type": "cost_of_revenue",
        "account_subtype": "payment_processing",
        "description": "Stripe transaction fees (2.9% + $0.30)",
        "is_system": True,
    },
    {
        "account_number": "5220",
        "account_name": "ACH Fees",
        "account_type": "cost_of_revenue",
        "account_subtype": "payment_processing",
        "description": "ACH/bank transfer fees",
        "is_system": True,
    },
    {
        "account_number": "5230",
        "account_name": "Synctera Banking Fees",
        "account_type": "cost_of_revenue",
        "account_subtype": "payment_processing",
        "description": "BaaS platform fees",
        "is_system": True,
    },

    # Third-Party Data (5300-5399)
    {
        "account_number": "5300",
        "account_name": "Data Provider Costs",
        "account_type": "cost_of_revenue",
        "account_subtype": "hosting",
        "description": "Third-party data feeds",
        "is_system": True,
    },
    {
        "account_number": "5310",
        "account_name": "Mapping & Location Data",
        "account_type": "cost_of_revenue",
        "account_subtype": "hosting",
        "description": "Google Maps, HERE, location APIs",
        "is_system": False,
    },
    {
        "account_number": "5320",
        "account_name": "Weather & Traffic Data",
        "account_type": "cost_of_revenue",
        "account_subtype": "hosting",
        "description": "Weather API, traffic data feeds",
        "is_system": False,
    },

    # =========================================================================
    # 6000-6999: OPERATING EXPENSES (Debit Balance)
    # =========================================================================

    # Payroll & Personnel (6000-6199)
    {
        "account_number": "6000",
        "account_name": "Personnel Expenses",
        "account_type": "expense",
        "account_subtype": "payroll",
        "description": "Parent account for all personnel costs",
        "is_system": True,
    },
    {
        "account_number": "6100",
        "account_name": "Salaries & Wages",
        "account_type": "expense",
        "account_subtype": "payroll",
        "description": "Employee salaries (via Check)",
        "is_system": True,
    },
    {
        "account_number": "6110",
        "account_name": "Salaries - Engineering",
        "account_type": "expense",
        "account_subtype": "payroll",
        "description": "Engineering team salaries",
        "is_system": False,
    },
    {
        "account_number": "6120",
        "account_name": "Salaries - Sales",
        "account_type": "expense",
        "account_subtype": "payroll",
        "description": "Sales team salaries",
        "is_system": False,
    },
    {
        "account_number": "6130",
        "account_name": "Salaries - Operations",
        "account_type": "expense",
        "account_subtype": "payroll",
        "description": "Operations team salaries",
        "is_system": False,
    },
    {
        "account_number": "6140",
        "account_name": "Salaries - G&A",
        "account_type": "expense",
        "account_subtype": "payroll",
        "description": "General & admin salaries",
        "is_system": False,
    },
    {
        "account_number": "6150",
        "account_name": "Contractor Payments",
        "account_type": "expense",
        "account_subtype": "payroll",
        "description": "Independent contractor payments",
        "is_system": True,
    },
    {
        "account_number": "6160",
        "account_name": "Payroll Taxes",
        "account_type": "expense",
        "account_subtype": "payroll",
        "description": "Employer payroll tax expense",
        "is_system": True,
    },
    {
        "account_number": "6170",
        "account_name": "Employee Benefits",
        "account_type": "expense",
        "account_subtype": "payroll",
        "description": "Health, dental, vision insurance",
        "is_system": True,
    },
    {
        "account_number": "6180",
        "account_name": "401(k) Match",
        "account_type": "expense",
        "account_subtype": "payroll",
        "description": "Employer 401(k) contributions",
        "is_system": False,
    },
    {
        "account_number": "6190",
        "account_name": "Stock-Based Compensation",
        "account_type": "expense",
        "account_subtype": "payroll",
        "description": "Stock options expense (non-cash)",
        "is_system": False,
    },

    # Marketing & Sales (6200-6299)
    {
        "account_number": "6200",
        "account_name": "Sales & Marketing",
        "account_type": "expense",
        "account_subtype": "marketing",
        "description": "Parent account for S&M expenses",
        "is_system": True,
    },
    {
        "account_number": "6210",
        "account_name": "Advertising",
        "account_type": "expense",
        "account_subtype": "marketing",
        "description": "Google Ads, LinkedIn, paid marketing",
        "is_system": True,
    },
    {
        "account_number": "6220",
        "account_name": "Content Marketing",
        "account_type": "expense",
        "account_subtype": "marketing",
        "description": "Blog, video, content creation",
        "is_system": False,
    },
    {
        "account_number": "6230",
        "account_name": "Events & Conferences",
        "account_type": "expense",
        "account_subtype": "marketing",
        "description": "Trade shows, conferences, events",
        "is_system": False,
    },
    {
        "account_number": "6240",
        "account_name": "Sales Commissions",
        "account_type": "expense",
        "account_subtype": "marketing",
        "description": "Sales rep commissions",
        "is_system": True,
    },
    {
        "account_number": "6250",
        "account_name": "CRM & Sales Tools",
        "account_type": "expense",
        "account_subtype": "marketing",
        "description": "HubSpot, Salesforce, sales software",
        "is_system": False,
    },

    # Software & Tools (6300-6399)
    {
        "account_number": "6300",
        "account_name": "Software Subscriptions",
        "account_type": "expense",
        "account_subtype": "software",
        "description": "SaaS tools and software",
        "is_system": True,
    },
    {
        "account_number": "6310",
        "account_name": "Development Tools",
        "account_type": "expense",
        "account_subtype": "software",
        "description": "GitHub, CI/CD, dev tools",
        "is_system": False,
    },
    {
        "account_number": "6320",
        "account_name": "Productivity Software",
        "account_type": "expense",
        "account_subtype": "software",
        "description": "Slack, Notion, Google Workspace",
        "is_system": False,
    },
    {
        "account_number": "6330",
        "account_name": "Analytics & Monitoring",
        "account_type": "expense",
        "account_subtype": "software",
        "description": "Sentry, Datadog, analytics tools",
        "is_system": False,
    },

    # Professional Services (6400-6499)
    {
        "account_number": "6400",
        "account_name": "Professional Services",
        "account_type": "expense",
        "account_subtype": "professional_services",
        "description": "External professional services",
        "is_system": True,
    },
    {
        "account_number": "6410",
        "account_name": "Legal Fees",
        "account_type": "expense",
        "account_subtype": "professional_services",
        "description": "Legal services and counsel",
        "is_system": True,
    },
    {
        "account_number": "6420",
        "account_name": "Accounting & Audit",
        "account_type": "expense",
        "account_subtype": "professional_services",
        "description": "CPA, audit, tax preparation",
        "is_system": True,
    },
    {
        "account_number": "6430",
        "account_name": "Consulting",
        "account_type": "expense",
        "account_subtype": "professional_services",
        "description": "Business consulting services",
        "is_system": False,
    },
    {
        "account_number": "6440",
        "account_name": "Recruiting",
        "account_type": "expense",
        "account_subtype": "professional_services",
        "description": "Recruiting fees and job boards",
        "is_system": False,
    },

    # Office & Facilities (6500-6599)
    {
        "account_number": "6500",
        "account_name": "Office & Facilities",
        "account_type": "expense",
        "account_subtype": "office",
        "description": "Office-related expenses",
        "is_system": True,
    },
    {
        "account_number": "6510",
        "account_name": "Rent",
        "account_type": "expense",
        "account_subtype": "office",
        "description": "Office rent",
        "is_system": True,
    },
    {
        "account_number": "6520",
        "account_name": "Utilities",
        "account_type": "expense",
        "account_subtype": "office",
        "description": "Electric, internet, phone",
        "is_system": False,
    },
    {
        "account_number": "6530",
        "account_name": "Office Supplies",
        "account_type": "expense",
        "account_subtype": "office",
        "description": "Office supplies and equipment",
        "is_system": False,
    },
    {
        "account_number": "6540",
        "account_name": "Equipment Rental",
        "account_type": "expense",
        "account_subtype": "office",
        "description": "Equipment and furniture leases",
        "is_system": False,
    },

    # Other Operating Expenses (6600-6999)
    {
        "account_number": "6600",
        "account_name": "Insurance",
        "account_type": "expense",
        "account_subtype": "other_expense",
        "description": "Business insurance",
        "is_system": True,
    },
    {
        "account_number": "6610",
        "account_name": "General Liability Insurance",
        "account_type": "expense",
        "account_subtype": "other_expense",
        "description": "General liability coverage",
        "is_system": False,
    },
    {
        "account_number": "6620",
        "account_name": "E&O / Cyber Insurance",
        "account_type": "expense",
        "account_subtype": "other_expense",
        "description": "Errors & omissions, cyber liability",
        "is_system": False,
    },
    {
        "account_number": "6700",
        "account_name": "Travel & Entertainment",
        "account_type": "expense",
        "account_subtype": "other_expense",
        "description": "Business travel and meals",
        "is_system": True,
    },
    {
        "account_number": "6800",
        "account_name": "Bank Charges",
        "account_type": "expense",
        "account_subtype": "other_expense",
        "description": "Bank fees and charges",
        "is_system": True,
    },
    {
        "account_number": "6900",
        "account_name": "Depreciation Expense",
        "account_type": "expense",
        "account_subtype": "other_expense",
        "description": "Asset depreciation",
        "is_system": True,
    },
    {
        "account_number": "6910",
        "account_name": "Bad Debt Expense",
        "account_type": "expense",
        "account_subtype": "other_expense",
        "description": "Uncollectible accounts",
        "is_system": True,
    },
    {
        "account_number": "6990",
        "account_name": "Other Operating Expenses",
        "account_type": "expense",
        "account_subtype": "other_expense",
        "description": "Miscellaneous operating expenses",
        "is_system": False,
    },
]


async def seed_chart_of_accounts(db, gl_manager) -> int:
    """
    Seed the Chart of Accounts with standard SaaS accounts.

    Returns the number of accounts created.
    """
    from app.models.hq_general_ledger import AccountType, AccountSubtype

    created_count = 0

    for account_data in STANDARD_CHART_OF_ACCOUNTS:
        # Check if account already exists
        existing = await gl_manager._get_account_by_number(account_data["account_number"])
        if existing:
            continue

        # Map string types to enums
        account_type = AccountType(account_data["account_type"])
        account_subtype = None
        if account_data.get("account_subtype"):
            account_subtype = AccountSubtype(account_data["account_subtype"])

        await gl_manager.create_account(
            account_number=account_data["account_number"],
            account_name=account_data["account_name"],
            account_type=account_type,
            account_subtype=account_subtype,
            description=account_data.get("description"),
            is_system=account_data.get("is_system", False),
        )
        created_count += 1

    await db.commit()
    return created_count


# ============================================================================
# AI Cost Pricing (for COGS attribution)
# ============================================================================

AI_MODEL_PRICING = {
    # OpenAI pricing per 1K tokens (as of 2024)
    "gpt-4-turbo": {"input": Decimal("0.01"), "output": Decimal("0.03")},
    "gpt-4": {"input": Decimal("0.03"), "output": Decimal("0.06")},
    "gpt-3.5-turbo": {"input": Decimal("0.0005"), "output": Decimal("0.0015")},

    # Anthropic pricing per 1K tokens
    "claude-3-opus": {"input": Decimal("0.015"), "output": Decimal("0.075")},
    "claude-3-sonnet": {"input": Decimal("0.003"), "output": Decimal("0.015")},
    "claude-3-haiku": {"input": Decimal("0.00025"), "output": Decimal("0.00125")},

    # Groq/Llama pricing (much cheaper)
    "llama-3.1-70b": {"input": Decimal("0.00059"), "output": Decimal("0.00079")},
    "llama-3.1-8b": {"input": Decimal("0.00005"), "output": Decimal("0.00008")},
    "llama-4-maverick": {"input": Decimal("0.0003"), "output": Decimal("0.0005")},

    # AWS Bedrock pricing varies by model
    "bedrock-claude-3": {"input": Decimal("0.003"), "output": Decimal("0.015")},
    "bedrock-titan": {"input": Decimal("0.0003"), "output": Decimal("0.0004")},
}


def get_ai_pricing(model: str) -> dict:
    """Get pricing for an AI model."""
    # Try exact match first
    if model in AI_MODEL_PRICING:
        return AI_MODEL_PRICING[model]

    # Try partial match
    model_lower = model.lower()
    for key, pricing in AI_MODEL_PRICING.items():
        if key in model_lower or model_lower in key:
            return pricing

    # Default fallback pricing
    return {"input": Decimal("0.001"), "output": Decimal("0.002")}
