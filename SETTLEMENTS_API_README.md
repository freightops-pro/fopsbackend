# Settlements API

This API manages driver settlements for completed freight loads, providing settlement calculation, request processing, and payment tracking for drivers.

## Overview

The settlement process follows a 2-step workflow:
1. **Settlement Request** - Get settlement data and rates for a completed load
2. **Settlement Submission** - Submit actual delivery data and calculate final settlement

## Base URL
```
/api/settlements
```

## Endpoints

### 1. Get Settlement Request Data
**GET** `/request/{load_id}`

Returns settlement request data including driver information, load details, and applicable rates for a specific load.

**Response:**
```json
{
  "loadId": "load-123",
  "driverId": "driver-456",
  "driverInfo": {
    "firstName": "John",
    "lastName": "Smith",
    "payRate": 25.0,
    "payType": "hourly"
  },
  "loadDetails": {
    "loadNumber": "LD-2024-001",
    "pickupLocation": "123 Main St, City, State",
    "deliveryLocation": "456 Oak Ave, City, State",
    "estimatedMiles": 250,
    "estimatedDuration": 4.5
  },
  "completedData": null,
  "settlementCalculation": null,
  "rates": {
    "mileageRate": 0.50,
    "hourlyRate": 25.0,
    "detentionRate": 25.0
  }
}
```

**cURL Example:**
```bash
curl -X GET "http://localhost:8000/api/settlements/request/load-123"
```

### 2. Submit Settlement Request
**POST** `/request/{load_id}`

Submits actual delivery data and calculates the final settlement for a completed load.

**Request Body:**
```json
{
  "actualMiles": 275.5,
  "actualHours": 5.2,
  "detentionHours": 1.5,
  "fuelSurcharge": 50.0,
  "otherDeductions": 25.0,
  "notes": "Additional fuel cost due to traffic delays"
}
```

**Response:**
```json
{
  "settlementId": "settlement-789",
  "status": "pending_approval",
  "totalSettlement": 387.75,
  "breakdown": {
    "mileagePay": 137.75,
    "hourlyPay": 130.0,
    "detentionPay": 37.5,
    "fuelSurcharge": 50.0,
    "totalSettlement": 387.75
  }
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/settlements/request/load-123" \
  -H "Content-Type: application/json" \
  -d '{
    "actualMiles": 275.5,
    "actualHours": 5.2,
    "detentionHours": 1.5,
    "fuelSurcharge": 50.0,
    "otherDeductions": 25.0,
    "notes": "Additional fuel cost due to traffic delays"
  }'
```

## Settlement Calculation

The settlement is calculated using the following formula:

```
Total Settlement = (Actual Miles × Mileage Rate) + 
                   (Actual Hours × Hourly Rate) + 
                   (Detention Hours × Detention Rate) + 
                   Fuel Surcharge - 
                   Other Deductions
```

### Rate Structure

- **Mileage Rate**: $0.50 per mile (company standard)
- **Hourly Rate**: Driver's pay rate (from driver profile)
- **Detention Rate**: Same as hourly rate
- **Fuel Surcharge**: Additional fuel costs
- **Other Deductions**: Any additional deductions

## Prerequisites

- **Load Completion**: Load must be in `delivered` status
- **Driver Assignment**: Load must have an assigned driver
- **Driver Profile**: Driver must have pay rate and pay type configured

## Error Handling

- **400 Bad Request**: Invalid request data
- **404 Not Found**: Load not found or no driver assigned
- **500 Internal Server Error**: Server-side errors

## Features

- **Automatic Calculation**: Settlement amounts calculated automatically
- **Rate Management**: Uses driver-specific rates and company standards
- **Detention Tracking**: Separate tracking for detention hours
- **Fuel Surcharge**: Additional fuel cost reimbursement
- **Deductions Support**: Various deduction types supported
- **Settlement Periods**: Organized by month for payroll processing
- **Status Tracking**: Settlement status tracking (pending_approval, approved, paid)

## Integration Points

- **Delivery Flow**: Triggered after delivery confirmation
- **Driver Management**: Uses driver pay rates and information
- **Load Management**: References completed load details
- **Payroll System**: Integrates with payroll processing
- **Accounting**: Settlement records for financial tracking

## Settlement Status Flow

1. **pending_approval** - Initial status after submission
2. **approved** - After management approval
3. **paid** - After payment processing

## Notes

- Settlement requests can only be submitted for completed loads
- All monetary values are calculated to 2 decimal places
- Settlement periods are organized by year-month format (YYYY-MM)
- Driver pay rates are used for hourly and detention calculations
- Company standard mileage rate is $0.50 per mile
- Fuel surcharge and other deductions are optional
- Settlement records are created for payroll and accounting purposes
- Notes field allows for additional context and explanations
