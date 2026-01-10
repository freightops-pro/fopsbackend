# Compliance API Guide

## Overview

The Compliance API provides endpoints for validating loads, generating shipping documents, validating payments, and assigning drivers according to regional freight regulations.

The API automatically routes requests to the appropriate compliance engine based on the company's `operating_region` field.

## Base URL

```
/api/compliance
```

All endpoints are prefixed with `/api/compliance` and are tagged as `Compliance` in the OpenAPI documentation.

## Authentication

All endpoints require authentication. Include your JWT token in the Authorization header:

```
Authorization: Bearer <your-token>
```

## Endpoints

### 1. Validate Load Before Dispatch

**POST** `/api/compliance/validate-load`

Validates that a load can be dispatched under regional regulations.

**Request Body:**
```json
{
  "company_id": "company-uuid",
  "load_data": {
    "origin": "Los Angeles, CA",
    "destination": "Phoenix, AZ",
    "weight_kg": 10000,
    "is_interstate": true
  }
}
```

**Response:**
```json
{
  "status": "VALID",
  "message": "US DOT compliance validation complete",
  "errors": [],
  "warnings": ["MC number recommended for for-hire operations"],
  "details": null
}
```

**Status Values:**
- `VALID` - Load can be dispatched
- `WARNING` - Load can be dispatched but has warnings
- `ERROR` - Load cannot be dispatched (missing requirements)

**Regional Examples:**

**USA:**
- Checks DOT/MC registration
- Validates IFTA for interstate loads
- No government API required

**Brazil:**
- Validates CNPJ, RNTRC, ANTT registration
- Checks for high-theft routes
- Warns about red zones during dangerous hours

---

### 2. Generate Shipping Document

**POST** `/api/compliance/generate-document`

Generates region-specific shipping documents.

**Request Body:**
```json
{
  "company_id": "company-uuid",
  "load_data": {
    "load_number": "L-2026-0001",
    "origin": "São Paulo, SP",
    "destination": "Rio de Janeiro, RJ"
  },
  "driver_data": {
    "cpf": "123.456.789-00",
    "name": "João Silva"
  },
  "vehicle_data": {
    "plate": "ABC-1234",
    "state": "SP"
  }
}
```

**Response:**
```json
{
  "success": true,
  "document_type": "mdfe",
  "document_id": "35260112345678000100580010000000011234567890",
  "document_url": null,
  "xml_content": "<?xml version=\"1.0\" encoding=\"UTF-8\"?><MDFe>...</MDFe>",
  "errors": []
}
```

**Regional Documents:**
- **USA**: Bill of Lading (BOL) - standard format, no government submission
- **Brazil**: MDF-e XML - requires SEFAZ authorization
- **Mexico**: Carta de Porte 3.0 - requires SAT digital seal
- **EU**: e-CMR - digital consignment note with QR code
- **India**: e-Way Bill - via NIC API

---

### 3. Validate Payment

**POST** `/api/compliance/validate-payment`

Validates payment meets regional compliance requirements.

**Request Body:**
```json
{
  "company_id": "company-uuid",
  "payment_data": {
    "amount_brl": 5000.00,
    "ciot_code": "CIOT-12345678"
  },
  "load_data": {
    "distance_km": 500,
    "cargo_type": "dry_goods"
  }
}
```

**Response:**
```json
{
  "status": "VALID",
  "message": "Payment validation complete",
  "errors": [],
  "warnings": [],
  "details": {
    "antt_minimum_rate": 4500.00,
    "provided_amount": 5000.00
  }
}
```

**Regional Requirements:**
- **USA**: No government-mandated requirements
- **Brazil**: CIOT code required, ANTT minimum rate validation
- **Mexico**: VAT compliance validation

---

### 4. Validate Driver Assignment

**POST** `/api/compliance/validate-driver`

Validates driver can be assigned to a load under regional rules.

**Request Body:**
```json
{
  "company_id": "company-uuid",
  "driver_data": {
    "cdl_number": "CA123456789",
    "cdl_class": "A",
    "hos_hours_available": 8.5,
    "eld_connected": true
  },
  "load_data": {
    "vehicle_weight_lbs": 80000,
    "estimated_hours": 7
  }
}
```

**Response:**
```json
{
  "status": "VALID",
  "message": "Driver HOS validation complete",
  "errors": [],
  "warnings": [],
  "details": {
    "hos_hours_available": 8.5,
    "eld_status": "connected"
  }
}
```

**Regional Validations:**
- **USA**: HOS (11-hour limit), CDL class, ELD requirement
- **Brazil**: CNH validation, security clearance for route
- **EU**: Mobility Package (return-to-home), digital tachograph
- **Japan**: 960 hour/year overtime limit check

---

### 5. List Supported Regions

**GET** `/api/compliance/regions`

Returns all supported regions with their configuration.

**Response:**
```json
[
  {
    "code": "usa",
    "name": "United States",
    "description": "HOS compliance, ELD mandate, IFTA reporting",
    "currency_code": "USD",
    "distance_unit": "miles",
    "weight_unit": "lbs",
    "requires_government_api": false,
    "complexity_level": 2
  },
  {
    "code": "brazil",
    "name": "Brazil",
    "description": "MDF-e/CT-e, SEFAZ integration, CIOT payment validation",
    "currency_code": "BRL",
    "distance_unit": "kilometers",
    "weight_unit": "kg",
    "requires_government_api": true,
    "complexity_level": 5
  }
]
```

**Complexity Levels:**
- 1-2: Simple (USA, Canada)
- 3: Moderate (Japan)
- 4: Complex (Mexico, EU, India)
- 5: Very Complex (Brazil, China)

---

### 6. Get Region Information

**GET** `/api/compliance/regions/{region_code}`

Returns detailed information about a specific region.

**Example:** `/api/compliance/regions/brazil`

**Response:**
```json
{
  "code": "brazil",
  "name": "Brazil",
  "description": "MDF-e/CT-e, SEFAZ integration, CIOT payment validation",
  "currency_code": "BRL",
  "distance_unit": "kilometers",
  "weight_unit": "kg",
  "requires_government_api": true,
  "complexity_level": 5
}
```

---

### 7. Get Region Requirements

**GET** `/api/compliance/regions/{region_code}/requirements`

Returns detailed compliance requirements for a region.

**Example:** `/api/compliance/regions/brazil/requirements`

**Response:**
```json
{
  "region_code": "brazil",
  "required_company_fields": [
    "cnpj",
    "ie_number",
    "rntrc",
    "antt_registration"
  ],
  "required_integrations": [
    {
      "name": "SEFAZ API",
      "type": "government_api",
      "required": true,
      "description": "Tax authority API for MDF-e/CT-e authorization"
    },
    {
      "name": "CIOT Provider",
      "type": "payment_validation",
      "required": true,
      "description": "Approved payment provider (Pamcard, Repom, Sem Parar)",
      "options": ["Pamcard", "Repom", "Sem Parar"]
    }
  ],
  "optimization_goal": "maximize_security",
  "key_regulations": [
    "CNPJ (corporate tax ID) required",
    "RNTRC (road cargo transporter registry) required",
    "MDF-e electronic manifest submitted to SEFAZ before trip",
    "CIOT payment code from approved provider mandatory",
    "ANTT minimum freight rate validation"
  ]
}
```

---

### 8. Get Route Optimization Rules

**GET** `/api/compliance/regions/{region_code}/optimization-rules`

Returns AI route optimization rules specific to a region.

**Example:** `/api/compliance/regions/brazil/optimization-rules`

**Response:**
```json
{
  "optimization_goal": "maximize_security",
  "penalties": {
    "red_zones_at_night": 1000,
    "highway_robbery_risk": 500,
    "no_security_escort": 200
  },
  "constraints": {
    "avoid_sp_rj_corridor_night": true,
    "require_security_escort_above": 500000
  },
  "preferences": {
    "prefer_toll_highways": true,
    "prefer_daytime_driving": true
  }
}
```

**Regional Optimization Goals:**
- **USA**: `maximize_rate_per_mile` - Focus on profitability
- **Brazil**: `maximize_security` - Avoid cargo theft zones
- **EU**: `minimize_empty_return` - Respect return-to-home rules
- **Japan**: `minimize_driver_overtime` - Stay under 960 hours/year

---

## Error Handling

All endpoints return standard HTTP status codes:

- `200 OK` - Success
- `400 Bad Request` - Invalid request or unsupported region
- `404 Not Found` - Company not found or region not supported
- `422 Unprocessable Entity` - Validation error

**Error Response Format:**
```json
{
  "detail": "Company abc-123 not found"
}
```

---

## Integration Examples

### Frontend Usage (React/TypeScript)

```typescript
// Validate load before dispatch
const validateLoad = async (companyId: string, loadData: any) => {
  const response = await fetch('/api/compliance/validate-load', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      company_id: companyId,
      load_data: loadData
    })
  });

  const result = await response.json();

  if (result.status === 'ERROR') {
    // Block dispatch, show errors
    alert(result.errors.join('\n'));
    return false;
  }

  if (result.status === 'WARNING') {
    // Allow dispatch with warnings
    console.warn(result.warnings);
  }

  return true;
};

// Get supported regions for dropdown
const fetchRegions = async () => {
  const response = await fetch('/api/compliance/regions', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  return await response.json();
};
```

---

## Testing

### Test USA Load Validation

```bash
curl -X POST http://localhost:8000/api/compliance/validate-load \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "your-company-id",
    "load_data": {
      "origin": "Los Angeles, CA",
      "destination": "Phoenix, AZ",
      "is_interstate": true
    }
  }'
```

### Test Brazil Document Generation

```bash
curl -X POST http://localhost:8000/api/compliance/generate-document \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "your-company-id",
    "load_data": {
      "load_number": "L-2026-0001",
      "origin": "São Paulo, SP",
      "destination": "Rio de Janeiro, RJ"
    },
    "driver_data": {
      "cpf": "123.456.789-00"
    },
    "vehicle_data": {
      "plate": "ABC-1234"
    }
  }'
```

### List All Regions

```bash
curl http://localhost:8000/api/compliance/regions \
  -H "Authorization: Bearer <token>"
```

---

## Next Steps

1. **Run Database Migrations**:
   ```bash
   python -m scripts.migrations.add_universal_core
   python -m scripts.migrations.add_brazil_tables
   ```

2. **Update Frontend**:
   - Add region selector to company profile form
   - Call `/compliance/validate-load` before dispatching
   - Call `/compliance/validate-driver` before assigning

3. **Add More Regions**:
   - Implement Mexico compliance module
   - Implement EU compliance module
   - Implement India, China, Japan modules

4. **Government API Integration**:
   - Brazil: SEFAZ API client for MDF-e authorization
   - Mexico: SAT API client for Carta de Porte sealing
   - India: NIC API client for e-Way Bill generation

---

## OpenAPI Documentation

Full interactive API documentation is available at:

```
http://localhost:8000/docs
```

Search for the "Compliance" tag to see all endpoints with request/response schemas.
