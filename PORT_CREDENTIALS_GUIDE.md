# Port Credentials Management System

## Overview

The Port Credentials Management System is a comprehensive add-on feature that enables FreightOps users to connect to major US container ports for real-time container tracking, vessel scheduling, gate operations, and document management.

## Features

### 🔐 Secure Credential Management
- **AES-256 Encryption**: All credentials encrypted using Fernet (AES-128 with HMAC)
- **Key Derivation**: PBKDF2 with 100,000 iterations for enhanced security
- **Zero-Downtime Rotation**: 24-hour grace period for credential updates
- **Audit Trail**: Complete logging of all credential access and modifications

### 💰 Dual Pricing Model
- **Pay-Per-Request**: $0.50-$2.00 per API call (ideal for <100 requests/month)
- **Unlimited Monthly**: $99/month for unlimited API calls (ideal for 100+ requests/month)
- **Smart Recommendations**: Automatic suggestions based on usage patterns
- **Usage Tracking**: Detailed analytics and cost optimization

### 🚢 Port Coverage
- **10 Major US Ports**: Los Angeles, Long Beach, NY/NJ, Savannah, Houston, Seattle, Oakland, Charleston, Virginia, Tacoma
- **Multiple Auth Types**: API Key, OAuth2, JWT, Client Certificate, Basic Auth
- **Compliance Standards**: TWIC, C-TPAT, ISF, AMS requirements mapped
- **Service Coverage**: Vessel scheduling, container tracking, gate operations, document upload, berth availability

## Quick Start

### 1. Enable Port Credentials Add-on

Navigate to **Settings → Integrations → Port Integration** and choose your pricing model:

#### Pay-as-you-go Option
- Container tracking: $0.50
- Vessel schedule: $1.00  
- Gate status: $1.50
- Document upload: $2.00
- Berth availability: $0.75

#### Unlimited Monthly Option
- $99/month flat rate
- Unlimited API calls to all ports
- All services included
- Breakeven at ~132 requests/month

### 2. Configure Port Credentials

For each port you want to use:

1. Click **"Add Credentials"**
2. Select the port from the dropdown
3. Choose credential type (API Key, OAuth2, etc.)
4. Enter your port-specific credentials
5. Set expiration date (optional)
6. Click **"Save Credentials"**

### 3. Start Using Port APIs

Once configured, you can use the port APIs through FreightOps:

```javascript
// Track a container
const response = await fetch('/api/ports/operations/track-container', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    port_code: 'USLAX',
    container_number: 'ABCD1234567'
  })
});

// Get vessel schedule
const schedule = await fetch('/api/ports/operations/vessel-schedule', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    port_code: 'USLGB',
    vessel_id: 'COSCO001'
  })
});
```

## API Reference

### Authentication

All port API endpoints require:
1. Valid user authentication
2. Company with enabled port credentials add-on
3. Valid port credentials for the specific port

### Endpoints

#### Port Registry
- `GET /api/ports/available` - List all available ports
- `GET /api/ports/addon/status` - Get add-on status and usage stats

#### Add-on Management
- `POST /api/ports/addon/enable` - Enable port credentials add-on
- `POST /api/ports/addon/switch-pricing` - Switch between pricing models

#### Credential Management
- `POST /api/ports/credentials` - Store encrypted credentials
- `GET /api/ports/credentials` - List company credentials
- `POST /api/ports/credentials/{id}/validate` - Validate credentials

#### Port Operations (Billable)
- `POST /api/ports/operations/track-container` - Track container status
- `POST /api/ports/operations/vessel-schedule` - Get vessel schedule
- `POST /api/ports/operations/gate-status` - Get gate operations status
- `POST /api/ports/operations/document-upload` - Upload port documents
- `POST /api/ports/operations/berth-availability` - Check berth availability

#### Health & Monitoring
- `GET /api/ports/health/{port_code}` - Check port API health

### Request/Response Examples

#### Track Container
```json
// Request
{
  "port_code": "USLAX",
  "container_number": "ABCD1234567"
}

// Response
{
  "container_number": "ABCD1234567",
  "status": "in_port",
  "location": "Yard Block A-12",
  "last_movement": "2024-01-15T10:30:00Z",
  "terminal": "Terminal 1",
  "vessel": null,
  "holds": [],
  "estimated_gate_time": "2024-01-15T14:00:00Z",
  "weight": "25,000 kg",
  "seal_number": "SEAL123456",
  "customs_status": "cleared",
  "usage_cost": 0.50
}
```

#### Vessel Schedule
```json
// Request
{
  "port_code": "USLGB",
  "vessel_id": "COSCO001"
}

// Response
{
  "vessels": [
    {
      "vessel_name": "COSCO SHIPPING UNIVERSE",
      "imo_number": "9154683",
      "vessel_id": "COSCO001",
      "eta": "2024-01-17T08:00:00Z",
      "etd": "2024-01-18T16:00:00Z",
      "berth": "A-5",
      "terminal": "Terminal 1",
      "voyage_number": "001E",
      "status": "inbound",
      "cargo_type": "container"
    }
  ],
  "port_code": "USLGB",
  "timestamp": "2024-01-15T10:00:00Z",
  "usage_cost": 1.00
}
```

## Security Protocols

### Credential Encryption
- **Algorithm**: Fernet (AES-128 with HMAC authentication)
- **Key Derivation**: PBKDF2 with SHA-256, 100,000 iterations
- **Salt**: Static salt per application instance
- **Storage**: Encrypted credentials stored in database
- **Access**: Credentials only decrypted during API calls

### Access Control
- **Company Isolation**: Credentials are company-scoped
- **User Authentication**: All operations require valid user session
- **Audit Logging**: Complete trail of credential access
- **Rate Limiting**: API calls limited per port specifications

### Credential Rotation
- **Zero-Downtime**: Old credentials remain active for 24 hours
- **Validation**: New credentials validated before activation
- **Rollback**: Automatic rollback if validation fails
- **Notification**: Users notified of rotation status

## Pricing & Billing

### Cost Structure

| Operation | Pay-Per-Request | Unlimited Monthly |
|-----------|----------------|-------------------|
| Container Tracking | $0.50 | Included |
| Vessel Schedule | $1.00 | Included |
| Gate Status | $1.50 | Included |
| Document Upload | $2.00 | Included |
| Berth Availability | $0.75 | Included |

### Billing Models

#### Pay-Per-Request
- **Best For**: Companies with <100 requests/month
- **Billing**: Monthly invoice for actual usage
- **Tracking**: Real-time usage monitoring
- **Optimization**: Smart recommendations for cost savings

#### Unlimited Monthly
- **Best For**: Companies with 100+ requests/month
- **Price**: $99/month flat rate
- **Breakeven**: ~132 requests/month (at average $0.75/request)
- **Billing**: Recurring monthly subscription

### Usage Analytics

The system provides detailed usage analytics:
- **Monthly Usage**: Requests and costs by month
- **Port Breakdown**: Usage by port and operation type
- **Cost Trends**: Historical cost analysis
- **Recommendations**: Automatic pricing optimization suggestions

## Supported Ports

### West Coast Ports

#### Port of Los Angeles (USLAX)
- **Auth Type**: OAuth2
- **Services**: Vessel scheduling, container tracking, gate operations, document upload
- **Rate Limits**: 100 requests/minute, 10,000/day
- **Compliance**: TWIC, C-TPAT, ISF, AMS required

#### Port of Long Beach (USLGB)
- **Auth Type**: API Key
- **Services**: Vessel scheduling, container tracking, gate operations
- **Rate Limits**: 80 requests/minute, 8,000/day
- **Compliance**: TWIC, C-TPAT, ISF required

#### Port of Seattle (USSEA)
- **Auth Type**: OAuth2
- **Services**: Vessel scheduling, container tracking, gate operations
- **Rate Limits**: 70 requests/minute, 7,000/day
- **Compliance**: TWIC, ISF required

#### Port of Oakland (USOAK)
- **Auth Type**: API Key
- **Services**: Vessel scheduling, container tracking, gate operations
- **Rate Limits**: 60 requests/minute, 6,000/day
- **Compliance**: TWIC, ISF required

#### Port of Tacoma (USTIW)
- **Auth Type**: OAuth2
- **Services**: Vessel scheduling, container tracking, gate operations
- **Rate Limits**: 45 requests/minute, 4,500/day
- **Compliance**: TWIC, ISF required

### East Coast Ports

#### Port of New York & New Jersey (USNYC)
- **Auth Type**: JWT
- **Services**: Vessel scheduling, container tracking, document upload, berth availability
- **Rate Limits**: 120 requests/minute, 12,000/day
- **Compliance**: TWIC, C-TPAT, ISF, AMS, C-TPAT Tier 3 required

#### Port of Savannah (USSAV)
- **Auth Type**: API Key
- **Services**: Vessel scheduling, gate operations, berth availability
- **Rate Limits**: 90 requests/minute, 9,000/day
- **Compliance**: TWIC, ISF required

#### Port of Charleston (USCHS)
- **Auth Type**: Basic Auth
- **Services**: Vessel scheduling, container tracking, gate operations
- **Rate Limits**: 55 requests/minute, 5,500/day
- **Compliance**: TWIC, ISF required

#### Port of Virginia (USORF)
- **Auth Type**: API Key
- **Services**: Vessel scheduling, container tracking, gate operations
- **Rate Limits**: 50 requests/minute, 5,000/day
- **Compliance**: TWIC, ISF required

### Gulf Coast Ports

#### Port of Houston (USHOU)
- **Auth Type**: Client Certificate
- **Services**: Vessel scheduling, container tracking, berth availability
- **Rate Limits**: 75 requests/minute, 7,500/day
- **Compliance**: TWIC, C-TPAT, ISF, AMS, petroleum license required

## Error Handling & Recovery

### Common Error Scenarios

#### Authentication Failures
- **401 Unauthorized**: Invalid or expired credentials
- **403 Forbidden**: Insufficient permissions
- **Recovery**: Validate and rotate credentials

#### Rate Limiting
- **429 Too Many Requests**: API rate limit exceeded
- **Recovery**: Automatic retry with exponential backoff

#### Network Issues
- **Timeout**: Network connectivity problems
- **Recovery**: Retry with circuit breaker pattern

#### Port API Errors
- **5xx Server Errors**: Port API unavailable
- **Recovery**: Failover to backup endpoints (if available)

### Error Response Format
```json
{
  "error": "Port API temporarily unavailable",
  "message": "The Port of Los Angeles API is currently experiencing issues",
  "port_code": "USLAX",
  "operation": "track_container",
  "timestamp": "2024-01-15T10:00:00Z",
  "retry_after": 300
}
```

## Monitoring & Health Checks

### Health Check Endpoints
- **Port Status**: Real-time health monitoring
- **Credential Validation**: Periodic credential verification
- **Performance Metrics**: Response time and success rate tracking

### Alerting
- **Credential Expiration**: 30-day advance warning
- **API Failures**: Consecutive failure threshold alerts
- **Usage Anomalies**: Unusual usage pattern detection

### Metrics Tracked
- **Response Times**: API call latency
- **Success Rates**: Operation success/failure ratios
- **Usage Patterns**: Request frequency and volume
- **Cost Analysis**: Billing and optimization metrics

## Troubleshooting

### Common Issues

#### "Port Credentials add-on required"
- **Cause**: Company hasn't enabled the port credentials add-on
- **Solution**: Enable add-on in Settings → Integrations → Port Integration

#### "No credentials configured for port"
- **Cause**: No credentials stored for the requested port
- **Solution**: Add credentials for the port in the Port Credentials section

#### "Credential validation failed"
- **Cause**: Stored credentials are invalid or expired
- **Solution**: Update credentials or contact port for new credentials

#### "Rate limit exceeded"
- **Cause**: Too many requests to port API
- **Solution**: Wait for rate limit reset or upgrade to unlimited plan

### Debug Mode
Enable debug logging by setting `DEBUG=true` in environment variables to get detailed API call information.

### Support
For technical support or questions:
- **Email**: support@freightops.com
- **Documentation**: https://docs.freightops.com/port-credentials
- **Status Page**: https://status.freightops.com

## FAQ

### Q: Can I use multiple pricing models?
A: No, each company can only have one active pricing model at a time. You can switch between pay-per-request and unlimited monthly.

### Q: Are there any setup fees?
A: No setup fees. You only pay for the add-on subscription and actual API usage.

### Q: Can I get custom pricing for high volume?
A: Yes, contact sales@freightops.com for enterprise pricing options.

### Q: How often are usage statistics updated?
A: Usage statistics are updated in real-time for current month and daily for historical data.

### Q: Can I export usage data?
A: Yes, usage data can be exported via the API or requested through support.

### Q: What happens if a port API is down?
A: The system will retry with exponential backoff and notify you of any persistent issues.

### Q: Can I use this with existing port integrations?
A: Yes, the Port Credentials system can work alongside existing integrations or replace them entirely.

### Q: Is there a free trial?
A: Yes, new companies get a 14-day free trial with 100 free API calls.

## Changelog

### Version 1.0.0 (January 2024)
- Initial release
- Support for 10 major US ports
- Dual pricing model (pay-per-request and unlimited monthly)
- Secure credential encryption and management
- Real-time usage tracking and billing
- Smart pricing recommendations
- Comprehensive audit logging
- Health monitoring and alerting

---

*For the most up-to-date information, visit our [documentation portal](https://docs.freightops.com/port-credentials).*









