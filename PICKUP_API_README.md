# Pickup API

This API manages the pickup workflow for freight loads, providing a step-by-step process to navigate to pickup locations, confirm arrivals, verify trailers/containers, and complete pickup operations.

## Overview

The pickup process follows a 7-step workflow:
1. **Navigation** - Start navigation to pickup location
2. **Arrival** - Mark arrival with geofence tracking
3. **Trailer Confirmation** - Verify trailer details (optional)
4. **Container Confirmation** - Verify container details (optional)
5. **Pickup Confirmation** - Final pickup completion
6. **Departure** - Mark departure from pickup location
7. **In Transit** - Load status updated for delivery

## Base URL
```
/api/pickup
```

## Endpoints

### 1. Get Pickup Status
**GET** `/status/{load_id}`

Returns the current pickup status for a specific load.

**Response:**
```json
{
  "loadId": "load-123",
  "pickupStatus": "arrived",
  "navigationStartTime": "2024-01-15T10:00:00Z",
  "pickupArrivalTime": "2024-01-15T11:30:00Z",
  "trailerConfirmationTime": null,
  "containerConfirmationTime": null,
  "pickupConfirmationTime": null,
  "departureTime": null,
  "billOfLadingUrl": null,
  "pickupNotes": null,
  "pickupLocation": "123 Main St, City, State",
  "deliveryLocation": "456 Oak Ave, City, State"
}
```

**cURL Example:**
```bash
curl -X GET "http://localhost:8000/api/pickup/status/load-123"
```

### 2. Start Navigation
**POST** `/{load_id}/start-navigation`

Starts navigation to the pickup location. Requires truck assignment to be completed first.

**Request Body:**
```json
{
  "timestamp": "2024-01-15T10:00:00Z",
  "notes": "Starting navigation to pickup location"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Navigation started successfully",
  "newStatus": "navigation",
  "timestamp": "2024-01-15T10:00:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/pickup/load-123/start-navigation" \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Starting navigation to pickup location"
  }'
```

### 3. Mark Arrival
**POST** `/{load_id}/arrive`

Marks arrival at the pickup location with optional geofence tracking.

**Request Body:**
```json
{
  "latitude": 40.7128,
  "longitude": -74.0060,
  "timestamp": "2024-01-15T11:30:00Z",
  "geofenceStatus": "entered",
  "notes": "Arrived at pickup location"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Arrival at pickup location confirmed",
  "newStatus": "arrived",
  "timestamp": "2024-01-15T11:30:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/pickup/load-123/arrive" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 40.7128,
    "longitude": -74.0060,
    "geofenceStatus": "entered",
    "notes": "Arrived at pickup location"
  }'
```

### 4. Confirm Trailer
**POST** `/{load_id}/confirm-trailer`

Confirms trailer details for the pickup. This step is optional.

**Request Body:**
```json
{
  "timestamp": "2024-01-15T12:00:00Z",
  "trailerNumber": "TRL-789",
  "notes": "Trailer confirmed and ready"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Trailer confirmation completed",
  "newStatus": "trailer_confirmed",
  "timestamp": "2024-01-15T12:00:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/pickup/load-123/confirm-trailer" \
  -H "Content-Type: application/json" \
  -d '{
    "trailerNumber": "TRL-789",
    "notes": "Trailer confirmed and ready"
  }'
```

### 5. Confirm Container
**POST** `/{load_id}/confirm-container`

Confirms container details for the pickup. This step is optional and can be used instead of trailer confirmation.

**Request Body:**
```json
{
  "timestamp": "2024-01-15T12:15:00Z",
  "containerNumber": "CONT-456",
  "notes": "Container verified and sealed"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Container confirmation completed",
  "newStatus": "container_confirmed",
  "timestamp": "2024-01-15T12:15:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/pickup/load-123/confirm-container" \
  -H "Content-Type: application/json" \
  -d '{
    "containerNumber": "CONT-456",
    "notes": "Container verified and sealed"
  }'
```

### 6. Confirm Pickup
**POST** `/{load_id}/confirm-pickup`

Final confirmation that completes the pickup process and marks the load as picked up.

**Request Body:**
```json
{
  "timestamp": "2024-01-15T12:30:00Z",
  "pickupNotes": "All cargo loaded successfully, BOL signed"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Pickup confirmed successfully",
  "newStatus": "pickup_confirmed",
  "timestamp": "2024-01-15T12:30:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/pickup/load-123/confirm-pickup" \
  -H "Content-Type: application/json" \
  -d '{
    "pickupNotes": "All cargo loaded successfully, BOL signed"
  }'
```

### 7. Mark Departure
**POST** `/{load_id}/depart`

Marks departure from the pickup location and updates load status to in transit.

**Request Body:**
```json
{
  "timestamp": "2024-01-15T13:00:00Z",
  "notes": "Departed pickup location, en route to delivery"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Departure confirmed successfully",
  "newStatus": "departed",
  "timestamp": "2024-01-15T13:00:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/pickup/load-123/depart" \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Departed pickup location, en route to delivery"
  }'
```

### 8. Upload Bill of Lading
**POST** `/{load_id}/upload-bol`

Uploads a bill of lading document for the pickup.

**Request:** Multipart form data with file upload

**Response:**
```json
{
  "success": true,
  "message": "Bill of lading uploaded successfully",
  "filename": "bol_load-123_20240115_130000.pdf",
  "file_url": "/uploads/bol/bol_load-123_20240115_130000.pdf",
  "file_size": 245760,
  "content_type": "application/pdf"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/pickup/load-123/upload-bol" \
  -F "file=@/path/to/bol_document.pdf"
```

## Status Flow

The pickup status progresses through these states:

1. `pending` (initial state - waiting for truck assignment)
2. `navigation` (after starting navigation)
3. `arrived` (after marking arrival)
4. `trailer_confirmed` (after trailer confirmation) OR `container_confirmed` (after container confirmation)
5. `pickup_confirmed` (after final pickup confirmation)
6. `departed` (after marking departure)

## Prerequisites

- **Truck Assignment**: Load must have `truck_confirmed` status before pickup can begin
- **Navigation**: Must start navigation before marking arrival
- **Arrival**: Must mark arrival before confirming trailer/container
- **Confirmation**: Must confirm either trailer OR container before final pickup confirmation

## Error Handling

- **400 Bad Request**: Invalid request data or workflow violation
- **404 Not Found**: Load not found
- **500 Internal Server Error**: Server-side errors

## Features

- **Geofence Tracking**: GPS coordinates and geofence status for arrival confirmation
- **Document Upload**: Bill of lading file upload with automatic URL storage
- **Flexible Confirmation**: Can confirm trailer OR container (not both required)
- **Location Storage**: Arrival coordinates stored in load meta field
- **Status Validation**: Enforces proper workflow progression
- **Notes Support**: Optional notes at each step for additional context

## Notes

- All timestamps are optional and will default to the current time if not provided
- The workflow must be followed in order - you cannot skip steps
- Trailer and container confirmation are mutually exclusive - choose one based on load type
- Once a load reaches `departed` status, it becomes `in_transit` for delivery
- Bill of lading upload is optional but recommended for documentation
- Geofence coordinates are stored in the load's meta field for location tracking
