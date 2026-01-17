"""
Seed the HQ Knowledge Base with domain expertise.

This script populates the knowledge base with comprehensive knowledge
for the HQ AI agents (Oracle, Sentinel, Nexus) in areas of:
- Accounting (GAAP, financial statements, bookkeeping)
- Taxes (payroll taxes, IFTA, quarterly filings)
- HR (hiring, termination, labor laws, benefits)
- Payroll (driver pay, deductions, garnishments)
- Marketing (sales, customer acquisition, retention)
- Compliance (banking, BSA/AML, KYB/KYC)
- Operations (system health, integrations, SaaS metrics)

Usage:
    python scripts/seed_knowledge_base.py
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.services.hq_rag_service import ingest_document
from app.models.hq_knowledge_base import KnowledgeCategory

settings = get_settings()

# =============================================================================
# Knowledge Documents
# =============================================================================

KNOWLEDGE_DOCUMENTS = [
    # ----- ACCOUNTING -----
    {
        "title": "GAAP Principles for SaaS Revenue Recognition (ASC 606)",
        "category": KnowledgeCategory.ACCOUNTING,
        "source": "FASB ASC 606 / GAAP Guidelines",
        "content": """
# Revenue Recognition for SaaS Companies (ASC 606)

## The Five-Step Model

### Step 1: Identify the Contract
A contract exists when:
- Both parties have approved and committed to the contract
- Each party's rights can be identified
- Payment terms can be identified
- The contract has commercial substance
- Collection is probable

For SaaS, this is typically the subscription agreement or Terms of Service acceptance.

### Step 2: Identify Performance Obligations
Common SaaS performance obligations:
- Software access (stand-ready obligation)
- Implementation/onboarding services
- Customer support
- Professional services
- Data storage

**Key Question**: Are these distinct or combined?
- Distinct if customer can benefit from it on its own AND it's separately identifiable

### Step 3: Determine Transaction Price
Include:
- Fixed fees (monthly/annual subscription)
- Variable consideration (usage-based, overages)
- Discounts and rebates

Exclude:
- Amounts collected on behalf of third parties (sales tax)

### Step 4: Allocate Transaction Price
For bundled services:
- Use standalone selling prices (SSP)
- If SSP not available, estimate using:
  - Adjusted market assessment
  - Expected cost plus margin
  - Residual approach (limited use)

### Step 5: Recognize Revenue
For SaaS subscriptions:
- Recognize ratably over the contract period
- Time-based recognition for stand-ready obligations
- Point-in-time for setup fees (if distinct)

## Common SaaS Revenue Scenarios

### Monthly Subscriptions
- Recognize evenly over each month
- Deferred revenue for prepaid periods

### Annual Prepaid Subscriptions
- Cash received upfront
- Recognize 1/12 each month
- Deferred revenue liability decreases monthly

### Usage-Based Billing
- Variable consideration
- Recognize as usage occurs
- May need to estimate for reporting periods

### Implementation Fees
- If distinct: recognize when complete
- If not distinct: defer and recognize with subscription

## Deferred Revenue (Contract Liability)
- Cash received before revenue recognition
- Balance sheet liability
- Decrease as revenue is recognized
- Key metric for SaaS companies

## MRR vs GAAP Revenue
- MRR: Monthly Recurring Revenue (management metric)
- GAAP Revenue: May differ due to:
  - Recognition timing
  - Non-recurring items
  - Revenue allocated to multiple obligations
"""
    },
    {
        "title": "SaaS Financial Statements and Key Metrics",
        "category": KnowledgeCategory.ACCOUNTING,
        "source": "SaaS Finance Best Practices",
        "content": """
# SaaS Financial Statements Guide

## Income Statement (P&L)

### Revenue Categories
1. **Subscription Revenue**: Core SaaS recurring revenue
2. **Professional Services**: Implementation, training, consulting
3. **Other Revenue**: One-time fees, add-ons

### Cost of Revenue (COGS)
- Hosting/infrastructure costs
- Customer support costs
- Payment processing fees
- Third-party software costs
- DevOps personnel (allocated)

### Gross Margin
- Target: 70-80%+ for SaaS
- Formula: (Revenue - COGS) / Revenue
- Below 60% indicates pricing or cost issues

### Operating Expenses
1. **Sales & Marketing (S&M)**
   - Sales team compensation
   - Marketing spend
   - Target: 30-50% of revenue (growth stage)

2. **Research & Development (R&D)**
   - Engineering salaries
   - Product development
   - Target: 15-25% of revenue

3. **General & Administrative (G&A)**
   - Finance, HR, Legal
   - Office expenses
   - Target: 10-15% of revenue

## Key SaaS Metrics

### MRR (Monthly Recurring Revenue)
Components:
- New MRR: From new customers
- Expansion MRR: Upgrades from existing
- Contraction MRR: Downgrades
- Churned MRR: Cancellations

Formula: Sum of all recurring monthly charges

### ARR (Annual Recurring Revenue)
- ARR = MRR × 12
- Preferred for annual contracts
- Don't include one-time fees

### Net Revenue Retention (NRR)
Formula: (Starting MRR + Expansion - Contraction - Churn) / Starting MRR
- Target: >100% (negative net churn)
- World-class: >120%

### Customer Acquisition Cost (CAC)
Formula: (S&M Spend) / (New Customers Acquired)
- Include all S&M costs
- Measure over consistent periods

### LTV (Lifetime Value)
Simple Formula: ARPU × Gross Margin × (1/Churn Rate)
Or: ARPU × Gross Margin × Average Customer Lifetime

### LTV:CAC Ratio
- Target: >3:1
- <3:1 indicates inefficient growth
- >5:1 may indicate underinvestment in growth

### CAC Payback Period
Formula: CAC / (ARPU × Gross Margin)
- Target: <12 months
- Longer means slower capital efficiency

### Rule of 40
Formula: Revenue Growth Rate + Profit Margin >= 40%
- Balances growth and profitability
- Used to benchmark SaaS companies
"""
    },
    # ----- TAXES -----
    {
        "title": "Payroll Tax Compliance Guide",
        "category": KnowledgeCategory.TAXES,
        "source": "IRS / State Tax Agencies",
        "content": """
# Payroll Tax Compliance for SaaS Companies

## Federal Payroll Taxes

### FICA (Social Security + Medicare)
**Social Security (OASDI)**
- Rate: 6.2% employee + 6.2% employer = 12.4% total
- Wage Base (2024): $168,600
- No tax on wages above this amount

**Medicare**
- Rate: 1.45% employee + 1.45% employer = 2.9% total
- No wage base limit
- Additional Medicare: 0.9% on wages over $200,000 (employee only)

### Federal Income Tax Withholding
- Based on W-4 elections
- Use IRS withholding tables
- Deposited with FICA taxes

### Federal Unemployment Tax (FUTA)
- Rate: 6.0% on first $7,000 of wages per employee
- Credit up to 5.4% for state unemployment taxes paid
- Effective rate usually 0.6%

## Deposit Schedules

### Semi-Weekly Depositors
If you reported >$50,000 in taxes during lookback period:
- Wednesday/Thursday/Friday paydays: Deposit by following Wednesday
- Saturday-Tuesday paydays: Deposit by following Friday

### Monthly Depositors
If you reported <=$50,000 in taxes during lookback period:
- Deposit by 15th of following month

### $100,000 Next-Day Rule
If you accumulate $100,000+ in taxes on any day:
- Must deposit by next business day

## Quarterly Filing (Form 941)
Due dates:
- Q1: April 30
- Q2: July 31
- Q3: October 31
- Q4: January 31

Report:
- Wages paid
- Tips reported
- Federal income tax withheld
- Social Security and Medicare taxes
- Adjustments and credits

## State Payroll Taxes

### State Income Tax Withholding
- Varies by state (some states have none)
- Based on state W-4 or federal W-4
- Different withholding methods by state

### State Unemployment Insurance (SUI)
- Employer-paid in most states
- Rates vary by employer experience rating
- Taxable wage base varies by state

### State Disability Insurance (SDI)
- Required in: CA, HI, NJ, NY, RI
- Usually employee-paid via withholding

### Paid Family Leave
- Required in some states
- Employee and/or employer contributions

## Year-End Requirements

### W-2 Forms
- Due to employees: January 31
- Due to SSA: January 31
- Report all wages and withholdings

### W-3 Transmittal
- Summary of all W-2s
- Filed with SSA

### Form 940 (FUTA Annual)
- Due: January 31
- Report annual FUTA tax liability
"""
    },
    {
        "title": "IFTA Fuel Tax Reporting Guide",
        "category": KnowledgeCategory.TAXES,
        "source": "IFTA, Inc. / State Revenue Departments",
        "content": """
# IFTA (International Fuel Tax Agreement) Guide

## What is IFTA?
IFTA is an agreement between US states and Canadian provinces to simplify
fuel tax reporting for motor carriers operating across multiple jurisdictions.

## Who Must File?
Qualified Motor Vehicles:
- Used, designed, or maintained for transportation of persons or property
- Has two axles and gross weight >26,000 lbs, OR
- Has three or more axles regardless of weight, OR
- Is used in combination when weight exceeds 26,000 lbs

## IFTA Concepts

### Base Jurisdiction
- State/province where you are based
- Where you file IFTA returns
- Where you get your IFTA license and decals

### Reporting Period
- Quarterly filing required
- Q1: Jan-Mar (due Apr 30)
- Q2: Apr-Jun (due Jul 31)
- Q3: Jul-Sep (due Oct 31)
- Q4: Oct-Dec (due Jan 31)

## Calculating IFTA Tax

### Step 1: Track Miles by Jurisdiction
For each vehicle, record:
- Total miles traveled
- Miles in each jurisdiction
- Must have supporting documentation (trip sheets, GPS data)

### Step 2: Track Fuel Purchases by Jurisdiction
Record for each purchase:
- Date
- Location (jurisdiction)
- Gallons purchased
- Type of fuel

### Step 3: Calculate Fleet MPG
Formula: Total Miles / Total Gallons = MPG

### Step 4: Calculate Taxable Gallons per Jurisdiction
Formula: Miles in Jurisdiction / Fleet MPG = Taxable Gallons

### Step 5: Calculate Tax Owed/Credit per Jurisdiction
For each jurisdiction:
- Taxable Gallons × Tax Rate = Tax Owed
- Gallons Purchased × Tax Rate = Tax Paid
- Tax Owed - Tax Paid = Net Tax (credit if negative)

### Step 6: Sum All Jurisdictions
- Total all positive amounts (tax owed)
- Total all negative amounts (credits)
- Net = Total Owed - Total Credits

## Record Keeping Requirements

### Distance Records (4 years)
- Trip reports or logs
- Origin and destination
- Routes traveled
- Beginning and ending odometer
- Total miles and miles by jurisdiction

### Fuel Records (4 years)
- Date of purchase
- Seller name and address
- Gallons purchased
- Fuel type
- Unit number or vehicle ID
- Purchase price

## Common Issues

### Jurisdiction Miles vs Total Miles
- Must match exactly
- Unlicensed jurisdictions count toward total

### Inter-state vs Intra-state
- Only inter-jurisdictional travel is IFTA reportable
- Vehicles operating only within one state don't need IFTA

### Fuel Types
- Report separately: diesel, gasoline, propane, LNG, CNG
- Different tax rates apply
"""
    },
    # ----- HR -----
    {
        "title": "Employee Hiring and Onboarding Compliance",
        "category": KnowledgeCategory.HR,
        "source": "DOL / EEOC / State Labor Departments",
        "content": """
# Employee Hiring and Onboarding Compliance

## Pre-Hire Requirements

### Job Postings
- Non-discriminatory language
- Essential job functions
- Pay transparency (required in some states)
- EEO statement

### Application Process
- Consistent screening criteria
- Ban-the-box laws (criminal history timing)
- Salary history bans (some jurisdictions)

### Interviews
- Avoid protected class questions
- Reasonable accommodation for disabilities
- Document all hiring decisions

## New Hire Paperwork

### Form I-9 (Employment Eligibility)
- Complete Section 1: First day of work
- Complete Section 2: Within 3 business days
- Acceptable documents: List A OR (List B + List C)
- E-Verify if required

### Form W-4 (Tax Withholding)
- Employee completes
- Keep on file (don't send to IRS)
- State W-4 may also be required

### State New Hire Reporting
- Report within 20 days of hire (varies by state)
- Required for child support enforcement
- Usually name, SSN, address, hire date

### Direct Deposit Authorization
- Optional but common
- Requires written consent
- Provide paystub access

## Required Notices

### Federal Notices
- FLSA Minimum Wage Poster
- OSHA Job Safety and Health
- EEO Poster
- FMLA Notice (50+ employees)

### State-Specific Notices
- Wage theft prevention act (varies)
- Workers' compensation notice
- State disability/paid leave
- At-will employment notice

## At-Will Employment

### Definition
- Either party can terminate at any time
- For any reason or no reason
- Except for illegal reasons

### Exceptions
- Discrimination (protected classes)
- Retaliation (whistleblower, FMLA, etc.)
- Implied contract (handbooks, policies)
- Public policy violations

## Employee Handbook Requirements
Recommended policies:
- At-will disclaimer
- EEO and anti-harassment
- Leave policies (FMLA, state leaves)
- Wage and hour information
- Discipline procedures
- Technology/social media policies

## Classification Issues

### Employee vs Independent Contractor
IRS 20-Factor Test / ABC Test (state-dependent)
Misclassification penalties:
- Back taxes and penalties
- Unpaid benefits
- State fines
- Lawsuits

### Exempt vs Non-Exempt
Exempt (salaried, no overtime) requires:
- Salary basis: $684/week minimum
- Duties test: Executive, Administrative, Professional, etc.
"""
    },
    {
        "title": "Employee Termination and Final Pay Requirements",
        "category": KnowledgeCategory.HR,
        "source": "DOL / State Labor Departments",
        "content": """
# Employee Termination Compliance

## Termination Types

### Voluntary Resignation
- Employee-initiated
- Request written notice (not required)
- Conduct exit interview
- Document reason for leaving

### Involuntary Termination
- Employer-initiated
- Document performance issues
- Follow progressive discipline (if policy exists)
- Consider discrimination implications

### Layoff/Reduction in Force
- Business necessity
- WARN Act compliance (100+ employees)
- Selection criteria must be non-discriminatory

## Final Pay Requirements by State

### Same Day (Involuntary):
- California, Colorado, Montana

### Within 24-72 Hours:
- Alaska, Arizona, Connecticut, DC, Idaho, Massachusetts, Nevada, Vermont

### Next Scheduled Payday:
- Most other states

### Voluntary Resignation:
- Generally next regular payday
- Some states require earlier

## What to Include in Final Pay
- All hours worked
- Accrued, unused PTO/vacation (if policy/state requires)
- Commissions earned
- Expense reimbursements
- Bonuses (if earned)

## PTO/Vacation Payout

### States Requiring Payout:
California, Colorado, Illinois, Louisiana, Massachusetts, Montana, Nebraska

### States with "Use It or Lose It" Allowed:
Most other states (check specific requirements)

### Policy Considerations:
- Written policy should be clear
- Apply consistently
- Don't cap accruals in "payout required" states

## COBRA Continuation

### Who:
- Employers with 20+ employees
- Medical, dental, vision plans

### What:
- Election notice within 14 days of qualifying event
- 60-day election period
- 18-month coverage (36 for some events)

### Cost:
- Employee pays 102% of premium
- Employer can require payment

## Severance Agreements

### Consideration:
- Must provide something of value
- Beyond what employee is already owed

### OWBPA Requirements (Age 40+):
- 21 days to consider (45 for group)
- 7-day revocation period
- Written in understandable manner
- Advise to consult attorney
- Disclose job titles and ages in group layoff

### What to Include:
- Release of claims
- Confidentiality provisions
- Non-disparagement
- Return of property
- Cooperation clause

## Exit Process Checklist
1. Final pay calculation
2. Benefits termination notice
3. COBRA election notice
4. Return of company property
5. Revoke system access
6. Exit interview (optional)
7. Reference policy communication
8. Update payroll records
9. Report to state (if required for UI)
"""
    },
    # ----- PAYROLL -----
    {
        "title": "Payroll Processing Best Practices",
        "category": KnowledgeCategory.PAYROLL,
        "source": "APA / Industry Best Practices",
        "content": """
# Payroll Processing for SaaS Companies

## Payroll Cycle Options

### Weekly
- Pros: Employees like frequent pay
- Cons: Higher processing costs, more tax deposits

### Bi-Weekly (Every Two Weeks)
- 26 pay periods per year
- Most common in US
- Watch for 3-paycheck months

### Semi-Monthly (15th and Last)
- 24 pay periods per year
- Easier budgeting for salaried employees
- Harder for hourly time calculation

### Monthly
- 12 pay periods
- Lower costs
- May be illegal for some employees (state laws)

## Gross to Net Calculation

### Gross Pay
- Regular hours × hourly rate
- Overtime hours × 1.5 × hourly rate (or 2× in CA after certain hours)
- Salary (divide annual by pay periods)
- Bonuses, commissions

### Pre-Tax Deductions
- 401(k) traditional contributions
- Health insurance premiums (Section 125)
- FSA contributions
- HSA contributions
- Commuter benefits

### Taxable Wages
Gross Pay - Pre-Tax Deductions = Taxable Wages

### Tax Withholdings
- Federal income tax (based on W-4)
- State income tax (based on state W-4)
- Social Security (6.2% up to wage base)
- Medicare (1.45% + 0.9% additional over $200k)
- Local taxes (if applicable)

### Post-Tax Deductions
- Roth 401(k) contributions
- Garnishments (follow priority rules)
- After-tax insurance
- Union dues
- Charitable contributions

### Net Pay
Gross - Pre-Tax - Taxes - Post-Tax = Net Pay

## Garnishment Priority

### Federal Priority Order:
1. Tax levies (IRS, state)
2. Child support
3. Federal student loans
4. Creditor garnishments
5. Voluntary deductions

### Limits:
- Consumer debt: 25% of disposable income
- Child support: Up to 50-65% depending on circumstances
- Tax levies: Based on exemption tables

## Overtime Rules (FLSA)

### Federal:
- Over 40 hours per workweek
- 1.5× regular rate

### California (more restrictive):
- Over 8 hours per day: 1.5×
- Over 12 hours per day: 2×
- 7th consecutive day: 1.5× (first 8 hours), 2× (over 8)

### Regular Rate of Pay
Must include:
- Hourly pay
- Shift differentials
- Non-discretionary bonuses
- Commissions

## Time Tracking Requirements

### FLSA Requirements:
- Day and time workweek begins
- Hours worked each day
- Total hours each workweek
- Regular rate of pay
- Total straight-time earnings
- Total overtime earnings
- Deductions from pay
- Total wages paid
- Pay period dates

### Record Retention:
- 3 years for payroll records
- 2 years for time cards and schedules
"""
    },
    # ----- MARKETING -----
    {
        "title": "SaaS Marketing and Customer Acquisition",
        "category": KnowledgeCategory.MARKETING,
        "source": "SaaS Marketing Best Practices",
        "content": """
# SaaS Marketing Strategy

## The SaaS Marketing Funnel

### Awareness (Top of Funnel)
Goal: Get discovered by potential customers
Channels:
- Content marketing (blog, guides, whitepapers)
- SEO (organic search)
- Social media (LinkedIn, Twitter)
- Paid advertising (Google, LinkedIn, Facebook)
- PR and media coverage
- Podcasts and webinars

### Interest (Middle of Funnel)
Goal: Educate and nurture leads
Tactics:
- Email marketing campaigns
- Free resources (ebooks, templates)
- Webinar registrations
- Product demos
- Free trials
- Case studies

### Decision (Bottom of Funnel)
Goal: Convert leads to customers
Tactics:
- Sales demos
- Free trial support
- ROI calculators
- Competitor comparisons
- Customer testimonials
- Pricing transparency

## Key Marketing Metrics

### Traffic Metrics
- Website visitors (unique and total)
- Traffic sources (organic, paid, referral, direct)
- Bounce rate
- Time on site
- Pages per session

### Lead Metrics
- MQLs (Marketing Qualified Leads)
- SQLs (Sales Qualified Leads)
- Conversion rates (visitor to lead, lead to SQL)
- Lead velocity rate

### Acquisition Metrics
- CAC (Customer Acquisition Cost)
- CAC Payback Period
- Trial-to-paid conversion rate
- Time to close
- Win rate

### Engagement Metrics
- Email open rates (target: 20-25%)
- Click-through rates (target: 2-5%)
- Webinar attendance rates
- Content engagement

## Content Marketing for SaaS

### Blog Strategy
- Educational content (how-to, guides)
- Industry news and trends
- Product updates and features
- Customer success stories
- SEO-optimized posts

### Lead Magnets
- Ebooks and whitepapers
- Industry reports
- Templates and tools
- Checklists
- Video courses

### SEO Focus Areas
- Product keywords (what you do)
- Problem keywords (what customers need)
- Industry keywords (your space)
- Competitor keywords
- Long-tail keywords

## Paid Acquisition Channels

### Google Ads
- Search ads (high intent)
- Display ads (awareness)
- YouTube ads (video)
- Target: Specific keywords, competitors

### LinkedIn Ads
- Sponsored content
- Lead gen forms
- InMail
- Target: Job titles, industries, company size

### Facebook/Instagram
- Better for B2C SaaS
- Lookalike audiences
- Retargeting

## Product-Led Growth (PLG)

### Free Trial
- Time-limited full access
- Credit card required? (higher conversion but fewer trials)
- Length: 7-30 days

### Freemium
- Limited free tier forever
- Upgrade for more features/usage
- Works for viral/network effect products

### PLG Metrics
- Activation rate
- Feature adoption
- Time to value
- PQL (Product Qualified Leads)
- Expansion revenue
"""
    },
    {
        "title": "SaaS Customer Retention and Expansion",
        "category": KnowledgeCategory.MARKETING,
        "source": "Customer Success Best Practices",
        "content": """
# Customer Retention and Expansion Strategies

## Why Retention Matters

### The Math
- Acquiring new customer: 5-25× more expensive than retaining
- 5% increase in retention = 25-95% increase in profits
- NRR >100% means growth without new customers

### Key Metrics
- Gross Revenue Retention (GRR): Target >90%
- Net Revenue Retention (NRR): Target >100%, best-in-class >120%
- Customer Churn Rate: Target <5% annually for SMB, <2% for Enterprise
- Logo Churn vs Revenue Churn

## Identifying At-Risk Customers

### Early Warning Signs
- Decreased login frequency
- Reduced feature usage
- Support ticket volume changes
- NPS score drops
- Payment failures
- Key user departures
- Competitor mentions

### Health Score Components
- Product usage metrics
- Support interactions
- Billing status
- Relationship strength
- Contract value/tenure

## Retention Strategies

### Onboarding Excellence
- Time to First Value (TTFV)
- Activation milestones
- Training and education
- Quick wins early

### Customer Success Programs
- Assigned CSM (for higher tiers)
- Regular check-ins
- Business reviews (QBRs)
- Success plans
- Proactive outreach

### Community Building
- User communities
- Customer advisory boards
- Events and meetups
- Peer networking

### Product Stickiness
- Integrations with other tools
- Data accumulation value
- Workflow dependencies
- Team collaboration features

## Expansion Revenue

### Upsell Strategies
- Feature upgrades
- Tier upgrades
- Seat-based expansion
- Usage-based growth

### Cross-sell Strategies
- Additional products/modules
- Add-on services
- Professional services
- Partner solutions

### Expansion Triggers
- Approaching usage limits
- New use case identified
- Team growth
- Positive sentiment
- Feature requests matching higher tier

## Reducing Churn

### Save Motions
- Downgrade options (vs cancellation)
- Pause subscriptions
- Extended trials
- Discount offers (carefully)
- Executive escalation

### Exit Interview Value
- Understand real reasons
- Identify product gaps
- Competitive intelligence
- Re-engagement opportunities

### Win-Back Campaigns
- Timing: 3-6 months after churn
- Product improvements since departure
- Special offers
- Success stories
"""
    },
    # ----- COMPLIANCE -----
    {
        "title": "BSA/AML Compliance for Fintech SaaS",
        "category": KnowledgeCategory.COMPLIANCE,
        "source": "FinCEN / OCC / FFIEC",
        "content": """
# BSA/AML Compliance Guide

## What is BSA/AML?

### Bank Secrecy Act (BSA)
Federal law requiring financial institutions to:
- Establish AML programs
- File reports on suspicious activity
- Keep records of certain transactions
- Cooperate with law enforcement

### Anti-Money Laundering (AML)
Framework to prevent:
- Money laundering
- Terrorist financing
- Fraud
- Other financial crimes

## AML Program Requirements

### Five Pillars
1. **Written Policies and Procedures**
   - Risk assessment
   - Customer identification
   - Transaction monitoring
   - Reporting procedures

2. **Designated BSA/AML Officer**
   - Responsible for compliance
   - Authority to implement program
   - Direct board/senior management access

3. **Training Program**
   - All relevant employees
   - Annual at minimum
   - Document completion

4. **Independent Testing**
   - Annual audit (internal or external)
   - Scope covers all program elements
   - Findings reported to board

5. **Customer Due Diligence (CDD)**
   - Customer identification
   - Beneficial ownership
   - Risk rating
   - Ongoing monitoring

## Know Your Customer (KYC)

### Customer Identification Program (CIP)
Collect and verify:
- Name
- Date of birth (individuals)
- Address
- Identification number (SSN/EIN)

### Documentary Verification
- Government-issued ID
- Articles of incorporation
- Business licenses

### Non-Documentary Verification
- Credit bureau data
- Public records
- Database verification

## Know Your Business (KYB)

### Business Verification
- Legal entity name and type
- State of incorporation
- Business address
- EIN/Tax ID
- Operating licenses

### Beneficial Ownership
- Individuals owning 25%+ equity
- Control prong (significant management)
- Collect for all beneficial owners:
  - Name
  - DOB
  - Address
  - SSN

## Suspicious Activity Reports (SARs)

### Filing Requirements
File when transaction:
- Involves $5,000+ (or $2,000 for money services)
- And institution knows/suspects:
  - Funds from illegal activity
  - Transaction to hide illegal funds
  - Transaction evades BSA requirements
  - No business or lawful purpose

### Filing Timeline
- File within 30 days of detection
- Can extend to 60 days if suspect unknown
- 90-day filing available in some cases

### Confidentiality
- Cannot disclose SAR filing to subject
- "Tipping off" is illegal
- Safe harbor protections for filers

## Transaction Monitoring

### What to Monitor
- Transaction amounts
- Frequency patterns
- Geographic locations
- Counterparties
- Account behavior changes

### Red Flags
- Structuring (smurfing)
- Rapid movement of funds
- Transactions just below thresholds
- Unusual patterns for customer type
- Third-party payments without explanation
"""
    },
    # ----- OPERATIONS -----
    {
        "title": "SaaS Operations and System Reliability",
        "category": KnowledgeCategory.OPERATIONS,
        "source": "SRE Best Practices",
        "content": """
# SaaS Operations Excellence

## Uptime and SLAs

### Availability Targets
- 99% = 7.31 hours downtime/month
- 99.9% = 43.83 minutes/month
- 99.95% = 21.92 minutes/month
- 99.99% = 4.38 minutes/month

### SLA Components
- Uptime commitment
- Response time guarantees
- Support levels
- Service credits for violations
- Exclusions (maintenance windows, force majeure)

### Calculating Uptime
Formula: ((Total Minutes - Downtime) / Total Minutes) × 100

## Monitoring Strategy

### Infrastructure Metrics
- Server CPU, memory, disk
- Network latency and throughput
- Database performance
- Queue depths

### Application Metrics
- Response times (p50, p95, p99)
- Error rates
- Throughput (requests/second)
- Active users

### Business Metrics
- Transaction success rates
- User registrations
- Revenue processing
- Integration health

## Incident Management

### Severity Levels
**SEV1 (Critical)**
- Complete service outage
- Data loss or security breach
- All hands on deck

**SEV2 (High)**
- Major feature unavailable
- Significant performance degradation
- Dedicated team response

**SEV3 (Medium)**
- Feature partially impaired
- Workaround available
- Normal response queue

**SEV4 (Low)**
- Minor issue
- No user impact
- Scheduled fix

### Incident Response Process
1. **Detection**: Monitoring alert or user report
2. **Triage**: Assess severity and impact
3. **Communication**: Status page, customer notification
4. **Investigation**: Root cause analysis
5. **Resolution**: Fix and verify
6. **Post-mortem**: Document and prevent recurrence

## Integration Health

### Monitoring Third-Party APIs
- Availability checks
- Response time tracking
- Error rate monitoring
- Rate limit tracking
- Authentication health

### Common Integrations to Monitor
- Payment processors (Stripe, etc.)
- Email providers (SendGrid, etc.)
- Storage (AWS S3, etc.)
- Authentication (Auth0, etc.)
- Analytics (Segment, etc.)

### Fallback Strategies
- Graceful degradation
- Queue and retry
- Secondary providers
- Circuit breakers

## Capacity Planning

### Growth Indicators
- User growth rate
- Data growth rate
- Transaction volume trends
- Seasonal patterns

### Scaling Triggers
- CPU consistently >70%
- Memory utilization >80%
- Database connection pool exhaustion
- Queue backlogs increasing

### Scaling Options
- Vertical (bigger instances)
- Horizontal (more instances)
- Database read replicas
- Caching layers
- CDN distribution
"""
    },
]

# =============================================================================
# Main Script
# =============================================================================

async def seed_knowledge_base():
    """Seed the knowledge base with domain documents."""
    print("=" * 60)
    print("HQ Knowledge Base Seeder")
    print("=" * 60)

    # Create database session
    engine = create_async_engine(settings.database_url.replace("postgresql://", "postgresql+asyncpg://"))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        total_docs = len(KNOWLEDGE_DOCUMENTS)
        total_chunks = 0

        for i, doc_data in enumerate(KNOWLEDGE_DOCUMENTS, 1):
            print(f"\n[{i}/{total_docs}] Ingesting: {doc_data['title'][:50]}...")
            print(f"    Category: {doc_data['category'].value}")

            doc = await ingest_document(
                db=db,
                title=doc_data["title"],
                content=doc_data["content"],
                category=doc_data["category"],
                source=doc_data.get("source"),
            )

            if doc:
                # Count chunks created
                from sqlalchemy import select, func
                from app.models.hq_knowledge_base import HQKnowledgeChunk

                result = await db.execute(
                    select(func.count()).select_from(HQKnowledgeChunk).where(
                        HQKnowledgeChunk.document_id == doc.id
                    )
                )
                chunks = result.scalar() or 0
                total_chunks += chunks
                print(f"    ✓ Created {chunks} chunks")
            else:
                print(f"    ✗ Failed to ingest document")

        print("\n" + "=" * 60)
        print(f"COMPLETE: {total_docs} documents, {total_chunks} total chunks")
        print("=" * 60)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_knowledge_base())
