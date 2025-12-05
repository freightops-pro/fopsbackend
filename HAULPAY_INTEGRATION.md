# HaulPay Factoring Integration

## Overview

HaulPay is a **factoring company** that provides cash flow solutions for carriers by purchasing invoices at a discount. This integration enables FreightOps Pro to:

- Submit invoices to HaulPay for factoring
- Receive advance payments (typically 80-95% of invoice value)
- Track factoring status, reserves, and fees
- Manage relationships with debtors (brokers/customers) and carriers
- Automate invoice factoring workflows

This integration follows the [HaulPay Carrier API documentation](https://docs.haulpay.io/carrier-api).

## How Factoring Works

1. **Invoice Submission**: Carrier submits invoice to HaulPay for factoring
2. **Document Upload**: Supporting documents (POD, BOL, etc.) are attached to the invoice
3. **Approval**: HaulPay reviews invoice and documents, then approves
4. **Funding**: HaulPay advances funds (typically 80-95% of invoice value) to carrier
5. **Reserve**: Remaining amount (minus fees) held in reserve
6. **Payment**: Debtor pays HaulPay directly
7. **Reserve Release**: HaulPay releases reserve amount to carrier (minus factoring fees)

**Important**: POD (Proof of Delivery) is typically **required** for factoring approval. Other documents like BOL and rate confirmations help speed up the approval process.

## Features

- **Debtor Management**: Sync and manage relationships with brokers/customers (debtors)
- **Carrier Management**: Sync and manage relationships with carriers
- **Invoice Sync**: Push invoices from FreightOps to HaulPay for payment processing
- **Relationship Mapping**: Maintain external ID mappings between systems
- **Daily Sync**: Automated daily sync of debtor and carrier relationships

## Setup

### 1. Get HaulPay API Key

1. Log into HaulPay dashboard: https://app.haulpay.io
2. Generate an API key
3. Share the API key with your FreightOps integration

### 2. Configure Integration

Create a company integration with:
- **Integration Key**: `haulpay`
- **API Key**: Your HaulPay bearer token
- **Staging**: Set to `true` for testing (uses `api-staging.haulpay.io`)

### 3. Initial Sync

For new clients:
- **Case 1**: Client used FreightOps before, new to HaulPay
  - Send full list of active debtors/carriers to HaulPay using their templates
- **Case 2**: Client used HaulPay before, new to FreightOps
  - Use relationship endpoints to sync all active debtors/carriers

## API Endpoints

### Sync Debtors

```http
POST /api/integrations/haulpay/{integration_id}/sync/debtors
```

Syncs debtor relationships from HaulPay. Should be called daily.

**Response:**
```json
{
  "success": true,
  "data": {
    "created": 5,
    "updated": 12,
    "errors": [],
    "total": 17
  }
}
```

### Sync Carriers

```http
POST /api/integrations/haulpay/{integration_id}/sync/carriers
```

Syncs carrier relationships from HaulPay. Should be called daily.

### Search Debtors

```http
GET /api/integrations/haulpay/{integration_id}/search/debtors?search=Acme
```

Search for debtors in HaulPay when connecting a new customer.

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "debtor-123",
      "name": "Acme Logistics",
      "status": "active",
      ...
    }
  ]
}
```

### Search Carriers

```http
GET /api/integrations/haulpay/{integration_id}/search/carriers?search=ABC&mc=MC123456&dot=1234567
```

Search for carriers by name, MC number, or DOT number.

### Connect Debtor

```http
POST /api/integrations/haulpay/{integration_id}/connect/debtor
Content-Type: application/json

{
  "debtor_id": "debtor-123",
  "customer_id": "customer-uuid"
}
```

Creates a relationship between a FreightOps customer and HaulPay debtor.

### Connect Carrier

```http
POST /api/integrations/haulpay/{integration_id}/connect/carrier
Content-Type: application/json

{
  "carrier_id": "carrier-456",
  "carrier_external_id": "carrier-uuid"
}
```

Creates a relationship between a FreightOps carrier and HaulPay carrier.

### Submit Invoice for Factoring (Single)

```http
POST /api/integrations/haulpay/{integration_id}/submit-invoice
Content-Type: application/json

{
  "invoice_id": "invoice-uuid",
  "debtor_id": "debtor-123",
  "carrier_id": "carrier-456",
  "document_urls": [
    {
      "url": "documents/pod_12345.pdf",
      "document_type": "pod",
      "filename": "POD_Load_12345.pdf"
    },
    {
      "url": "documents/bol_12345.pdf",
      "document_type": "bol",
      "filename": "BOL_Load_12345.pdf"
    }
  ]
}
```

Submits a single invoice to HaulPay for factoring with optional document attachments. 
**POD (Proof of Delivery) is typically required** for factoring approval.

**Document Types:**
- `pod` - Proof of Delivery (usually required)
- `bol` - Bill of Lading
- `rate_confirmation` - Rate confirmation sheet
- `delivery_receipt` - Delivery receipt
- `invoice` - Invoice copy
- `attachment` - Other supporting documents

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "haulpay-invoice-123",
    "status": "submitted",
    "advance_rate": 0.85,
    "advance_amount": 8500.00,
    "reserve_amount": 1500.00,
    "factoring_fee": 150.00,
    "invoice_number": "INV-001"
  }
}
```

### Batch Submit Invoices for Factoring

```http
POST /api/integrations/haulpay/{integration_id}/batch-submit-invoices
Content-Type: application/json

{
  "invoices": [
    {
      "invoice_id": "invoice-uuid-1",
      "debtor_id": "debtor-123",
      "carrier_id": "carrier-456"
    },
    {
      "invoice_id": "invoice-uuid-2",
      "debtor_id": "debtor-123"
    },
    {
      "invoice_id": "invoice-uuid-3",
      "debtor_id": "debtor-456",
      "carrier_id": "carrier-456"
    }
  ]
}
```

Batch submit multiple invoices to HaulPay for factoring. Each invoice is tracked separately with its own status, advance amount, and reserve.

**Response:**
```json
{
  "total": 3,
  "successful": 2,
  "failed": 1,
  "results": [
    {
      "invoice_id": "invoice-uuid-1",
      "success": true,
      "haulpay_invoice_id": "haulpay-invoice-123",
      "status": "submitted",
      "advance_rate": 0.85,
      "advance_amount": 8500.00,
      "reserve_amount": 1500.00,
      "factoring_fee": 150.00,
      "error": null
    },
    {
      "invoice_id": "invoice-uuid-2",
      "success": true,
      "haulpay_invoice_id": "haulpay-invoice-124",
      "status": "submitted",
      "advance_rate": 0.85,
      "advance_amount": 4250.00,
      "reserve_amount": 750.00,
      "factoring_fee": 75.00,
      "error": null
    },
    {
      "invoice_id": "invoice-uuid-3",
      "success": false,
      "haulpay_invoice_id": null,
      "status": null,
      "advance_rate": null,
      "advance_amount": null,
      "reserve_amount": null,
      "factoring_fee": null,
      "error": "Invoice already submitted for factoring"
    }
  ]
}
```

**Features:**
- Each invoice is processed independently
- Partial failures don't stop the batch
- Detailed results for each invoice
- Prevents duplicate submissions
- Tracks each invoice separately in database
- Supports document attachments for each invoice

**Example with Documents:**
```json
{
  "invoices": [
    {
      "invoice_id": "invoice-uuid-1",
      "debtor_id": "debtor-123",
      "carrier_id": "carrier-456",
      "document_urls": [
        {
          "url": "documents/pod_load_001.pdf",
          "document_type": "pod",
          "filename": "POD_Load_001.pdf"
        }
      ]
    }
  ]
}
```

### Get Invoice Factoring Status (by HaulPay ID)

```http
GET /api/integrations/haulpay/{integration_id}/invoice/{haulpay_invoice_id}/status
```

Get the current factoring status of an invoice from HaulPay API, including:
- Status (submitted, approved, funded, paid, reserve_released)
- Advance amount and rate
- Reserve amount
- Factoring fees
- Funding date

### Get Invoice Factoring Tracking (by Internal ID)

```http
GET /api/integrations/haulpay/{integration_id}/invoice/{invoice_id}/tracking
```

Get the stored factoring tracking information for an invoice using your internal invoice ID. This returns the metadata stored in your database, including:
- HaulPay invoice ID
- Submission timestamp
- Current status
- Advance amount and rate
- Reserve amount
- Factoring fees
- Number of documents submitted

**Response:**
```json
{
  "invoice_id": "invoice-uuid-1",
  "invoice_number": "INV-001",
  "factored": true,
  "haulpay_invoice_id": "haulpay-invoice-123",
  "submitted_at": "2024-01-15T10:30:00Z",
  "status": "funded",
  "advance_rate": 0.85,
  "advance_amount": 8500.00,
  "reserve_amount": 1500.00,
  "factoring_fee": 150.00,
  "documents_submitted": 2
}
```

### Upload Document to Existing Invoice

```http
POST /api/integrations/haulpay/{integration_id}/invoice/{haulpay_invoice_id}/upload-document
Content-Type: application/json

{
  "document_url": "documents/pod_12345.pdf",
  "document_type": "pod",
  "filename": "POD_Load_12345.pdf"
}
```

Upload a document to an existing HaulPay invoice. Useful for adding missing documents after initial submission.

### List Factored Invoices

```http
GET /api/integrations/haulpay/{integration_id}/factored-invoices?status=funded
```

List all factored invoices, optionally filtered by status.

## Workflow

### Optimal Workflow for Shared Client

1. **Adding Debtor/Carrier to Load/Invoice**
   - Client searches list of already active debtors/carriers
   - If found, use existing external ID
   - If not found, show "I cannot find my debtor/carrier" option

2. **Adding New Debtor/Carrier**
   - Client provides details (name, MC, DOT)
   - System queries HaulPay's `debtor_list` or `carrier_list`
   - Present results to client with all details
   - Client selects correct debtor/carrier
   - System creates relationship using `POST /debtor_relationships` or `POST /carrier_relationships`
   - Store external ID mapping

3. **If Debtor/Carrier Doesn't Exist in HaulPay**
   - Guide client to HaulPay dashboard to create it
   - Then follow step 2

### Daily Sync

Run daily sync to keep relationships up to date:

```python
# Daily sync job
await sync_debtor_relationships(company_id, external_customer_map)
await sync_carrier_relationships(company_id, external_carrier_map)
```

## Integration Guidelines

As per HaulPay documentation:

1. **Maintain Active Lists**: Keep list of all active debtors/carriers for shared clients
2. **Store External IDs**: Store HaulPay's external ID for each party
3. **Don't Over-Query**: Only query for debtors/carriers actively used by shared clients
4. **Daily Sync**: Query relationship endpoints once per day per client
5. **Manual Updates**: Rare updates to debtors/carriers should be entered manually in both systems

## Authentication

HaulPay uses Bearer token authentication:

```http
Authorization: Bearer {api_key}
```

The API key is stored securely in the `CompanyIntegration.credentials` field.

## Environments

- **Production**: `https://api.haulpay.io/v1/external_api`
- **Staging**: `https://api-staging.haulpay.io/v1/external_api`

Set `staging: true` in integration config to use staging environment.

## Error Handling

All endpoints include comprehensive error handling:
- Invalid API keys return 401
- Missing relationships return 404
- Rate limiting returns 429
- All errors are logged with full context

## Future Enhancements

Based on HaulPay's planned expansions:
- Endpoint to create debtors/carriers directly
- Contract type specification on invoices
- Client properties endpoint
- Bidirectional external ID setting
- Deep links to invoices
- Credit limit exposure for debtors

## Factoring Workflow Examples

### Single Invoice Submission

```python
from app.services.haulpay.haulpay_service import HaulPayService

# Initialize service
service = HaulPayService(db)

# 1. Search for a debtor (broker/customer)
debtors = await service.search_debtors(company_id, search="Acme Logistics")

# 2. Connect customer to debtor (if not already connected)
await service.connect_debtor(
    company_id=company_id,
    debtor_id="debtor-123",
    customer_id="customer-uuid"
)

# 3. Prepare documents (POD is typically required)
document_urls = [
    {
        "url": "documents/pod_load_001.pdf",  # Storage key or URL
        "document_type": "pod",
        "filename": "POD_Load_001.pdf"
    },
    {
        "url": "documents/bol_load_001.pdf",
        "document_type": "bol",
        "filename": "BOL_Load_001.pdf"
    }
]

# 4. Submit invoice for factoring with documents
result = await service.submit_invoice_for_factoring(
    company_id=company_id,
    invoice=invoice,
    debtor_id="debtor-123",
    carrier_id="carrier-456",
    document_urls=document_urls,
)

# Result contains:
# - haulpay_invoice_id: Use this to track the invoice
# - advance_amount: Amount that will be advanced
# - reserve_amount: Amount held in reserve
# - factoring_fee: Fee charged by HaulPay
# - status: Current factoring status

# 4. Check factoring status
status = await service.get_factoring_status(
    company_id=company_id,
    haulpay_invoice_id=result["id"]
)

# Status will show:
# - "submitted": Awaiting approval
# - "approved": Approved, funds will be advanced
# - "funded": Advance funds have been sent
# - "paid": Invoice paid by debtor
# - "reserve_released": Reserve released to carrier
```

### Batch Invoice Submission

```python
from app.services.haulpay.haulpay_service import HaulPayService

# Initialize service
service = HaulPayService(db)

# 1. Prepare batch of invoices to submit with documents
invoice_submissions = [
    {
        "invoice_id": "invoice-uuid-1",
        "debtor_id": "debtor-123",
        "carrier_id": "carrier-456",
        "document_urls": [
            {
                "url": "documents/pod_load_001.pdf",
                "document_type": "pod",
                "filename": "POD_Load_001.pdf"
            }
        ]
    },
    {
        "invoice_id": "invoice-uuid-2",
        "debtor_id": "debtor-123",
        "carrier_id": "carrier-456",
        "document_urls": [
            {
                "url": "documents/pod_load_002.pdf",
                "document_type": "pod",
                "filename": "POD_Load_002.pdf"
            },
            {
                "url": "documents/bol_load_002.pdf",
                "document_type": "bol",
                "filename": "BOL_Load_002.pdf"
            }
        ]
    },
    {
        "invoice_id": "invoice-uuid-3",
        "debtor_id": "debtor-456",
        "carrier_id": "carrier-456"
        # No documents - will submit invoice only
    }
]

# 2. Batch submit all invoices
batch_result = await service.batch_submit_invoices_for_factoring(
    company_id=company_id,
    invoice_submissions=invoice_submissions,
)

# Result contains:
# - total: Total invoices in batch
# - successful: Number successfully submitted
# - failed: Number that failed
# - results: List of results for each invoice

# 3. Process results
for result in batch_result["results"]:
    if result["success"]:
        print(f"Invoice {result['invoice_id']} submitted: {result['haulpay_invoice_id']}")
        print(f"  Advance: ${result['advance_amount']}")
        print(f"  Status: {result['status']}")
    else:
        print(f"Invoice {result['invoice_id']} failed: {result['error']}")

# 4. Track individual invoices
for result in batch_result["results"]:
    if result["success"]:
        tracking = await service.get_invoice_factoring_tracking(
            company_id=company_id,
            invoice_id=result["invoice_id"]
        )
        print(f"Invoice {tracking['invoice_number']}: {tracking['status']}")
```

## Factoring Terms

Typical factoring terms:
- **Advance Rate**: 80-95% of invoice value
- **Factoring Fee**: 1-5% of invoice value
- **Reserve**: Remaining amount minus fees
- **Funding Time**: Usually 24-48 hours after approval
- **Reserve Release**: After invoice is paid by debtor

## Related Documentation

- [HaulPay Carrier API Docs](https://docs.haulpay.io/carrier-api)
- [HaulPay Broker API Docs](https://docs.haulpay.io/broker-api)
- [HaulPay Webhooks](https://docs.haulpay.io/webhooks)

