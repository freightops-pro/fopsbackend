# Port Terminal API Acquisition Guide

## Reality Check

**Most port terminals do NOT offer public developer APIs.** The shipping industry still relies heavily on:
- EDI (Electronic Data Interchange) - 315/322 messages
- Web portals with manual login
- Third-party aggregators who have negotiated data access

This guide covers your actual options for container tracking integration.

---

## Option 1: Direct Port Integration (Limited)

### Port Houston (USHOU) ✅ Has API
**System:** Navis N4 EVP (External Vessel Planning)

**Contact:**
- Customer Service: 713-670-2400
- EDI Team: [email protected]
- Website: https://porthouston.com

**Process:**
1. Contact Port Houston EDI team
2. Sign data sharing agreement
3. Receive OAuth2 credentials (client_id, client_secret)
4. API Base: `https://api.porthouston.naviscloudops.com/v3/evp`

**Notes:** Port Houston is one of the few US ports with documented API access.

---

### Georgia Ports Authority - Savannah (USSAV)
**System:** Navis N4 (same as Houston)

**Contact:**
- Customer Service: 912-963-5526
- General: [email protected]
- **EDI Team: [email protected]** ← Primary contact for API/EDI
- Website: https://gaports.com

**Process:**
1. Email [email protected] requesting API/EDI integration
2. Specify you need container tracking data (EDI 315)
3. They will provide integration specifications
4. WebAccess portal: https://webaccess.gaports.com

**Resources:**
- [N4 FAQs](https://gaports.com/n4/n4-faqs/)
- [Customer Experience](https://gaports.com/departments/customer-experience/)

---

### LA/Long Beach Terminals (USLAX/USLGB) ⚠️ No Public APIs

Most LA/LB terminals use **eModal** for appointments but container data APIs are not publicly available.

| Terminal | System | Contact |
|----------|--------|---------|
| TraPac | eModal | https://www.trapac.com |
| Fenix Marine (FMS) | Proprietary | https://fenixmarineservices.com |
| LBCT | Navis + API (truckers only) | https://www.lbct.com |
| APM Pier 400 | Navis | https://www.apmterminals.com/los-angeles |
| Yusen (YTI) | eModal | https://yusen-terminals.com |
| Everport | eModal | https://www.everport.com |
| SSA Marine | eModal | https://ssamarine.com |
| TTI | eModal | https://ttilgb.com |
| PCT | eModal | https://www.pilotterminal.com |

**eModal Platform:**
- Website: https://www.emodal.com
- Used for appointments, not container tracking
- No public developer API

**LBCT Special Note:**
LBCT offers an API specifically for trucking companies - contact them directly if you operate trucks.

---

### NY/NJ Terminals (USNYC/USEWR) ⚠️ No Public APIs

| Terminal | Operator | Portal |
|----------|----------|--------|
| PNCT | Ports America | https://mtosportalec.portsamerica.com |
| APM Elizabeth | APM Terminals | https://www.apmterminals.com/elizabeth |
| Maher | Maher Terminals | https://www.maherterminals.com |
| GCT Bayonne | GCT USA | https://www.gct.com |
| GCT NY | GCT USA | https://www.gct.com |
| Red Hook | Red Hook Container Terminal | https://www.redhookcontainerterminal.com |

**PNCT TOS Web Portal:**
- URL: https://www.pnct.net/content/show/TWP
- Offers container inquiry by number or BL
- MultiTrack feature for multiple containers
- Notifications available
- **No developer API** - portal access only

---

## Option 2: EDI Integration (Traditional)

EDI is the industry standard for terminal data exchange.

### EDI Message Types for Container Tracking

| Code | Name | Purpose |
|------|------|---------|
| 315 | Status Details | Container milestone events |
| 322 | Terminal Status | Terminal-specific events |
| 304 | Shipping Instructions | Booking confirmation |
| 301 | Ocean Booking | Booking request |

### How to Set Up EDI

1. **Contact each port's EDI team**
2. **Sign trading partner agreement**
3. **Exchange AS2 certificates** or set up VAN connection
4. **Map EDI messages** to your system
5. **Test in sandbox** environment
6. **Go live**

### EDI Service Providers (VANs)

- **Descartes** - https://www.descartes.com
- **Cleo** - https://www.cleo.com
- **SPS Commerce** - https://www.spscommerce.com
- **TrueCommerce** - https://www.truecommerce.com

**Cost:** $200-500/month base + per-message fees

### Pros/Cons of EDI

✅ Industry standard, reliable
✅ Direct from source
✅ No third-party dependency
❌ Requires setup with EACH port
❌ Technical complexity (AS2, X12 format)
❌ Slower to implement
❌ Per-port maintenance

---

## Option 3: Third-Party Aggregators (Recommended for TMS)

These companies have already negotiated data access with terminals and carriers, offering unified APIs.

### Terminal49 ⭐ Recommended

**Website:** https://terminal49.com

**API Docs:** https://terminal49.com/docs/home

**Pricing:**
- Free Developer tier: 100 containers/month
- Paid: Starting at $350/month
- Volume-based pricing available

**Coverage:**
- 100% of ocean carriers to North America
- All major US terminals
- Rail tracking
- AIS vessel data

**Features:**
- REST API with JSON
- Webhooks for real-time updates
- Last Free Day (LFD)
- Hold status
- Yard location
- FIRMS codes

**Getting Started:**
1. Sign up at https://terminal49.com
2. Get API key from developer dashboard
3. Use their quickstart guide: https://terminal49.com/docs/api-docs/in-depth-guides/quickstart/

```python
# Example Terminal49 API call
import requests

headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}

# Track a container
response = requests.post(
    "https://api.terminal49.com/v2/tracking_requests",
    headers=headers,
    json={
        "data": {
            "type": "tracking_request",
            "attributes": {
                "request_type": "bill_of_lading",
                "request_number": "MAEU123456789",
                "scac": "MAEU"
            }
        }
    }
)
```

---

### Vizion API

**Website:** https://www.vizionapi.com

**API Docs:** https://docs.vizionapi.com

**Pricing:** Contact sales (subscription model)

**Coverage:**
- Ocean carriers
- US terminals
- Class I railways (intermodal)
- AIS data

**Features:**
- REST API
- Webhooks
- Multiple data sources (EDI, AIS, terminals)
- 6-hour or less latency

**Getting Started:**
1. Contact sales at https://www.vizionapi.com
2. Receive API key
3. Follow docs at https://docs.vizionapi.com/reference/introduction

---

### project44

**Website:** https://www.project44.com

**Type:** Enterprise-grade visibility platform

**Best for:** Large shippers, 3PLs, enterprises

**Features:**
- Multi-modal tracking
- Predictive ETAs
- Analytics

**Pricing:** Enterprise pricing (contact sales)

---

### Comparison

| Feature | Terminal49 | Vizion | project44 |
|---------|------------|--------|-----------|
| Free tier | ✅ 100 containers | ❌ | ❌ |
| Starting price | $350/mo | Contact | Enterprise |
| US Terminals | ✅ | ✅ | ✅ |
| Rail | ✅ | ✅ | ✅ |
| LFD data | ✅ | ✅ | ✅ |
| Webhooks | ✅ | ✅ | ✅ |
| Best for | SMB TMS | Mid-market | Enterprise |

---

## Recommendation for FreightOps TMS

### Short-term (MVP)
Use **Terminal49** API:
1. Free tier for development/testing
2. Unified API for all ports/carriers
3. Good documentation
4. Affordable for growing TMS

### Integration Code

```python
# app/services/port/terminal49_adapter.py

import httpx
from datetime import datetime
from typing import Optional
from app.core.config import settings


class Terminal49Adapter:
    """Terminal49 API adapter for container tracking."""

    BASE_URL = "https://api.terminal49.com/v2"

    def __init__(self):
        self.api_key = settings.terminal49_api_key

    async def track_container(
        self,
        container_number: str,
        carrier_scac: Optional[str] = None,
    ):
        """Track container via Terminal49."""
        async with httpx.AsyncClient() as client:
            # Create tracking request
            response = await client.post(
                f"{self.BASE_URL}/tracking_requests",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "data": {
                        "type": "tracking_request",
                        "attributes": {
                            "request_type": "container",
                            "request_number": container_number,
                            "scac": carrier_scac,
                        }
                    }
                }
            )

            data = response.json()

            # Parse response
            attributes = data.get("data", {}).get("attributes", {})

            return {
                "container_number": container_number,
                "status": attributes.get("status"),
                "port_code": attributes.get("pod_locode"),
                "terminal": attributes.get("pod_terminal_name"),
                "last_free_day": attributes.get("last_free_day"),
                "holds": attributes.get("holds", []),
                "is_available": attributes.get("available_for_pickup"),
                "vessel_name": attributes.get("vessel_name"),
                "vessel_eta": attributes.get("vessel_eta"),
            }
```

### Config Addition

```python
# Add to app/core/config.py

# Terminal49 API (container tracking aggregator)
# Sign up at: https://terminal49.com
terminal49_api_key: Optional[str] = None
```

---

## Summary

| Approach | Cost | Complexity | Coverage | Recommendation |
|----------|------|------------|----------|----------------|
| Direct Port APIs | Free | High | Limited | Only for Houston/Savannah |
| EDI | $200-500/mo | Very High | Good | For enterprises with EDI infrastructure |
| Terminal49 | $0-350+/mo | Low | Excellent | **Best for TMS** |
| Vizion | Contact | Low | Excellent | Good alternative |

**For a TMS product**, the practical path is:

1. **Start with Terminal49** free tier during development
2. **Upgrade to paid** when you have paying customers
3. **Keep direct port adapters** for Houston/Savannah as fallback
4. **Consider EDI** only if specific customers require it

---

## Sources

- [Terminal49 API Pricing](https://terminal49.com/api-pricing)
- [Terminal49 Developer Docs](https://terminal49.com/docs/home)
- [Vizion API Overview](https://www.vizionapi.com/container-tracking/api-overview)
- [Georgia Ports N4 FAQs](https://gaports.com/n4/n4-faqs/)
- [PNCT TOS Web Portal](https://www.pnct.net/content/show/TWP)
- [eModal Platform](https://www.emodal.com)
