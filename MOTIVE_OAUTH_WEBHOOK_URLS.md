# Motive OAuth 2.0 and Webhook Configuration URLs

## Production URLs

### OAuth 2.0 Redirect URI

When configuring your Motive OAuth 2.0 application, use this redirect URI:

```
https://www.freightopspro.com/api/integrations/motive/oauth/callback
```

**Note:** Motive primarily uses Client Credentials flow (not Authorization Code), so this redirect URI may not be needed. However, it's implemented for future compatibility if Motive adds Authorization Code flow support.

### Webhook Destination URL

For Motive webhook configuration, try these webhook endpoint URLs (Motive may have specific requirements):

**Primary URL:**
```
https://www.freightopspro.com/api/webhooks/motive
```

**Alternative URLs to try if the primary doesn't work:**
```
https://www.freightopspro.com/webhooks/motive
https://freightopspro.com/api/webhooks/motive
https://freightopspro.com/webhooks/motive
```

**Webhook Secret:**
If you have a webhook secret from Motive (e.g., `3b329fdc6b114d44a29a8db6f927f445`), you can:
1. Use it when creating the webhook via the API endpoint: `POST /api/integrations/motive/{integration_id}/webhooks/create?webhook_secret=YOUR_SECRET`
2. Or update it using: `POST /api/integrations/motive/{integration_id}/webhooks/update-secret` with body `{"secret": "YOUR_SECRET"}`

This endpoint:
- Does not require authentication (public endpoint)
- Accepts POST requests from Motive servers
- Validates webhook signatures using the stored secret
- Routes events to the appropriate company integration based on webhook ID

## Development URLs (for local testing)

If you need to test locally, you can use:

- **OAuth Callback:** `http://localhost:8000/api/integrations/motive/oauth/callback`
- **Webhook:** `http://localhost:8000/api/webhooks/motive`

**Note:** For local webhook testing, you'll need to use a tool like ngrok to expose your local server to the internet, as Motive needs to reach your endpoint.

## Webhook Event Types Supported

The webhook handler processes these Motive event types:

- `vehicle.location` / `location.updated` - Vehicle location updates
- `hos.violation` / `violation.created` - HOS violation alerts
- `hos.status` / `hos.updated` - HOS status changes
- `geofence.entry` / `geofence.exit` - Geofence entry/exit events
- `fault_code.created` / `fault_code.updated` - Fault code alerts

## Configuration

The base URL is configured in `backend_v2/app/core/config.py`:

```python
base_url: str = "https://www.freightopspro.com"
```

You can override this in your `.env` file if needed:

```env
BASE_URL=https://www.freightopspro.com
API_BASE_URL=https://www.freightopspro.com/api  # Optional, defaults to {BASE_URL}/api
```

## Security Notes

1. **OAuth Callback:** The callback endpoint validates the `state` parameter to ensure the request is legitimate and routes to the correct company integration.

2. **Webhooks:** The public webhook endpoint should validate webhook signatures when Motive provides them. Currently, signature validation is stubbed out and should be implemented based on Motive's webhook security documentation.

3. **Webhook ID Routing:** The webhook handler uses the `X-Motive-Webhook-Id` header to route events to the correct company integration. Make sure to store the webhook ID in your integration config when creating webhooks via the Motive API.

