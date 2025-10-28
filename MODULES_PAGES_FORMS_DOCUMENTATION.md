# FreightOps Pro - Modules, Pages & Forms Documentation

## Complete Overview of System Modules, Pages, Forms, and Functions

**Document Version:** 1.0  
**Last Updated:** January 27, 2025  
**Purpose:** Comprehensive reference for all pages, forms, and their functions across the FreightOps Pro platform

---

## Table of Contents

1. [Fleet Management Module](#1-fleet-management-module)
2. [Dispatch Module](#2-dispatch-module)
3. [Accounting Module](#3-accounting-module)
4. [HR & Payroll Module](#4-hr--payroll-module)
5. [Banking Module](#5-banking-module)
6. [Compliance Module](#6-compliance-module)
7. [Billing Module](#7-billing-module)
8. [Customer Management Module](#8-customer-management-module)
9. [Vendor Management Module](#9-vendor-management-module)
10. [Settings Module](#10-settings-module)
11. [Reports Module](#11-reports-module)
12. [Subscription Management Module](#12-subscription-management-module)
13. [HQ Admin Module](#13-hq-admin-module)
14. [Onboarding Module](#14-onboarding-module)
15. [Authentication Pages](#15-authentication-pages)

---

## 1. Fleet Management Module

**Base Route:** `/fleet`

### Pages

#### 1.1 Fleet Overview (`/fleet/overview`)
**Function:** Dashboard view of entire fleet with key metrics and status indicators

**Components:**
- Fleet summary cards (total vehicles, active drivers, maintenance alerts)
- Real-time status dashboard
- Quick action buttons
- Fleet health metrics

**No Forms** - Display only

---

#### 1.2 Vehicle Management (`/fleet/vehicles`)
**Function:** Manage all trucks, trailers, and equipment

**Forms:**

##### Create Vehicle Dialog
- **Fields:**
  - VIN (17 characters, validated)
  - Make
  - Model
  - Year
  - License Plate
  - Type (Truck, Trailer, Other)
  - Status (Active, Maintenance, Out of Service)
  - Current Mileage
  - Purchase Date
  - Purchase Price
- **Function:** Add new vehicles to fleet inventory
- **Component:** `CreateVehicleDialog.tsx`

##### Edit Vehicle Form
- **Fields:** Same as Create Vehicle
- **Function:** Update existing vehicle information
- **Additional Features:**
  - View maintenance history
  - Assign to driver
  - Update status

**Display Tables:**
- Vehicle List Table with filtering and sorting
- Status badges (Active, Maintenance, Out of Service)
- Quick actions (View, Edit, Assign)

---

#### 1.3 Driver Management (`/fleet/drivers`)
**Function:** Manage driver roster, certifications, and compliance

**Forms:**

##### Create Driver Dialog
- **Fields:**
  - First Name
  - Last Name
  - Email
  - Phone Number
  - License Number
  - License State
  - License Expiration Date
  - DOT Physical Expiration
  - Hire Date
  - Employment Status
  - Home Address (Street, City, State, ZIP)
  - Emergency Contact Name
  - Emergency Contact Phone
- **Function:** Add new drivers to the system
- **Component:** `CreateDriverDialog.tsx`

##### Edit Driver Form
- **Fields:** Same as Create Driver
- **Additional Fields:**
  - Current Status (Available, On Load, Off Duty, On Leave)
  - Assigned Vehicle
  - ELD Hours Tracking
  - Performance Metrics
- **Function:** Update driver information and status

**Display Tables:**
- Active Drivers List
- Driver Status Dashboard
- Certification/Compliance Tracking

---

#### 1.4 Live Tracking (`/fleet/tracking`)
**Function:** Real-time GPS tracking of vehicles and drivers

**Components:**
- Interactive map with vehicle markers
- Driver location pins
- Route visualization
- Geofence monitoring
- Dual location tracking (Truck GPS + Driver Mobile GPS)

**Map Filters:**
- Show/Hide Truck GPS (Asset Tracking)
- Show/Hide Driver GPS (Load Tracking)
- Filter by status
- Filter by region

**No Forms** - Display and monitoring only

---

#### 1.5 Maintenance Management (`/fleet/maintenance`)
**Function:** Schedule and track vehicle maintenance

**Forms:**

##### Create Maintenance Record
- **Fields:**
  - Vehicle Selection (Dropdown)
  - Maintenance Type (Oil Change, Tire Rotation, DOT Inspection, etc.)
  - Service Date
  - Service Provider
  - Odometer Reading
  - Cost
  - Parts Replaced
  - Labor Hours
  - Next Service Due Date
  - Next Service Due Mileage
  - Notes
- **Function:** Log maintenance activities
- **Triggers:** Automatic alerts for upcoming maintenance

##### Schedule Maintenance Form
- **Fields:**
  - Vehicle
  - Maintenance Type
  - Scheduled Date
  - Service Location
  - Estimated Cost
  - Priority (Low, Medium, High)
  - Notify Driver (Yes/No)
- **Function:** Plan future maintenance activities

**Display Components:**
- Maintenance Calendar
- Upcoming Maintenance Alerts
- Maintenance History Timeline
- Cost Analytics Dashboard

---

#### 1.6 Compliance Management (`/fleet/compliance`)
**Function:** Track DOT, FMCSA, and safety compliance

**Forms:**

##### Add Compliance Item Dialog
- **Fields:**
  - Compliance Type (DOT, FMCSA, Safety, Insurance, Other)
  - Item Description
  - Entity Type (Company, Driver, Vehicle)
  - Entity Selection
  - Due Date
  - Status (Compliant, Warning, Expired)
  - Document Upload
  - Reminder Settings
- **Function:** Track compliance requirements
- **Component:** `AddComplianceItemDialog.tsx`

##### ELD Compliance Form
- **Fields:**
  - Driver Selection
  - ELD Device ID
  - Hours of Service Status
  - Violations (if any)
  - Certification Date
- **Function:** Monitor ELD compliance
- **Component:** `AddELDComplianceForm.tsx`

##### Insurance Policy Form
- **Fields:**
  - Policy Type (Liability, Cargo, Physical Damage)
  - Policy Number
  - Provider
  - Effective Date
  - Expiration Date
  - Coverage Amount
  - Premium Amount
  - Document Upload
- **Function:** Track insurance policies
- **Component:** `AddInsurancePolicyForm.tsx`

##### Permit Book Form
- **Fields:**
  - Permit Type (IRP, IFTA, Overweight, etc.)
  - Jurisdiction
  - Permit Number
  - Effective Date
  - Expiration Date
  - Cost
  - Renewal Date
- **Function:** Track permits and registrations
- **Component:** `AddPermitBookForm.tsx`

##### SAFER Data Form
- **Fields:**
  - Carrier Name
  - MC Number
  - DOT Number
  - SAFER Score
  - Last Audit Date
  - Violations Count
  - Out of Service Rate
- **Function:** Track FMCSA SAFER data
- **Component:** `AddSAFERDataForm.tsx`

---

## 2. Dispatch Module

**Base Route:** `/dispatch`

### Pages

#### 2.1 Dispatch Overview (`/dispatch`)
**Function:** Main dispatch dashboard with load overview and scheduling

**Display Components:**
- Total Loads Counter
- Pending/Assigned/In-Transit/Delivered Counters
- Available Loads List
- Available Drivers List
- Live Location Map (Dual GPS Tracking)
- Quick Actions Panel
- Recent Activity Feed
- Loads by Date Calendar
- Unscheduled Loads Section

**Forms:**

##### Create Load Modal (Multi-Tab)
**Tab 1: Manual Entry**
- **Uses Component:** `UnifiedLoadCreationForm.tsx`
- **Fields:**
  - Customer Name/Selection
  - Load Type (FTL, LTL, Intermodal, Drayage)
  - Commodity
  - Base Rate
  - Pickup Location (Address, City, State, ZIP)
  - Delivery Location (Address, City, State, ZIP)
  - Pickup Date/Time
  - Delivery Date/Time
  - Special Instructions
  - Accessorial Charges (Fuel, Lumper, Detention, etc.)
  - Multi-Stop Builder (Add unlimited stops)
  - Dispatch Leg Assignment
- **Function:** Create new loads with multiple stops and legs
- **Advanced Features:**
  - Multi-stop sequencing
  - Automatic leg generation
  - Driver/truck assignment per leg
  - Rate calculation with accessorials

**Tab 2: Rate Confirmation Upload**
- **Fields:**
  - File Upload (PDF, JPG, PNG)
  - OCR Processing (Automatic extraction)
  - Billing Method (Direct, Broker, Factoring)
  - Payment Terms (Net 15, 30, 45, COD)
  - Auto-populated fields from OCR
- **Function:** Create loads from rate confirmation documents with AI-powered OCR

**Tab 3: Bulk Upload Spreadsheet**
- **Fields:**
  - CSV/Excel File Upload
  - Column Mapping
  - Validation Preview
- **Function:** Import multiple loads from spreadsheet
- **Note:** Redirects to Load Management for full functionality

##### Load Assignment/Edit Modal
- **Fields:**
  - Assigned Driver (Dropdown with availability status)
  - Assigned Truck (Dropdown with status)
  - Pickup Time
  - Delivery Time
  - Dispatch Notes
  - Priority (Normal, High, Urgent)
- **Function:** Assign loads to drivers and trucks
- **Real-time Features:**
  - Collaboration warnings (who else is viewing)
  - ELD hours verification
  - Admin override capability

**Interactive Features:**
- Drag-and-drop load scheduling to timeline
- Real-time load status updates
- Multi-location selector
- Authority view switcher

---

#### 2.2 Load Management (`/dispatch/load-management`)
**Function:** Advanced load management with filtering and bulk operations

**Display Components:**
- **Core Tier:** `CoreLoadsTable` - Basic load listing
- **Professional/Enterprise Tier:** `ProfessionalLoadsTable` - Advanced features
- Advanced Filter System
- Bulk operations toolbar

**Forms:**

##### Advanced Filter System
- **Fields:**
  - Status (Multiple select)
  - Date Range
  - Customer
  - Origin State/City
  - Destination State/City
  - Load Type
  - Priority Level
  - Assigned Driver
  - Assigned Truck
- **Function:** Complex filtering of loads
- **Component:** `AdvancedFilterSystem.tsx`

##### Bulk Upload Form
- **Fields:**
  - CSV Template Download
  - File Upload
  - Field Mapping
  - Validation Results
  - Error Handling
- **Function:** Import multiple loads at once
- **Component:** `BulkUploadSpreadsheet.tsx`

**Table Actions:**
- View Details
- Edit Load
- Assign Driver/Truck
- Cancel Load
- Duplicate Load
- Print BOL
- Export Selected

---

#### 2.3 Dispatch Scheduling (`/dispatch/scheduling`)
**Function:** Calendar-based load scheduling and planning

**Display Components:**
- Full Calendar View
- Timeline View (6 AM - 10 PM)
- Driver Availability Grid
- Truck Availability Grid
- Continuous Timeline with drag-and-drop

**Forms:**

##### Schedule Load Form
- **Fields:**
  - Load Selection
  - Driver Assignment
  - Truck Assignment
  - Scheduled Pickup Time
  - Scheduled Delivery Time
  - Route Planning
  - Estimated Miles
  - Estimated Duration
- **Function:** Schedule loads with precision timing
- **Component:** `UnifiedDispatchCalendar.tsx`

**Interactive Features:**
- Drag loads to time slots
- Visual conflict detection
- Auto-calculate drive times
- Multi-day planning

---

#### 2.4 Driver Management (`/dispatch/drivers`)
**Function:** Dispatch-focused driver management and availability

**Display Components:**
- Driver Roster with Real-time Status
- ELD Hours of Service Monitoring
- Driver Performance Metrics
- Active Load Assignments

**Forms:**

##### Quick Driver Status Update
- **Fields:**
  - Driver Selection
  - Status (Available, On Load, Off Duty, Unavailable)
  - Location Update
  - Notes
- **Function:** Update driver availability quickly
- **Component:** `DispatchDriverManagement.tsx`

**Display Tables:**
- Available Drivers
- Drivers On Load
- Off-Duty Drivers
- Hours of Service Violations

---

#### 2.5 Customer Quick Creation (`/dispatch/customers`)
**Function:** Rapid customer creation from dispatch screen

**Forms:**

##### Quick Customer Creator
- **Fields:**
  - Company Name
  - Contact Name
  - Email
  - Phone
  - Billing Address
  - MC Number (optional)
  - DOT Number (optional)
  - Payment Terms
  - Credit Limit
- **Function:** Add customers on-the-fly during load creation
- **Component:** `DispatchCustomerCreator.tsx`
- **Integration:** Immediately available in dispatch and accounting modules

**Display Components:**
- Recent Customers List
- Quick access to full customer management

---

#### 2.6 Dispatch Reports (`/dispatch/reports`)
**Function:** Dispatch performance metrics and reporting

**Display Metrics:**
- Total Loads (Current Period)
- Active Drivers Count
- On-Time Delivery Rate
- Daily Summary Statistics

**Available Reports:**
- Driver Performance Report
- On-Time Delivery Report
- Load Volume Report
- Revenue by Lane Report

**No Forms** - Report generation and viewing only

---

## 3. Accounting Module

**Base Route:** `/accounting`

### Module Structure
- **Core Tier:** `BasicReports`, `Invoices`, `Settlements`
- **Professional Tier:** `AdvancedReports`, `Collections`, `CreditManagement`, `FinancialCalculator`
- **Enterprise Tier:** `CustomerAnalytics`, `ProfitabilityAnalysis`, `EnterpriseAccounting`

### Pages

#### 3.1 Accounting Management (`/accounting/accounting-management`)
**Function:** Customer and vendor management hub

**Tabs:**
1. **Customers Tab**
2. **Vendors Tab**

**Forms:**

##### Add Customer Dialog
- **Fields:**
  - Customer Type (Shipper, Broker, Receiver)
  - Company Name
  - Contact Person Name
  - Email
  - Phone
  - Street Address
  - City
  - State
  - ZIP Code
  - MC Number
  - DOT Number
  - Credit Limit
  - Payment Terms (Net 15, 30, 45, 60)
  - Status (Active, Inactive, Suspended)
- **Function:** Add new customers to accounting system
- **Auto-sync:** Available immediately in dispatch module

##### Edit Customer Form
- **Fields:** Same as Add Customer
- **Additional Fields:**
  - Current Balance
  - Total Loads Completed
  - Average Rate per Mile
  - Payment History
  - Credit Notes
- **Function:** Update customer information and credit terms

##### Add Vendor Dialog
- **Fields:**
  - Vendor Type (Fuel Provider, Equipment Provider, Maintenance Provider, Service Provider, Insurance Provider)
  - Company Name
  - Contact Person Name
  - Email
  - Phone
  - Street Address
  - City
  - State
  - ZIP Code
  - Services Provided (Multi-select: Fuel, Fleet Cards, Fuel Management, Truck Leasing, Maintenance, Parts, etc.)
  - Payment Terms
  - Account Number
  - Status (Active, Inactive)
- **Function:** Add vendors for expense tracking

##### Edit Vendor Form
- **Fields:** Same as Add Vendor
- **Additional Fields:**
  - Current Balance Owed
  - Total Spent (Lifetime)
  - Last Payment Date
  - Last Payment Amount
  - Payment History
- **Function:** Update vendor information and track spending

**Display Tables:**
- Customer List with Credit Status
- Vendor List with Payment Status
- Aging Reports
- Credit Limit Tracking

---

#### 3.2 Invoice Management (`/accounting/invoice-management`)
**Function:** Create, send, and track invoices

**Forms:**

##### Create Invoice Form
- **Fields:**
  - Customer Selection (Dropdown)
  - Invoice Date
  - Due Date
  - Payment Terms
  - Load Selection (Link to loads)
  - Line Items:
    - Description
    - Quantity
    - Unit Price
    - Amount
  - Subtotal (Auto-calculated)
  - Tax Rate
  - Tax Amount (Auto-calculated)
  - Additional Charges (Fuel surcharge, Detention, etc.)
  - Total Amount (Auto-calculated)
  - Notes
  - Payment Instructions
- **Function:** Generate invoices for completed loads
- **Auto-features:**
  - Pull load details automatically
  - Calculate totals with tax
  - Generate invoice number
  - Email to customer option

##### Edit Invoice Form
- **Fields:** Same as Create Invoice
- **Additional Options:**
  - Void Invoice
  - Mark as Paid
  - Send Reminder
  - Apply Payment
  - Generate Credit Memo
- **Function:** Modify existing invoices

##### Quick Payment Form
- **Fields:**
  - Invoice Number
  - Payment Amount
  - Payment Method (Cash, Check, ACH, Wire, Credit Card)
  - Payment Date
  - Reference Number
  - Notes
- **Function:** Record payments received

**Display Components:**
- Invoice List (Pending, Paid, Overdue)
- Invoice Status Dashboard
- Aging Report (30, 60, 90+ days)

---

#### 3.3 Comprehensive Accounting (`/accounting/comprehensive-accounting`)
**Function:** Full accounting dashboard with P&L, balance sheet, and cash flow

**Display Components:**
- Profit & Loss Statement
- Balance Sheet
- Cash Flow Statement
- Revenue Charts
- Expense Categories
- Profitability Metrics

**Forms:**

##### Quick Expense Entry
- **Fields:**
  - Expense Category (Fuel, Payroll, Maintenance, Insurance, Equipment, Other)
  - Vendor
  - Amount
  - Date
  - Payment Method
  - Description
  - Receipt Upload
- **Function:** Log expenses quickly

##### Journal Entry Form
- **Fields:**
  - Entry Date
  - Account Debits (Multi-line)
  - Account Credits (Multi-line)
  - Description
  - Reference Number
- **Function:** Manual accounting adjustments

**Reports Available:**
- Monthly P&L
- Quarterly Reports
- Annual Tax Summary
- 1099 Reports
- Mileage Tax Reports (IFTA)

---

#### 3.4 Customers Page (`/accounting/customers`)
**Function:** Detailed customer management and credit analysis

**Forms:**

##### Advanced Customer Search
- **Fields:**
  - Name
  - MC Number
  - Credit Status
  - Payment Terms
  - Outstanding Balance Range
- **Function:** Search and filter customers

##### Credit Limit Adjustment Form
- **Fields:**
  - Customer Selection
  - Current Credit Limit
  - Requested New Limit
  - Justification
  - Approval Status
  - Effective Date
- **Function:** Manage customer credit limits
- **Workflow:** Requires approval for increases

**Display Components:**
- Customer Profitability Analysis
- Payment History Timeline
- Credit Utilization Charts
- Outstanding Invoice Summary

---

## 4. HR & Payroll Module

**Base Route:** `/hr`

### Pages

#### 4.1 HR Overview Dashboard (`/hr/hr-overview-dashboard`)
**Function:** HR metrics and employee summary

**Display Components:**
- Total Employees Count
- Active/Inactive Status
- Department Breakdown
- Recent Hires
- Pending Tasks (Onboarding, Reviews, Documents)

**No Forms** - Dashboard only

---

#### 4.2 Employee Management (`/hr/hr-employees`)
**Function:** Employee roster and directory

**Forms:**

##### Add Employee Dialog
- **Fields:**
  - Employee ID (Auto-generated or manual)
  - First Name
  - Last Name
  - Email (Company email)
  - Personal Email
  - Phone Number
  - Date of Birth
  - Social Security Number (Encrypted)
  - Hire Date
  - Department (Operations, Finance, HR, IT, Admin)
  - Position/Title
  - Role (Operations Manager, Financial Analyst, HR Manager, Admin)
  - Employment Type (Full-time, Part-time, Contract)
  - Salary/Hourly Rate
  - Pay Frequency (Weekly, Bi-weekly, Monthly)
  - Home Address (Street, City, State, ZIP)
  - Emergency Contact Name
  - Emergency Contact Phone
  - Emergency Contact Relationship
- **Function:** Onboard new employees
- **Integration:** Syncs with Gusto for payroll setup

##### Edit Employee Form
- **Fields:** Same as Add Employee
- **Additional Options:**
  - Activate/Deactivate Status
  - Update Compensation
  - Change Department/Role
  - Add Performance Notes
  - Document Upload (I-9, W-4, Direct Deposit Form)
- **Function:** Update employee records

**Display Components:**
- Employee Directory
- Organizational Chart
- Employee Status Dashboard
- Quick Actions (Edit, View Profile, Deactivate)

---

#### 4.3 Payroll Module (`/hr/payroll-module`)
**Function:** Payroll processing and management

**Forms:**

##### Run Payroll Form
- **Fields:**
  - Pay Period Start Date
  - Pay Period End Date
  - Payment Date
  - Employee Selection (Multi-select or All)
  - Regular Hours (Per employee)
  - Overtime Hours
  - Bonuses
  - Deductions
  - Reimbursements
  - Review Summary
- **Function:** Process payroll for selected period
- **Integration:** Gusto API for actual payment processing

##### Payroll Adjustment Form
- **Fields:**
  - Employee Selection
  - Adjustment Type (Bonus, Reimbursement, Correction, Deduction)
  - Amount
  - Reason
  - Effective Pay Period
- **Function:** Make payroll corrections and additions

---

#### 4.4 Gusto-Style Payroll (`/hr/gusto-style-payroll`)
**Function:** Embedded Gusto payroll interface

**Embedded Components:**
- Gusto Payroll Dashboard (iframe or embedded component)
- Direct access to Gusto features
- Synced employee data

**No Forms** - Uses Gusto's native forms

---

#### 4.5 Payroll Automation (`/hr/payroll-automation`)
**Function:** Automated payroll rules and scheduling

**Forms:**

##### Auto-Payroll Rule Setup
- **Fields:**
  - Rule Name
  - Schedule (Weekly, Bi-weekly, Monthly)
  - Auto-run Date
  - Employee Group
  - Default Hours
  - Auto-approve Threshold
  - Notification Settings
- **Function:** Set up automatic payroll processing

##### Payroll Schedule Form
- **Fields:**
  - Pay Frequency
  - First Pay Date
  - Pay Day of Week/Month
  - Holiday Handling
  - Banking Delay Days
- **Function:** Configure payroll schedule

---

#### 4.6 Payroll Banking Setup (`/hr/payroll-banking-setup`)
**Function:** Link bank accounts for payroll funding

**Forms:**

##### Add Bank Account Form
- **Fields:**
  - Bank Name
  - Account Type (Checking, Savings)
  - Routing Number
  - Account Number (Confirm)
  - Account Verification Method (Micro-deposits, Instant)
  - Primary/Secondary designation
- **Function:** Connect bank accounts for payroll
- **Security:** Encrypted storage, verification required

---

#### 4.7 HR Benefits (`/hr/hr-benefits`)
**Function:** Employee benefits management

**Forms:**

##### Benefits Enrollment Form
- **Fields:**
  - Employee Selection
  - Benefit Plan Type (Health, Dental, Vision, 401k, etc.)
  - Plan Selection
  - Coverage Level (Employee only, Employee + Spouse, Family)
  - Effective Date
  - Employee Contribution
  - Employer Contribution
  - Beneficiaries
  - Waiver Option (if declining)
- **Function:** Enroll employees in benefits
- **Component:** Full page at `/hr/benefits-enrollment`

##### Edit Benefits Form
- **Fields:** Same as Enrollment
- **Additional Options:**
  - Life Event Changes
  - Coverage Cancellation
  - Dependent Addition/Removal
- **Function:** Modify existing benefits

---

#### 4.8 Benefits Enrollment Page (`/hr/benefits-enrollment`)
**Function:** Detailed benefits enrollment process

**Forms:**
- Multi-step wizard for benefits selection
- Plan comparison tools
- Cost calculators
- Dependent information collection

---

#### 4.9 HR Documents (`/hr/hr-documents`)
**Function:** Employee document management

**Forms:**

##### Upload Document Form
- **Fields:**
  - Employee Selection
  - Document Type (I-9, W-4, W-2, 1099, Contract, Performance Review, Handbook Acknowledgment, etc.)
  - Document Title
  - File Upload (PDF, DOC, JPG, PNG)
  - Expiration Date (if applicable)
  - Requires Signature (Yes/No)
  - Notes
- **Function:** Store employee documents
- **Security:** Encrypted storage, access logging

##### Document Request Form
- **Fields:**
  - Employee Selection
  - Document Type Requested
  - Due Date
  - Instructions
  - Notification Method
- **Function:** Request documents from employees

**Display Components:**
- Document Library by Employee
- Expiration Alerts
- Missing Documents Report

---

#### 4.10 HR Onboarding (`/hr/hr-onboarding`)
**Function:** New hire onboarding workflow

**Forms:**

##### Onboarding Checklist
- **Items:**
  - Personal Information Collected
  - I-9 Form Completed
  - W-4 Form Completed
  - Direct Deposit Setup
  - Benefits Enrollment
  - Handbook Acknowledgment
  - Equipment Assignment (laptop, phone, etc.)
  - System Access Provisioned
  - Training Completed
- **Function:** Track onboarding progress
- **Features:**
  - Task assignment
  - Automated reminders
  - Progress tracking

---

#### 4.11 Payroll Forms (`/hr/payroll-forms`)
**Function:** Generate and manage tax forms

**Forms:**

##### Generate W-2 Form
- **Fields:**
  - Tax Year
  - Employee Selection (Multi-select or All)
  - Generate Preview
  - E-file to IRS (checkbox)
  - Email to Employees (checkbox)
- **Function:** Create W-2 forms for employees

##### Generate 1099 Form
- **Fields:**
  - Tax Year
  - Contractor Selection
  - Form Type (1099-NEC, 1099-MISC)
  - Generate Preview
  - E-file to IRS
  - Email to Contractors
- **Function:** Create 1099 forms for contractors

**Available Forms:**
- W-2 (Employee wage statements)
- 1099-NEC (Contractor payments)
- 941 (Quarterly payroll tax)
- 940 (Annual unemployment tax)

---

#### 4.12 Employee Profile (`/hr/employee-profile`)
**Function:** Individual employee detail view

**Display Sections:**
- Personal Information
- Employment Details
- Compensation History
- Benefits Overview
- Time Off Balance
- Performance Reviews
- Documents
- Payroll History

**Forms:**
- Edit any section of employee profile
- Request time off (employee portal)
- Update direct deposit

---

## 5. Banking Module

**Base Route:** `/banking`

### Pages

#### 5.1 Banking Overview (`/banking`)
**Function:** Main banking dashboard

**Display Components:**
- Account Overview (All linked accounts)
  - Operating Account Balance
  - Reserve Account Balance
  - Fuel Card Account Balance
  - Equipment Finance Balance
- Quick Actions Panel
  - Send Money
  - View Activity
  - View Statements
  - Manage Cards
- Recent Activity (Last 5 transactions)
- Expense Categories with Pie Chart
  - Fuel
  - Payroll
  - Maintenance
  - Insurance
  - Equipment
  - Other
- QuickPay Favorites
- Pending & Scheduled Transactions

**No Forms** - Links to specific banking functions

---

#### 5.2 Banking Accounts (`/banking/accounts`)
**Function:** View and manage all bank accounts

**Display Components:**
- Account List with Balances
- Account Details (Number, Type, Status)
- Transaction History per Account

**Forms:**

##### Add Bank Account Form
- **Fields:**
  - Account Nickname
  - Bank Name
  - Account Type (Checking, Savings, Credit, Loan)
  - Routing Number
  - Account Number (Confirm)
  - Balance (Initial)
  - Currency (USD default)
- **Function:** Link external bank accounts

---

#### 5.3 Banking Activity (`/banking/activity`)
**Function:** Detailed transaction history

**Display Components:**
- Full Transaction List
- Filter Options (Date range, Type, Amount range)
- Search Transactions
- Export to CSV/PDF

**Forms:**

##### Filter Transactions
- **Fields:**
  - Date Range (From/To)
  - Transaction Type (All, Deposits, Withdrawals, Transfers, Fees)
  - Amount Range (Min/Max)
  - Status (Completed, Pending, Failed)
  - Account Filter
- **Function:** Filter transaction history

**Transaction Details:**
- Date/Time
- Description
- Category
- Amount (Credit/Debit)
- Balance After
- Status Badge

---

#### 5.4 Banking Transactions (`/banking/transactions`)
**Function:** Similar to Activity page with additional filtering

**Forms:** Same as Banking Activity page

---

#### 5.5 Banking Send Money (`/banking/send-money`)
**Function:** Initiate payments and transfers

**Forms:**

##### Send Money Form
- **Fields:**
  - From Account (Dropdown)
  - To (Saved Payee or New Payee)
  - Payment Type (ACH, Wire Transfer, Check, Internal Transfer)
  - Amount
  - Payment Date (Immediate or Schedule)
  - Memo/Description
  - Category (Bill Payment, Vendor Payment, Payroll, Transfer)
  - Repeat Payment (One-time, Weekly, Monthly, Custom)
- **Function:** Send money to vendors, drivers, or transfer between accounts

##### Add Payee Form
- **Fields:**
  - Payee Type (Individual, Business, Vendor)
  - Payee Name
  - Email (optional)
  - Bank Name
  - Routing Number
  - Account Number
  - Account Type
  - Nickname
  - Default Amount (optional)
  - Category
- **Function:** Save frequent payment recipients

**Display Components:**
- Saved Payees List
- Recent Transfers
- Scheduled Payments
- QuickPay favorites

---

#### 5.6 Banking Cards (`/banking/cards`)
**Function:** Manage debit/credit cards and fuel cards

**Display Components:**
- Card List with Status
- Card Details (Last 4 digits, Type, Expiration)
- Transaction History per Card
- Spending Limits

**Forms:**

##### Request New Card Form
- **Fields:**
  - Card Type (Debit, Credit, Fuel)
  - Cardholder Name
  - Shipping Address
  - Spending Limit (optional)
  - Linked Account
  - Card Purpose/Notes
- **Function:** Order new physical or virtual cards

##### Manage Card Form
- **Fields:**
  - Card Selection
  - Action (Lock, Unlock, Report Lost/Stolen, Cancel)
  - Spending Limit Adjustment
  - Transaction Alerts (On/Off)
  - PIN Change
- **Function:** Control card settings

##### Card Spending Controls
- **Fields:**
  - Daily Limit
  - Transaction Limit
  - Merchant Categories Allowed (Fuel stations, Maintenance, etc.)
  - Geographic Restrictions
  - Time-based Controls
- **Function:** Set card usage rules

---

#### 5.7 Banking Statements (`/banking/statements`)
**Function:** View and download bank statements

**Display Components:**
- Statement List (Monthly)
- Statement Date Range
- Download Options (PDF, CSV)

**Forms:**

##### Request Statement
- **Fields:**
  - Account Selection
  - Statement Period (Monthly, Quarterly, Annual, Custom Date Range)
  - Format (PDF, CSV, Excel)
  - Delivery Method (Download, Email)
- **Function:** Generate custom statements

**Available Statements:**
- Monthly Bank Statements
- Transaction Reports
- Tax Year Summary
- Reconciliation Reports

---

#### 5.8 Banking Transfers (`/banking/transfers`)
**Function:** Transfer money between accounts

**Forms:**

##### Internal Transfer Form
- **Fields:**
  - From Account
  - To Account
  - Amount
  - Transfer Date (Immediate or Schedule)
  - Frequency (One-time, Recurring)
  - Memo
- **Function:** Move money between own accounts

##### Schedule Recurring Transfer
- **Fields:**
  - From Account
  - To Account
  - Amount
  - Start Date
  - Frequency (Weekly, Bi-weekly, Monthly)
  - End Date (or # of transfers)
  - Auto-approval rules
- **Function:** Set up automatic transfers

---

#### 5.9 Banking Support (`/banking/support`)
**Function:** Banking help and support

**Display Components:**
- FAQ Section
- Contact Support Form
- Live Chat (if available)
- Banking Documents
- Tutorial Videos

**Forms:**

##### Support Request Form
- **Fields:**
  - Issue Category (Account Access, Transactions, Cards, Technical, Other)
  - Subject
  - Description
  - Priority (Low, Normal, High, Urgent)
  - Attachments (Screenshots, documents)
  - Preferred Contact Method
- **Function:** Submit support tickets

---

#### 5.10 Banking Activate (`/banking/activate`)
**Function:** Activate Railsr embedded banking

**Forms:**

##### Banking Activation Form
- **Fields:**
  - Company Legal Name
  - EIN/Tax ID
  - Business Address
  - Business Type
  - Authorized Signer Name
  - Authorized Signer DOB
  - Authorized Signer SSN (Encrypted)
  - Beneficial Owners Information
  - Agree to Terms & Conditions
- **Function:** Complete KYC/KYB for banking services
- **Process:**
  1. Submit application
  2. Identity verification
  3. Account approval
  4. Funding setup

---

#### 5.11 Banking Account Info (`/banking/banking-account-info`)
**Function:** Detailed account information and settings

**Display Sections:**
- Account Holder Details
- Account Numbers
- Routing Information
- Account Status
- Linked Services
- Security Settings

**Forms:**

##### Update Account Settings
- **Fields:**
  - Account Nickname
  - Email Notifications (On/Off)
  - SMS Alerts (On/Off)
  - Low Balance Alert Threshold
  - Large Transaction Alert Threshold
  - Statement Delivery Preference
- **Function:** Configure account preferences

---

## 6. Compliance Module

**Base Route:** `/compliance`

### Pages

#### 6.1 Compliance Overview (`/compliance`)
**Function:** Compliance dashboard and monitoring

**Display Metrics:**
- Compliance Score (Percentage)
- Compliant Items Count
- Warnings Count
- Violations Count
- Due This Week Count

**Forms:**

##### Add Compliance Record Dialog
- **Fields:**
  - Type (DOT, Safety, FMCSA, Driver, Vehicle)
  - Priority (High, Medium, Low)
  - Title
  - Description
  - Due Date
  - Entity Type (Company, Driver, Vehicle)
  - Entity Selection (If applicable)
  - Status (Compliant, Warning, Violation, Expired)
  - Document Upload
  - Reminder Settings
- **Function:** Track compliance requirements
- **Triggers:** Automatic alerts when approaching due date

**Display Tabs:**
1. **ELD Logbooks Compliance**
   - ELD device tracking
   - Hours of Service violations
   - Driver logbook status

2. **SAFER Data**
   - FMCSA Safety Score
   - Inspection results
   - Crash history
   - Violation history

3. **Insurance**
   - Policy tracking
   - Coverage verification
   - Expiration alerts

4. **Permit Books**
   - IRP Registration
   - IFTA License
   - Overweight Permits
   - State-specific permits

---

#### 6.2 Compliance Management (`/compliance/ComplianceManagement`)
**Function:** Detailed compliance item management

**Forms:**

##### Edit Compliance Record
- **Fields:** Same as Add Compliance Record
- **Additional Options:**
  - Mark as Complete
  - Extend Due Date
  - Add Notes/Comments
  - Upload Supporting Documents
  - Assign Responsible Party
- **Function:** Update compliance status

**Display Tables:**
- All Compliance Records
- Filtered Views (By Type, Status, Entity)
- Upcoming Deadlines
- Expired Items

---

## 7. Billing Module

**Base Route:** `/billing`

### Pages

#### 7.1 Billing Overview (`/billing`)
**Function:** Billing dashboard with financial summary

**Display Metrics:**
- Total Revenue (Paid invoices)
- Pending Amount (Unpaid invoices)
- Paid Invoices Count
- Overdue Invoices Count
- Payment Rate Percentage

**Display Components:**
- Revenue Statistics Cards
- Recent Activity Feed
- Quick Links to Sub-pages

**No Forms** - Dashboard with navigation

---

#### 7.2 Invoice Management (`/billing/invoices`)
**Function:** Comprehensive invoice management

**Display Metrics:**
- Total Invoices
- Pending Count
- Paid Count
- Overdue Count

**Forms:**

##### Create Invoice (via modal)
- **Fields:**
  - Customer Selection
  - Invoice Number (Auto-generated)
  - Invoice Date
  - Due Date
  - Load Reference (Optional link to load)
  - Line Items (Multi-row):
    - Description
    - Quantity
    - Unit Price
    - Amount
  - Subtotal (Auto-calculated)
  - Tax Rate
  - Tax Amount (Auto-calculated)
  - Total (Auto-calculated)
  - Payment Terms
  - Notes
- **Function:** Generate invoices for customers
- **Actions:** Save as Draft, Send to Customer, Mark as Paid

**Display Table:**
- Invoice List with status badges
- Filters (Status, Date range, Customer)
- Actions (View, Edit, Send, Void)

---

#### 7.3 Customer Management (`/billing/customers`)
**Function:** Customer billing information and credit management

**Display Metrics:**
- Total Customers
- Active Customers
- Customers with Outstanding Balances

**Forms:**

##### Customer Credit Terms
- **Fields:**
  - Customer Selection
  - Credit Limit
  - Payment Terms (Net 15, 30, 45, 60)
  - Credit Status (Good Standing, Warning, On Hold)
  - Credit Notes
- **Function:** Manage customer credit

**Display Table:**
- Customer Directory
- Credit Limit vs Current Balance
- Outstanding Invoices
- Payment History

---

#### 7.4 Payment Processing (`/billing/payments`)
**Function:** Track and process customer payments

**Display Metrics:**
- Total Received (All-time)
- Pending Payments
- This Month's Payments

**Forms:**

##### Record Payment
- **Fields:**
  - Customer Selection
  - Invoice(s) to Apply Payment
  - Payment Amount
  - Payment Method (Check, ACH, Wire, Credit Card, Cash)
  - Payment Date
  - Reference/Check Number
  - Bank Account (if electronic)
  - Notes
- **Function:** Apply customer payments to invoices

##### Payment Request
- **Fields:**
  - Customer Selection
  - Invoice Selection
  - Request Amount
  - Due Date
  - Payment Instructions
  - Send via Email (checkbox)
- **Function:** Request payment from customers

**Display Table:**
- Recent Payments
- Payment Method Breakdown
- Payment Status (Completed, Pending, Failed)
- Filters and Export Options

---

#### 7.5 Billing Reports (`/billing/reports`)
**Function:** Financial reporting and analytics

**Available Reports:**
- Aging Report (30/60/90 days)
- Revenue by Customer
- Revenue by Month
- Outstanding Invoices
- Payment Collection Rate
- Bad Debt Report

**Forms:**

##### Custom Report Generator
- **Fields:**
  - Report Type (Dropdown)
  - Date Range
  - Customer Filter
  - Status Filter
  - Format (PDF, Excel, CSV)
- **Function:** Generate custom financial reports

---

## 8. Customer Management Module

**Base Route:** `/customers` (within Accounting module)

### Pages

#### 8.1 Customers (`/accounting/customers`)
**Function:** Comprehensive customer relationship management

**Covered in Accounting Module Section 3.4** - See above for details

**Additional Features:**
- Customer Portal Access (view invoices, make payments)
- Customer Notes/History
- Communication Log
- Customer Segmentation (Platinum, Gold, Silver)

---

## 9. Vendor Management Module

**Base Route:** `/vendors` (within Accounting module)

### Pages

#### 9.1 Vendors (`/vendors`)
**Function:** Vendor relationship and expense management

**Forms:**

##### Add Vendor (Detailed)
- **Fields:**
  - Vendor Type (Fuel, Maintenance, Equipment, Insurance, Professional Services)
  - Company Name
  - Contact Name
  - Email
  - Phone
  - Billing Address (Street, City, State, ZIP)
  - Tax ID/EIN
  - Payment Terms
  - Preferred Payment Method (Check, ACH, Wire)
  - Account Number (Our account with them)
  - Services Provided (Multi-select)
  - Notes
- **Function:** Add vendor to system

##### Vendor Bill/Expense Entry
- **Fields:**
  - Vendor Selection
  - Bill Date
  - Due Date
  - Bill Number
  - Amount
  - Category (Fuel, Maintenance, Parts, etc.)
  - Related Vehicle (if applicable)
  - Related Driver (if applicable)
  - Receipt/Invoice Upload
  - Payment Status (Unpaid, Scheduled, Paid)
  - Notes
- **Function:** Record vendor bills and expenses

**Display Tables:**
- Vendor Directory
- Outstanding Bills
- Payment History
- Spending by Category
- Vendor Performance Ratings

---

## 10. Settings Module

**Base Route:** `/settings`

### Pages

#### 10.1 Company Settings
**Function:** Configure company profile and preferences

**Forms:**

##### Company Profile Form
- **Fields:**
  - Company Legal Name
  - DBA Name
  - MC Number
  - DOT Number
  - SCAC Code
  - EIN/Tax ID
  - Business Address (Street, City, State, ZIP)
  - Mailing Address (if different)
  - Phone Number
  - Email
  - Website
  - Company Logo Upload
  - Timezone
  - Currency
- **Function:** Update company information

##### Business Hours Form
- **Fields:**
  - Operating Days (Monday-Sunday checkboxes)
  - Business Hours (Open time, Close time per day)
  - Holiday Schedule
  - Emergency Contact
- **Function:** Set business hours

---

#### 10.2 User Management
**Function:** Manage user accounts and permissions

**Forms:**

##### Add User Form
- **Fields:**
  - First Name
  - Last Name
  - Email
  - Phone
  - Role (Admin, Dispatcher, Accountant, Manager, Driver, Viewer)
  - Department
  - Permissions (Checkboxes for module access)
  - Status (Active, Inactive)
  - Send Welcome Email (checkbox)
- **Function:** Create user accounts

##### Edit User Permissions
- **Fields:**
  - User Selection
  - Role Assignment
  - Module Access (Checkboxes):
    - Fleet Management
    - Dispatch
    - Accounting
    - HR
    - Banking
    - Compliance
    - Billing
    - Reports
    - Settings
  - Specific Permissions (View, Edit, Delete, Approve)
- **Function:** Control user access

---

#### 10.3 Integration Settings
**Sub-route:** `/settings/integrations`

**Function:** Configure third-party integrations

**Forms:**

##### Gusto Integration Setup
- **Fields:**
  - API Key
  - Company ID
  - Authorization Code
  - Enable Sync (checkbox)
  - Sync Frequency
- **Function:** Connect Gusto for payroll

##### Stripe Integration Setup
- **Fields:**
  - Publishable Key
  - Secret Key
  - Webhook URL
  - Enable Test Mode (checkbox)
- **Function:** Connect Stripe for payments

##### Railsr Banking Setup
- **Fields:**
  - API Key
  - Environment (Sandbox, Production)
  - Authorized User
  - Webhook Configuration
- **Function:** Connect Railsr for embedded banking

##### Port Credentials (`/settings/integrations/PortCredentials`)
- **Function:** Manage API credentials for port/facility access
- **Fields:**
  - Port Name
  - API Key
  - Username
  - Password (Encrypted)
  - Access Level
  - Expiration Date

---

#### 10.4 Notification Settings
**Function:** Configure email and SMS notifications

**Forms:**

##### Notification Preferences
- **Fields:**
  - Load Updates (Email, SMS, In-app)
  - Payment Received (Email, SMS)
  - Invoice Sent (Email)
  - Compliance Alerts (Email, SMS)
  - Driver Check-in (Email, SMS)
  - Maintenance Due (Email)
  - Low Balance Alert (Email, SMS)
  - Report Generation Complete (Email)
  - Frequency (Real-time, Daily Digest, Weekly Summary)
- **Function:** Control notification delivery

---

#### 10.5 Billing & Subscription Settings
**Function:** Manage subscription plan and billing

**Forms:**

##### Upgrade Plan
- **Fields:**
  - Current Plan Display (Core, Professional, Enterprise)
  - New Plan Selection
  - Billing Cycle (Monthly, Annual)
  - Payment Method
  - Promo Code (optional)
- **Function:** Change subscription tier

##### Payment Method Update
- **Fields:**
  - Card Number
  - Expiration Date
  - CVV
  - Billing ZIP Code
  - Cardholder Name
- **Function:** Update payment method for subscription

**Display Components:**
- Current Plan Details
- Usage Metrics
- Billing History
- Invoice Downloads

---

## 11. Reports Module

**Base Route:** `/reports`

### Pages

#### 11.1 Reports Overview (`/reports`)
**Function:** Central reporting hub

**Available Report Categories:**

##### 11.1.1 Fleet Reports
- Vehicle Utilization Report
- Maintenance Cost Report
- Fuel Efficiency Report
- Driver Performance Report
- Hours of Service Report
- Vehicle Inspection Report

##### 11.1.2 Financial Reports
- Profit & Loss Statement
- Revenue by Customer
- Revenue by Lane
- Expense Report by Category
- Invoice Aging Report
- Cash Flow Statement
- Balance Sheet
- Tax Reports (1099, W-2, IFTA)

##### 11.1.3 Operational Reports
- Load Count by Status
- On-Time Delivery Report
- Late Deliveries Report
- Driver Utilization Report
- Idle Time Report
- Route Efficiency Report

##### 11.1.4 Compliance Reports
- DOT Compliance Status
- FMCSA Safety Report
- Driver Qualification Files
- Vehicle Compliance Report
- Insurance Expiration Report

**Forms:**

##### Custom Report Builder
- **Fields:**
  - Report Type (Dropdown)
  - Date Range (From/To or predefined: This Week, This Month, This Quarter, This Year, Custom)
  - Filters:
    - Customer
    - Driver
    - Vehicle
    - Status
    - Region
    - Department
  - Group By (Day, Week, Month, Quarter, Year)
  - Sort By
  - Format (PDF, Excel, CSV, Print)
  - Schedule Report (One-time or Recurring)
  - Email to Recipients
- **Function:** Generate custom reports

##### Schedule Report
- **Fields:**
  - Report Template
  - Frequency (Daily, Weekly, Monthly, Quarterly)
  - Day/Time to Generate
  - Email Recipients (Multi-select or email addresses)
  - Format
  - Filters Applied
- **Function:** Automate report generation

**Display Components:**
- Report Library (Saved reports)
- Scheduled Reports List
- Recent Reports
- Report Templates

---

## 12. Subscription Management Module

**Base Route:** `/subscriptions` (embedded throughout app)

### Components

#### 12.1 Subscription Plans Display
**Component:** `SubscriptionPlans.tsx`

**Function:** Display available subscription tiers

**Plans:**
- **Core ($99/month)**
  - Basic dispatch
  - Up to 5 users
  - 10 vehicles
  - Basic reports

- **Professional ($199/month)**
  - Advanced dispatch
  - Up to 25 users
  - 50 vehicles
  - Advanced reporting
  - Collections management
  - Credit management

- **Enterprise ($399/month)**
  - Unlimited users
  - Unlimited vehicles
  - Custom integrations
  - Dedicated support
  - Advanced analytics
  - Multi-location support

---

#### 12.2 Subscription Management
**Component:** `SubscriptionManagement.tsx`

**Forms:**

##### Upgrade Subscription
- **Fields:**
  - Current Plan Display
  - Target Plan Selection
  - Billing Frequency (Monthly, Annual with discount)
  - Payment Method Selection
  - Promo Code Input
  - Agree to Terms
- **Function:** Upgrade/downgrade subscription tier

##### Cancel Subscription
- **Fields:**
  - Reason for Cancellation (Dropdown)
  - Additional Feedback
  - Effective Date (Immediate or End of Period)
  - Data Export Request
- **Function:** Cancel subscription

---

#### 12.3 Feature Gate
**Component:** `FeatureGate.tsx`

**Function:** Control access to features based on subscription tier

**No Forms** - Displays upgrade prompts when accessing restricted features

---

#### 12.4 Upgrade Prompt
**Component:** `UpgradePrompt.tsx`

**Function:** Encourage upgrades when limits reached

**Displayed When:**
- User limit reached
- Vehicle limit reached
- Feature not available in current tier

**Action:** Redirect to subscription upgrade flow

---

#### 12.5 Billing History
**Component:** `BillingHistory.tsx`

**Function:** Display past subscription invoices

**Display:**
- Invoice Date
- Amount
- Status (Paid, Failed)
- Download PDF
- Payment Method Used

---

## 13. HQ Admin Module

**Base Route:** `/hq`

**Function:** Super-admin portal for FreightOps HQ to manage all tenant companies

### Pages

#### 13.1 HQ Admin Dashboard (`/hq/hq-admin`)
**Function:** Overview of all tenant companies

**Display Metrics:**
- Total Companies
- Active Subscriptions
- Revenue Metrics
- Support Tickets
- System Health

**No Forms** - Dashboard with links

---

#### 13.2 HQ Banking Admin (`/hq/hq-banking-admin`)
**Function:** Manage banking operations across all tenants

**Forms:**

##### Banking KYB Review
- **Fields:**
  - Company Selection
  - KYB Status (Pending, Approved, Rejected)
  - Verification Documents Review
  - Approval/Rejection Reason
  - Notes
- **Function:** Review and approve banking applications

**Display:**
- Pending Banking Applications
- Active Banking Accounts
- Transaction Volume by Company
- Banking Compliance Status

---

#### 13.3 HQ Login (`/hq/hq-login`)
**Function:** HQ staff authentication

**Forms:**

##### HQ Login Form
- **Fields:**
  - Email
  - Password
  - Two-Factor Authentication Code
- **Function:** Secure HQ access

---

#### 13.4 HQ Register (`/hq/hq-register`)
**Function:** Add new HQ staff members

**Forms:**

##### HQ Staff Registration
- **Fields:**
  - First Name
  - Last Name
  - Email
  - Phone
  - Role (Super Admin, Support, Financial Analyst, Technical Support)
  - Access Level
  - Department
- **Function:** Onboard HQ staff

---

## 14. Onboarding Module

**Base Route:** `/onboarding`

**Function:** New customer onboarding workflow

### Pages

#### 14.1 Welcome Screen (`/onboarding/Welcome`)
**Function:** Greeting and overview of onboarding process

**Display:**
- Welcome message
- Onboarding steps overview
- Estimated time to complete
- Support contact information

**Actions:**
- Begin Setup button
- Skip for Now option (limited functionality)

---

#### 14.2 Company Setup (`/onboarding/CompanySetup`)
**Function:** Initial company configuration

**Forms:**

##### Company Information Form
- **Fields:**
  - Company Legal Name
  - MC Number
  - DOT Number
  - Business Address (Street, City, State, ZIP)
  - Phone
  - Email
  - Number of Trucks
  - Number of Drivers
  - Primary Business Type (Dry Van, Reefer, Flatbed, Specialized)
- **Function:** Collect company details

##### Primary User Setup
- **Fields:**
  - First Name
  - Last Name
  - Position/Title
  - Email (Will be login email)
  - Phone
  - Set Password
  - Confirm Password
- **Function:** Create admin user account

##### Subscription Selection
- **Fields:**
  - Plan Selection (Core, Professional, Enterprise)
  - Billing Cycle (Monthly, Annual)
  - Payment Method
  - Promo Code (optional)
- **Function:** Choose subscription plan

**Multi-Step Process:**
1. Company Details
2. Admin User Setup
3. Subscription Selection
4. Payment Information
5. Confirmation

---

## 15. Authentication Pages

**Base Routes:** `/login`, `/register`, `/activation`

### Pages

#### 15.1 Login Page (`/login`)
**Function:** User authentication

**Forms:**

##### Login Form
- **Fields:**
  - Email
  - Password
  - Remember Me (checkbox)
- **Function:** Authenticate users
- **Security:** JWT token generation

**Actions:**
- Login button
- Forgot Password link
- Don't have an account? Register link

---

#### 15.2 Registration Page (`/register`)
**Function:** New company registration

**Forms:**

##### Company Registration Form
- **Fields:**
  - Company Name
  - Contact Name
  - Email
  - Phone
  - MC Number (optional at this stage)
  - DOT Number (optional)
  - Password
  - Confirm Password
  - Agree to Terms & Conditions (checkbox)
  - Agree to Privacy Policy (checkbox)
- **Function:** Create new tenant account
- **Flow:** Registration → Email Verification → Onboarding

---

#### 15.3 Activation Page (`/activation`)
**Function:** Email verification after registration

**Forms:**

##### Email Verification
- **Fields:**
  - Verification Code (6 digits)
  - OR: Click activation link from email
- **Function:** Verify email address

**Actions:**
- Activate Account button
- Resend Verification Email link

---

## Additional Shared Components & Forms

### Global Components Used Across Modules

#### Load Detail Page (`/load/:loadId`)
**Function:** Comprehensive load information display

**Display Sections:**
- Load Number and Status
- Customer Information
- Pickup and Delivery Locations
- Assigned Driver and Truck
- Timeline (Pickup → In Transit → Delivery)
- Documents (BOL, POD, Rate Confirmation)
- Financial Details (Rate, Accessorials, Total)
- Notes and Special Instructions
- Status History

**Forms:**

##### Update Load Status
- **Fields:**
  - Status Selection (Assigned, In Transit, At Pickup, At Delivery, Delivered, Cancelled)
  - Update Time
  - Location (GPS or manual)
  - Notes
  - Photo Upload (optional)
- **Function:** Update load progress

##### Upload Document
- **Fields:**
  - Document Type (BOL, POD, Rate Confirmation, Weight Ticket, Other)
  - File Upload
  - Notes
- **Function:** Attach documents to load

---

#### Dashboard Components

##### Core Dashboard (`/dashboard`)
**Tier:** Core Plan
**Function:** Basic dashboard with essential KPIs

**Display:**
- Active Loads Count
- Available Drivers Count
- Fleet Status
- Today's Schedule
- Quick Actions

##### Professional Dashboard (`/dashboard`)
**Tier:** Professional Plan
**Function:** Enhanced dashboard with advanced analytics

**Additional Display:**
- Revenue Charts
- Profit Margins
- Customer Analytics
- Driver Performance Scores
- Predictive Alerts

##### Enterprise Dashboard (`/dashboard`)
**Tier:** Enterprise Plan
**Function:** Full-featured dashboard with AI insights

**Additional Display:**
- Multi-location Dashboard
- Custom Widgets
- Real-time Collaboration
- Advanced Business Intelligence
- Custom Reports

---

#### Universal Forms/Dialogs

##### Global Search Bar
- **Fields:**
  - Search Query
  - Filter by Type (Loads, Customers, Drivers, Vehicles, Invoices)
- **Function:** Search across entire platform

##### User Profile Form
- **Fields:**
  - Profile Photo Upload
  - First Name
  - Last Name
  - Email
  - Phone
  - Timezone
  - Notification Preferences
  - Change Password
  - Two-Factor Authentication Setup
- **Function:** Manage user account

##### Feedback/Support Form
- **Fields:**
  - Feedback Type (Bug Report, Feature Request, General Feedback)
  - Subject
  - Description
  - Attachments
  - Priority
- **Function:** Submit feedback to support

---

## Summary Statistics

### Total Counts

**Modules:** 13 main modules + 2 admin modules

**Pages:** 75+ distinct pages

**Forms:** 100+ unique forms

**Functions by Category:**
- **Fleet Management:** 15 forms
- **Dispatch:** 12 forms
- **Accounting:** 18 forms
- **HR & Payroll:** 16 forms
- **Banking:** 14 forms
- **Compliance:** 6 forms
- **Billing:** 10 forms
- **Settings:** 9 forms
- **Reports:** 3 custom builders
- **Authentication:** 5 forms
- **Miscellaneous:** 12 forms

---

## Module Function Summary

| Module | Primary Function | Key Forms |
|--------|------------------|-----------|
| **Fleet** | Vehicle & driver management, maintenance tracking | Create Vehicle, Create Driver, Maintenance Records, Compliance Items |
| **Dispatch** | Load management, driver assignment, scheduling | Create Load, Assign Load, Schedule Load, Quick Customer Creator |
| **Accounting** | Financial management, invoicing, customer/vendor management | Create Invoice, Add Customer, Add Vendor, Payment Entry |
| **HR & Payroll** | Employee management, payroll processing, benefits | Add Employee, Run Payroll, Benefits Enrollment, Generate Tax Forms |
| **Banking** | Embedded banking, transactions, payments, cards | Send Money, Add Bank Account, Manage Cards, Record Transactions |
| **Compliance** | DOT/FMCSA compliance, safety tracking, certifications | Add Compliance Record, ELD Tracking, Insurance Tracking, Permit Management |
| **Billing** | Invoice generation, payment tracking, customer billing | Create Invoice, Record Payment, Credit Management |
| **Customers** | Customer relationship management, credit terms | Add Customer, Edit Credit Terms, Customer Portal |
| **Vendors** | Vendor management, expense tracking | Add Vendor, Vendor Bill Entry |
| **Settings** | System configuration, integrations, user management | Company Profile, Add User, Integration Setup, Notification Preferences |
| **Reports** | Business intelligence, financial reporting, analytics | Custom Report Builder, Schedule Reports |
| **Subscriptions** | Plan management, billing, feature gates | Upgrade Plan, Cancel Subscription |
| **Onboarding** | New customer setup, initial configuration | Company Setup, Primary User Setup, Subscription Selection |

---

## Technology Stack Reference

**Frontend Framework:** React 18 with TypeScript (Vite)

**UI Components:** Radix UI + shadcn/ui

**Forms:** React Hook Form + Zod validation

**State Management:** TanStack React Query

**Routing:** Wouter

**Styling:** Tailwind CSS

**Backend:** FastAPI (Python)

**Database:** PostgreSQL with SQLAlchemy ORM

**Authentication:** JWT tokens with bcrypt

**Integrations:**
- Gusto (Payroll)
- Stripe (Subscriptions)
- Railsr (Banking)
- Google Cloud Vision (OCR)

---

## Document Maintenance

**This document should be updated when:**
- New modules are added
- New pages are created
- Forms are modified or added
- Features change based on subscription tier
- Integration capabilities expand

**Last Review Date:** January 27, 2025

**Next Scheduled Review:** February 27, 2025

---

## Appendix: Form Validation Standards

All forms in FreightOps Pro follow these validation standards:

**Required Fields:**
- Clearly marked with asterisk (*)
- Cannot submit until filled

**Email Validation:**
- Valid email format
- Unique where required (user accounts)

**Phone Validation:**
- US phone format preferred
- International formats accepted
- Validation with formatting

**Financial Fields:**
- Positive numbers only (unless specifically allowing negatives)
- Two decimal places for currency
- Currency symbol formatting

**Date Fields:**
- Date picker with calendar
- Date range validation (start before end)
- No past dates where not applicable

**File Uploads:**
- Supported formats clearly indicated
- File size limits enforced
- Virus scanning on upload
- Preview capability where applicable

**Security Fields (SSN, Account Numbers):**
- Encrypted at rest
- Masked in display (***-**-1234)
- Access logging
- PCI DSS compliance for payment data

---

**End of Document**

*This comprehensive documentation provides a complete reference for all modules, pages, forms, and their functions within the FreightOps Pro platform.*

