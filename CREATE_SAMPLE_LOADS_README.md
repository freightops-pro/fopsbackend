# Create Sample Loads API

This guide provides cURL examples for creating sample loads to test the freight operations workflow, including truck assignment, pickup, delivery, and settlement processes.

## Base URL
```
/api
```

## Authentication

All requests require authentication. Include your JWT token in the Authorization header:
```bash
-H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Create Sample Loads

### 1. Basic Load Creation
**POST** `/loads`

Creates a new freight load with basic information.

**Request Body:**
```json
{
  "loadNumber": "LD-2024-001",
  "customerName": "ABC Manufacturing",
  "pickupLocation": "123 Industrial Blvd, Chicago, IL 60601",
  "deliveryLocation": "456 Warehouse Dr, Detroit, MI 48201",
  "pickupDate": "2024-01-15",
  "deliveryDate": "2024-01-16",
  "pickuptime": "2024-01-15T08:00:00Z",
  "deliverytime": "2024-01-16T14:00:00Z",
  "rate": 2500.00,
  "priority": "high",
  "notes": "Urgent delivery - automotive parts",
  "commodity": "Automotive Parts",
  "trailerType": "Dry Van",
  "weight": "45000",
  "pieces": "150"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/loads" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "loadNumber": "LD-2024-001",
    "customerName": "ABC Manufacturing",
    "pickupLocation": "123 Industrial Blvd, Chicago, IL 60601",
    "deliveryLocation": "456 Warehouse Dr, Detroit, MI 48201",
    "pickupDate": "2024-01-15",
    "deliveryDate": "2024-01-16",
    "pickuptime": "2024-01-15T08:00:00Z",
    "deliverytime": "2024-01-16T14:00:00Z",
    "rate": 2500.00,
    "priority": "high",
    "notes": "Urgent delivery - automotive parts",
    "commodity": "Automotive Parts",
    "trailerType": "Dry Van",
    "weight": "45000",
    "pieces": "150"
  }'
```

**Response:**
```json
{
  "id": "load-uuid-123"
}
```

### 2. Reefer Load (Temperature Controlled)
**POST** `/loads`

Creates a temperature-controlled load requiring refrigeration.

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/loads" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "loadNumber": "LD-2024-002",
    "customerName": "Fresh Foods Co",
    "pickupLocation": "789 Cold Storage, Phoenix, AZ 85001",
    "deliveryLocation": "321 Distribution Center, Denver, CO 80201",
    "pickupDate": "2024-01-16",
    "deliveryDate": "2024-01-17",
    "pickuptime": "2024-01-16T06:00:00Z",
    "deliverytime": "2024-01-17T10:00:00Z",
    "rate": 3200.00,
    "priority": "normal",
    "notes": "Temperature controlled - maintain 34°F",
    "commodity": "Frozen Foods",
    "trailerType": "Reefer",
    "temperature": "34",
    "weight": "38000",
    "pieces": "200"
  }'
```

### 3. Flatbed Load (Oversized Cargo)
**POST** `/loads`

Creates a load requiring flatbed trailer for oversized cargo.

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/loads" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "loadNumber": "LD-2024-003",
    "customerName": "Heavy Equipment Inc",
    "pickupLocation": "555 Construction Site, Houston, TX 77001",
    "deliveryLocation": "777 Industrial Park, Dallas, TX 75201",
    "pickupDate": "2024-01-17",
    "deliveryDate": "2024-01-18",
    "pickuptime": "2024-01-17T09:00:00Z",
    "deliverytime": "2024-01-18T15:00:00Z",
    "rate": 4500.00,
    "priority": "medium",
    "notes": "Oversized load - requires permits",
    "commodity": "Construction Equipment",
    "trailerType": "Flatbed",
    "weight": "80000",
    "pieces": "1",
    "dimensions": "40x12x15",
    "permitsRequired": true
  }'
```

### 4. Container Load (Intermodal)
**POST** `/loads`

Creates an intermodal container load.

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/loads" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "loadNumber": "LD-2024-004",
    "customerName": "Global Shipping Ltd",
    "pickupLocation": "Port of Los Angeles, CA 90731",
    "deliveryLocation": "Inland Port, Las Vegas, NV 89101",
    "pickupDate": "2024-01-18",
    "deliveryDate": "2024-01-19",
    "pickuptime": "2024-01-18T11:00:00Z",
    "deliverytime": "2024-01-19T16:00:00Z",
    "rate": 2800.00,
    "priority": "normal",
    "notes": "Container load - 40ft standard",
    "commodity": "Electronics",
    "trailerType": "Container",
    "containerNumber": "MSKU1234567",
    "weight": "42000",
    "pieces": "500"
  }'
```

### 5. Hazmat Load (Dangerous Goods)
**POST** `/loads`

Creates a hazardous materials load requiring special handling.

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/loads" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "loadNumber": "LD-2024-005",
    "customerName": "Chemical Solutions Corp",
    "pickupLocation": "999 Chemical Plant, Baton Rouge, LA 70801",
    "deliveryLocation": "111 Processing Facility, Mobile, AL 36601",
    "pickupDate": "2024-01-19",
    "deliveryDate": "2024-01-20",
    "pickuptime": "2024-01-19T07:00:00Z",
    "deliverytime": "2024-01-20T12:00:00Z",
    "rate": 5500.00,
    "priority": "urgent",
    "notes": "Hazmat load - Class 3 Flammable Liquid",
    "commodity": "Chemical Products",
    "trailerType": "Tanker",
    "hazmatClass": "3",
    "unNumber": "UN1203",
    "weight": "35000",
    "pieces": "1",
    "specialInstructions": "Driver must have hazmat endorsement"
  }'
```

## Load Assignment

### 6. Assign Driver and Truck to Load
**POST** `/loads/{load_id}/assign`

Assigns a driver and truck to a specific load.

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/loads/load-uuid-123/assign" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "assigned_driver_id": "driver-uuid-456",
    "assigned_truck_id": "truck-uuid-789"
  }'
```

## Load Billing

### 7. Create Load Billing
**POST** `/load-billing/{load_id}`

Creates billing information for a load.

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/load-billing/load-uuid-123" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "baseRate": 2500.00,
    "rateType": "flat",
    "billingStatus": "pending",
    "customerName": "ABC Manufacturing",
    "totalAmount": 2500.00
  }'
```

### 8. Add Accessorial Charges
**POST** `/load-accessorials/{load_id}`

Adds additional charges to a load.

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/load-accessorials/load-uuid-123" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "type": "detention",
    "description": "Driver detention at pickup",
    "amount": 150.00,
    "quantity": 2,
    "rate": 75.00,
    "isBillable": true,
    "notes": "Waited 2 hours for loading"
  }'
```

## Complete Workflow Example

Here's a complete example of creating a load and going through the entire workflow:

### Step 1: Create Load
```bash
LOAD_RESPONSE=$(curl -X POST "http://localhost:8000/api/loads" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "loadNumber": "LD-2024-TEST",
    "customerName": "Test Customer",
    "pickupLocation": "123 Test St, Test City, TC 12345",
    "deliveryLocation": "456 Delivery Ave, Delivery City, DC 54321",
    "pickupDate": "2024-01-20",
    "deliveryDate": "2024-01-21",
    "rate": 2000.00,
    "priority": "normal",
    "notes": "Test load for workflow demonstration"
  }')

LOAD_ID=$(echo $LOAD_RESPONSE | jq -r '.id')
echo "Created load with ID: $LOAD_ID"
```

### Step 2: Assign Driver and Truck
```bash
curl -X POST "http://localhost:8000/api/loads/$LOAD_ID/assign" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "assigned_driver_id": "driver-123",
    "assigned_truck_id": "truck-456"
  }'
```

### Step 3: Start Truck Assignment Workflow
```bash
# Assign truck
curl -X POST "http://localhost:8000/api/truck-assignment/$LOAD_ID/assign-truck" \
  -H "Content-Type: application/json" \
  -d '{"truckId": "truck-456"}'

# Confirm driver
curl -X POST "http://localhost:8000/api/truck-assignment/$LOAD_ID/confirm-driver" \
  -H "Content-Type: application/json" \
  -d '{"isDrivingAssignedTruck": true}'

# Setup trailer
curl -X POST "http://localhost:8000/api/truck-assignment/$LOAD_ID/setup-trailer" \
  -H "Content-Type: application/json" \
  -d '{"hasTrailer": true, "trailerNumber": "TRL-789"}'

# Confirm truck
curl -X POST "http://localhost:8000/api/truck-assignment/$LOAD_ID/confirm-truck" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Step 4: Start Pickup Workflow
```bash
# Start navigation
curl -X POST "http://localhost:8000/api/pickup/$LOAD_ID/start-navigation" \
  -H "Content-Type: application/json" \
  -d '{"notes": "Starting navigation to pickup"}'

# Mark arrival
curl -X POST "http://localhost:8000/api/pickup/$LOAD_ID/arrive" \
  -H "Content-Type: application/json" \
  -d '{"latitude": 40.7128, "longitude": -74.0060, "notes": "Arrived at pickup location"}'

# Confirm trailer
curl -X POST "http://localhost:8000/api/pickup/$LOAD_ID/confirm-trailer" \
  -H "Content-Type: application/json" \
  -d '{"trailerNumber": "TRL-789", "notes": "Trailer confirmed"}'

# Confirm pickup
curl -X POST "http://localhost:8000/api/pickup/$LOAD_ID/confirm-pickup" \
  -H "Content-Type: application/json" \
  -d '{"pickupNotes": "Cargo loaded successfully"}'

# Mark departure
curl -X POST "http://localhost:8000/api/pickup/$LOAD_ID/depart" \
  -H "Content-Type: application/json" \
  -d '{"notes": "Departed pickup location"}'
```

### Step 5: Start Delivery Workflow
```bash
# Mark arrival at delivery
curl -X POST "http://localhost:8000/api/delivery/$LOAD_ID/arrive" \
  -H "Content-Type: application/json" \
  -d '{"latitude": 40.7589, "longitude": -73.9851, "notes": "Arrived at delivery location"}'

# Mark docking
curl -X POST "http://localhost:8000/api/delivery/$LOAD_ID/dock" \
  -H "Content-Type: application/json" \
  -d '{"notes": "Docked at bay 3"}'

# Start unloading
curl -X POST "http://localhost:8000/api/delivery/$LOAD_ID/start-unloading" \
  -H "Content-Type: application/json" \
  -d '{"notes": "Unloading started"}'

# Complete unloading
curl -X POST "http://localhost:8000/api/delivery/$LOAD_ID/complete-unloading" \
  -H "Content-Type: application/json" \
  -d '{"notes": "Unloading completed"}'

# Confirm delivery
curl -X POST "http://localhost:8000/api/delivery/$LOAD_ID/confirm" \
  -H "Content-Type: application/json" \
  -d '{"recipientName": "John Smith", "deliveryNotes": "Delivery completed successfully"}'
```

### Step 6: Submit Settlement
```bash
# Get settlement data
curl -X GET "http://localhost:8000/api/settlements/request/$LOAD_ID"

# Submit settlement
curl -X POST "http://localhost:8000/api/settlements/request/$LOAD_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "actualMiles": 275.5,
    "actualHours": 5.2,
    "detentionHours": 1.5,
    "fuelSurcharge": 50.0,
    "otherDeductions": 25.0,
    "notes": "Settlement for completed load"
  }'
```

## Notes

- Replace `YOUR_JWT_TOKEN` with your actual JWT token
- Replace `load-uuid-123`, `driver-123`, `truck-456` with actual IDs from your system
- All timestamps are in ISO format
- The `meta` field captures additional custom fields
- Load numbers are auto-generated if not provided
- Company ID is automatically extracted from the JWT token
- Priority levels: `low`, `normal`, `medium`, `high`, `urgent`
- Status values: `pending`, `assigned`, `in_transit`, `delivered`, `cancelled`
