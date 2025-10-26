# Delivery API

This API manages the delivery workflow for freight loads, providing a step-by-step process to track arrival, docking, unloading, and final delivery confirmation.

## Overview

The delivery process follows a 5-step workflow:
1. **Arrival** - Mark arrival at delivery location with geofence tracking
2. **Docking** - Confirm docking at delivery location
3. **Unloading Start** - Begin unloading process
4. **Unloading Complete** - Finish unloading operations
5. **Delivery Confirmation** - Final delivery with recipient details

## Base URL
```
/api/delivery
```

## Endpoints

### 1. Get Delivery Status
**GET** `/status/{load_id}`

Returns the current delivery status for a specific load.

**Response:**
```json
{
  "loadId": "load-123",
  "deliveryStatus": "unloading",
  "arrivalTime": "2024-01-15T14:00:00Z",
  "dockingTime": "2024-01-15T14:15:00Z",
  "unloadingStartTime": "2024-01-15T14:30:00Z",
  "unloadingEndTime": null,
  "deliveryTime": null,
  "recipientName": null,
  "deliveryNotes": null
}
```

**cURL Example:**
```bash
curl -X GET "http://localhost:8000/api/delivery/status/load-123"
```

### 2. Mark Arrival
**POST** `/{load_id}/arrive`

Marks arrival at the delivery location with optional geofence tracking.

**Request Body:**
```json
{
  "latitude": 40.7589,
  "longitude": -73.9851,
  "timestamp": "2024-01-15T14:00:00Z",
  "geofenceStatus": "entered",
  "notes": "Arrived at delivery location"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Arrival confirmed successfully",
  "newStatus": "arrived",
  "timestamp": "2024-01-15T14:00:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/delivery/load-123/arrive" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 40.7589,
    "longitude": -73.9851,
    "geofenceStatus": "entered",
    "notes": "Arrived at delivery location"
  }'
```

### 3. Mark Docking
**POST** `/{load_id}/dock`

Confirms docking at the delivery location.

**Request Body:**
```json
{
  "timestamp": "2024-01-15T14:15:00Z",
  "notes": "Docked at bay 3, ready for unloading"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Docking confirmed successfully",
  "newStatus": "docked",
  "timestamp": "2024-01-15T14:15:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/delivery/load-123/dock" \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Docked at bay 3, ready for unloading"
  }'
```

### 4. Start Unloading
**POST** `/{load_id}/start-unloading`

Marks the beginning of the unloading process.

**Request Body:**
```json
{
  "timestamp": "2024-01-15T14:30:00Z",
  "notes": "Unloading started, 2 dock workers assigned"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Unloading started successfully",
  "newStatus": "unloading",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/delivery/load-123/start-unloading" \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Unloading started, 2 dock workers assigned"
  }'
```

### 5. Complete Unloading
**POST** `/{load_id}/complete-unloading`

Marks the completion of the unloading process.

**Request Body:**
```json
{
  "timestamp": "2024-01-15T16:00:00Z",
  "notes": "All cargo unloaded and verified"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Unloading completed successfully",
  "newStatus": "unloading_complete",
  "timestamp": "2024-01-15T16:00:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/delivery/load-123/complete-unloading" \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "All cargo unloaded and verified"
  }'
```

### 6. Confirm Delivery
**POST** `/{load_id}/confirm`

Final delivery confirmation with recipient details. This marks the load as fully delivered and triggers settlement calculation.

**Request Body:**
```json
{
  "deliveryTimestamp": "2024-01-15T16:15:00Z",
  "recipientName": "John Smith",
  "deliveryNotes": "Delivery completed successfully, all items accounted for"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Delivery confirmed successfully",
  "newStatus": "delivered",
  "timestamp": "2024-01-15T16:15:00Z"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/delivery/load-123/confirm" \
  -H "Content-Type: application/json" \
  -d '{
    "recipientName": "John Smith",
    "deliveryNotes": "Delivery completed successfully, all items accounted for"
  }'
```

## Status Flow

The delivery status progresses through these states:

1. `in_transit` (initial state - from pickup completion)
2. `arrived` (after marking arrival)
3. `docked` (after marking docking)
4. `unloading` (after starting unloading)
5. `unloading_complete` (after completing unloading)
6. `delivered` (after final delivery confirmation)

## Prerequisites

- **Pickup Completion**: Load must have `in_transit` status from pickup completion
- **Sequential Flow**: Steps must be completed in order
- **Arrival**: Must mark arrival before docking
- **Docking**: Must dock before starting unloading
- **Unloading**: Must start unloading before completing it
- **Completion**: Must complete unloading before final delivery confirmation

## Error Handling

- **400 Bad Request**: Invalid request data or workflow violation
- **404 Not Found**: Load not found
- **500 Internal Server Error**: Server-side errors

## Features

- **Geofence Tracking**: GPS coordinates and geofence status for arrival confirmation
- **Recipient Tracking**: Capture recipient name for delivery confirmation
- **Status Validation**: Enforces proper workflow progression
- **Location Storage**: Arrival coordinates stored in load meta field
- **Settlement Integration**: Final confirmation triggers payment/settlement calculations
- **Notes Support**: Optional notes at each step for additional context
- **Timestamp Tracking**: Detailed timing for each delivery stage

## Integration Points

- **Pickup Flow**: Requires `in_transit` status from pickup completion
- **Load Management**: Updates main load status to `delivered`
- **Settlement System**: Triggers payment and settlement calculations
- **Reporting**: Provides delivery metrics and timing data

## Notes

- All timestamps are optional and will default to the current time if not provided
- The workflow must be followed in order - you cannot skip steps
- Once a load reaches `delivered` status, it triggers settlement calculations
- Geofence coordinates are stored in the load's meta field for location tracking
- Recipient name is required for final delivery confirmation
- The delivery confirmation step updates both delivery status and main load status
- Unloading can take varying amounts of time depending on cargo type and volume
