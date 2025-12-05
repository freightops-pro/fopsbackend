# Webhook-Chat Integration Documentation

## Overview

The webhook-chat integration allows external systems and internal automation to send chat notifications to drivers through the collaboration system. This enables real-time communication between dispatchers, automation systems, and drivers.

## Architecture

```
External System/Webhook
    ↓
Webhook Endpoint (/api/webhooks/chat/*)
    ↓
WebhookChatService
    ↓
Collaboration System (Channels + Messages)
    ↓
WebSocket Hub (Real-time broadcast)
    ↓
Frontend Chat UI
```

## Features

### 1. Driver-Specific Channels

Each driver automatically gets a dedicated channel for communication:
- Channel naming: `driver:{driver_id}`
- Auto-created on first message
- Persistent across sessions

### 2. Webhook Event Types

The system automatically formats messages for various webhook events:

- **HOS Violations**: `hos_violation`, `hos.violation`
- **HOS Status Updates**: `hos_status`, `hos.status`
- **Geofence Events**: `geofence_entry`, `geofence_exit`
- **Fault Codes**: `fault_code`, `fault_code.created`
- **Vehicle Location**: `vehicle_location`, `vehicle.location`
- **Speeding Events**: `speeding_event`
- **Performance Events**: `driver_performance`
- **Engine Events**: `engine_toggle`

### 3. Custom Notifications

- Load assignments
- Pickup reminders
- Custom messages

## API Endpoints

### Send Custom Driver Notification

```http
POST /api/webhooks/chat/notify-driver
Authorization: Bearer {token}
Content-Type: application/json

{
  "driver_id": "driver-uuid",
  "message": "Custom message text",
  "event_type": "custom",
  "event_data": {}
}
```

### Notify Load Assignment

```http
POST /api/webhooks/chat/notify-load-assignment
Authorization: Bearer {token}
Content-Type: application/json

{
  "driver_id": "driver-uuid",
  "load_id": "load-uuid",
  "load_details": {
    "pickup_location": {
      "address": "123 Main St, City, State"
    },
    "delivery_location": {
      "address": "456 Oak Ave, City, State"
    }
  }
}
```

### Notify Pickup Reminder

```http
POST /api/webhooks/chat/notify-pickup-reminder
Authorization: Bearer {token}
Content-Type: application/json

{
  "driver_id": "driver-uuid",
  "load_id": "load-uuid",
  "pickup_time": "2024-01-15 10:00:00",
  "location": "123 Main St, City, State"
}
```

## Integration with Existing Webhooks

The system automatically integrates with existing webhook handlers:

### Motive Webhooks

When Motive sends webhook events, the system automatically:
1. Processes the event (updates database, triggers workflows)
2. Sends chat notification to the driver (if driver_id is present)

Supported Motive events:
- `vehicle_location_updated` → Location update message
- `hos_violation_upserted` → HOS violation alert
- `vehicle_geofence_event` → Geofence entry/exit notification
- `fault_code_opened` → Fault code alert
- `speeding_event_created` → Speeding alert

## Usage Examples

### Example 1: Dispatch System Notifies Driver

```python
# In your dispatch service
from app.services.webhook_chat import WebhookChatService

async def assign_load_to_driver(db, company_id, driver_id, load_id, load_details):
    # ... assign load logic ...
    
    # Notify driver via chat
    chat_service = WebhookChatService(db)
    await chat_service.notify_load_assignment(
        company_id=company_id,
        driver_id=driver_id,
        load_id=load_id,
        load_details=load_details,
    )
```

### Example 2: Automation Rule Triggers Chat

```python
# In automation service
from app.services.webhook_chat import WebhookChatService

async def handle_automation_rule(db, rule, event_data):
    if rule.action == "notify_driver":
        chat_service = WebhookChatService(db)
        await chat_service.notify_driver_webhook_event(
            company_id=rule.company_id,
            driver_id=event_data.get("driver_id"),
            event_type=rule.event_type,
            event_data=event_data,
        )
```

### Example 3: External System Sends Notification

```bash
curl -X POST http://localhost:8000/api/webhooks/chat/notify-driver \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "driver_id": "driver-123",
    "message": "Your load has been updated. Please check the new pickup location.",
    "event_type": "load_update"
  }'
```

## Frontend Integration

### Getting Driver Channels

```typescript
// Get all driver channels
const { data: channels } = useQuery({
  queryKey: ['channels', { driver_id: driverId }],
  queryFn: () => fetch(`/api/collaboration/channels?driver_id=${driverId}`)
    .then(r => r.json())
});

// Get specific driver channel
const { data: channel } = useQuery({
  queryKey: ['driver-channel', driverId],
  queryFn: () => fetch(`/api/collaboration/drivers/${driverId}/channel`)
    .then(r => r.json())
});
```

### WebSocket Connection

```typescript
// Connect to driver channel WebSocket
const ws = new WebSocket(`ws://localhost:8000/api/collaboration/channels/${channelId}/ws`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'message') {
    // Handle new message
    console.log('New message:', data.data);
  }
};
```

## Message Formatting

Messages are automatically formatted with emojis and structured text:

- ⚠️ HOS Violations
- 📊 HOS Status Updates
- 📍 Geofence Events
- 🔧 Fault Codes
- 🗺️ Location Updates
- 🚨 Speeding Alerts
- 📦 Load Assignments
- ⏰ Pickup Reminders

## Error Handling

All webhook chat operations include error handling:
- Failed notifications are logged but don't break webhook processing
- Missing driver_id gracefully skips chat notification
- Invalid channels are auto-created
- System user fallback ensures messages can always be sent

## Security

- All endpoints require authentication (Bearer token)
- Company isolation enforced (drivers can only receive messages from their company)
- Webhook signature validation for external webhooks
- Input validation on all payloads

## Future Enhancements

- SMS fallback for critical notifications
- Email notifications for offline drivers
- Message read receipts
- Typing indicators
- File attachments
- Voice messages









