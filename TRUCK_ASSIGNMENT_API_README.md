# Truck Assignment API

This API manages the truck assignment workflow for freight loads, providing a step-by-step process to assign trucks, confirm drivers, setup trailers, and finalize truck assignments.

## Overview

The truck assignment process follows a 5-step workflow:
1. **Truck Assignment** - Assign a truck to a load
2. **Driver Confirmation** - Confirm the driver is operating the assigned truck
3. **Trailer Setup** - Configure trailer information (if needed)
4. **Truck Confirmation** - Final confirmation before pickup
5. **Ready for Pickup** - Load is ready to begin pickup process

## Base URL
```
/api/truck-assignment
```

## Endpoints

### 1. Get Truck Assignment Status
**GET** `/status/{load_id}`

Returns the current truck assignment status for a specific load.

**Response:**
```json
{
  "loadId": "load-123",
  "truckAssignmentStatus": "truck_assigned",
  "assignedTruckId": "truck-001",
  "assignedDriverId": "driver-456",
  "truckAssignmentTime": "2024-01-15T10:30:00Z",
  "driverConfirmationTime": null,
  "trailerSetupTime": null,
  "truckConfirmationTime": null,
  "trailerNumber": null,
  "hasTrailer": null
}
```

**cURL Example:**
```bash
curl -X GET "http://localhost:8000/api/truck-assignment/status/load-123"
```

### 2. Get Available Trucks
**GET** `/available-trucks?company_id={company_id}`

Returns a list of available trucks for assignment.

**Response:**
```json
{
  "trucks": [
    {
      "id": "truck-001",
      "truckNumber": "TRK-001",
      "make": "Freightliner",
      "model": "Cascadia",
      "year": 2022,
      "status": "available",
      "location": "Main Yard"
    }
  ],
  "total": 1
}
```

**cURL Example:**
```bash
curl -X GET "http://localhost:8000/api/truck-assignment/available-trucks?company_id=company-123"
```

### 3. Assign Truck to Load
**POST** `/{load_id}/assign-truck`

Assigns a truck to a specific load. This is the first step in the truck assignment workflow.

**Request Body:**
```json
{
  "truckId": "truck-001",
  "timestamp": "2024-01-15T10:30:00Z",
  "notes": "Assigned for urgent delivery"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Truck assigned successfully",
  "newStatus": "truck_assigned",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/truck-assignment/load-123/assign-truck" \
  -H "Content-Type: application/json" \
  -d '{
    "truckId": "truck-001",
    "notes": "Assigned for urgent delivery"
  }'
```

### 4. Confirm Driver
**POST** `/{load_id}/confirm-driver`

Confirms that the assigned driver is operating the assigned truck.

**Request Body:**
```json
{
  "isDrivingAssignedTruck": true,
  "timestamp": "2024-01-15T11:00:00Z",
  "notes": "Driver confirmed and ready"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Driver confirmation successful",
  "newStatus": "driver_confirmed",
  "timestamp": "2024-01-15T11:00:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/truck-assignment/load-123/confirm-driver" \
  -H "Content-Type: application/json" \
  -d '{
    "isDrivingAssignedTruck": true,
    "notes": "Driver confirmed and ready"
  }'
```

### 5. Setup Trailer
**POST** `/{load_id}/setup-trailer`

Configures trailer information for the load. Can specify if a trailer is needed and its details.

**Request Body:**
```json
{
  "hasTrailer": true,
  "trailerNumber": "TRL-789",
  "timestamp": "2024-01-15T11:30:00Z",
  "notes": "53ft dry van trailer attached"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Trailer setup completed",
  "newStatus": "trailer_set",
  "timestamp": "2024-01-15T11:30:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/truck-assignment/load-123/setup-trailer" \
  -H "Content-Type: application/json" \
  -d '{
    "hasTrailer": true,
    "trailerNumber": "TRL-789",
    "notes": "53ft dry van trailer attached"
  }'
```

### 6. Confirm Truck
**POST** `/{load_id}/confirm-truck`

Final confirmation step that completes the truck assignment process and marks the load as ready for pickup.

**Request Body:**
```json
{
  "timestamp": "2024-01-15T12:00:00Z",
  "notes": "All systems checked, ready for pickup"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Truck confirmation completed",
  "newStatus": "truck_confirmed",
  "timestamp": "2024-01-15T12:00:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/truck-assignment/load-123/confirm-truck" \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "All systems checked, ready for pickup"
  }'
```

## Status Flow

The truck assignment status progresses through these states:

1. `truck_assignment_required` (initial state)
2. `truck_assigned` (after truck assignment)
3. `driver_confirmed` (after driver confirmation)
4. `trailer_set` (after trailer setup)
5. `truck_confirmed` (final state - ready for pickup)

## Error Handling

- **400 Bad Request**: Invalid request data or workflow violation
- **404 Not Found**: Load not found
- **500 Internal Server Error**: Server-side errors

## Notes

- All timestamps are optional and will default to the current time if not provided
- The workflow must be followed in order - you cannot skip steps
- Once a load reaches `truck_confirmed` status, it becomes ready for the pickup process
- Trailer information is stored in the load's meta field for flexibility
