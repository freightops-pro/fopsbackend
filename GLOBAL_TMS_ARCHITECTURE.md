# Global TMS Architecture - FreightOps World

## Overview

This document describes the plugin-based architecture for building a truly global Transportation Management System that works across all major freight markets.

## Core Principle: Modular Compliance Engines

**Problem**: Different countries have fundamentally different freight regulations, not just different forms.

**Solution**: Build a **plugin architecture** where each region has its own compliance engine that handles:
- Regulatory validation
- Government API integrations
- Document generation (XML, digital seals, etc.)
- Payment validation
- Route optimization rules
- Real-time tracking submission

## Architecture Layers

### Layer 1: Universal Core

**Location**: `app/models/`, `app/services/compliance/base.py`

**Purpose**: Region-agnostic data storage and interfaces

**Requirements**:
1. **Multi-Currency Ledger**
   - Store: `amount`, `currency_code`, `exchange_rate_at_transaction`
   - Why: Pay driver in MXN, invoice shipper in USD, capture spread

2. **Unit Agnostic Storage**
   - Store: All distances in kilometers, weights in kilograms (metric)
   - Convert: Display in miles/lbs only for USA/UK users in UI
   - Why: 95% of world uses metric; storing in imperial causes conversion errors

3. **UTC Timestamps**
   - Store: All dates/times in UTC
   - Display: Convert to user's local timezone in UI
   - Why: Cross-timezone operations (EU driver crossing borders)

### Layer 2: Compliance Engine Interface

**Location**: `app/services/compliance/base.py`

**Purpose**: Define the contract that all regional engines must implement

**Key Methods**:
```python
class BaseComplianceEngine(ABC):
    # Pre-dispatch validation
    async def validate_load_before_dispatch()

    # Document generation (MDF-e, Carta de Porte, e-Way Bill, BOL)
    async def generate_shipping_document()

    # Payment compliance (CIOT, minimum rates, etc.)
    async def validate_payment()

    # Driver assignment rules (HOS, Mobility Package, etc.)
    async def validate_driver_assignment()

    # AI routing rules
    def get_route_optimization_rules()

    # Government tracking submission
    async def submit_tracking_data()
```

### Layer 3: Regional Compliance Modules

**Location**: `app/services/compliance/{region}.py`

**Purpose**: Implement region-specific business logic

#### Implemented Modules:

##### 1. Brazil (`brazil.py`)
**Complexity**: ⭐⭐⭐⭐⭐ (Highest in world)

**Requirements**:
- **MDF-e**: XML manifest submitted to SEFAZ before trip starts
- **CT-e**: Electronic transport document for each shipment
- **CIOT**: Mandatory payment code from approved provider (Pamcard/Repom)
- **Security Focus**: Route optimization avoids high-theft zones
- **API Integration**: Real-time SEFAZ (tax authority) submission

**Code Example**:
```python
async def generate_shipping_document(...):
    # Generate MDF-e XML per Nota Técnica 2025.001
    xml = self._generate_mdfe_xml(...)
    # Sign with A1/A3 digital certificate
    signed_xml = self._sign_with_certificate(xml)
    # Submit to SEFAZ and get authorization
    response = await self.sefaz_client.authorize(signed_xml)
    return authorization_key
```

##### 2. USA (`usa.py`)
**Complexity**: ⭐⭐ (Moderate)

**Requirements**:
- **HOS Compliance**: 11-hour driving limit, 70-hour weekly limit
- **ELD Mandate**: Electronic logging device required
- **IFTA**: Fuel tax reporting for interstate
- **DOT/MC Numbers**: Registration requirements
- **Route Optimization**: Maximize revenue per mile, minimize deadhead

**No Government API**: Documents don't require real-time submission

#### Planned Modules:

##### 3. Mexico (`mexico.py`)
- **Carta de Porte 3.0**: Digital waybill with UUID seal
- **SAT Integration**: Tax authority digital sealing
- **GPS Jammer Detection**: Hardware integration for security
- **Route Security**: Avoid high-risk zones (similar to Brazil)

##### 4. EU (`eu.py`)
- **Mobility Package**: Return-to-home rules (max 4 weeks away)
- **Cabotage Counter**: Track internal moves per country
- **e-CMR**: Digital consignment note with QR code
- **CO2 Reporting**: GLEC Framework emissions per shipment
- **Digital Tachograph**: Driver hours tracking

##### 5. India (`india.py`)
- **e-Way Bill**: NIC API integration for loads >₹50,000
- **Part A & Part B Forms**: Invoice + vehicle details
- **GST Compliance**: Tax validation
- **SIM Tracking**: Cell tower triangulation (not GPS)

##### 6. China (`china.py`)
- **Beidou Integration**: National satellite system (not GPS)
- **WeChat Mini-Program**: Driver interface (not mobile app)
- **National Freight Platform**: Mandatory position reporting
- **Payment**: WeChat Pay integration

##### 7. Japan (`japan.py`)
- **Relay Trucking**: Trailer swap logic for 8-hour shifts
- **Zenrin Maps**: Accurate narrow street routing
- **960 Hour/Year Limit**: Annual overtime cap
- **Route Optimization**: Minimize driver overtime

## Compliance Engine Registry

**Location**: `app/services/compliance/registry.py`

**Purpose**: Central registry to load appropriate engine for a company's region

**Usage**:
```python
from app.services.compliance import ComplianceEngineRegistry

# Get engine for company's region
engine = ComplianceEngineRegistry.get_engine(company.operating_region)

# Validate before dispatch
result = await engine.validate_load_before_dispatch(load_data, company_data)

if result.status == ComplianceStatus.ERROR:
    raise ValidationError(result.errors)

# Generate shipping document
doc = await engine.generate_shipping_document(load_data, company_data, driver_data, vehicle_data)
```

## AI Route Optimization by Region

Each engine defines its own optimization rules:

| Region | Goal | Penalties | Key Constraint |
|--------|------|-----------|----------------|
| USA | Max rate/mile | Deadhead miles | HOS 11-hour limit |
| Brazil | Max security | Red zones at night | Cargo theft risk |
| EU | Min empty return | Return-to-home violation | 4 weeks away from home |
| Japan | Min overtime | Exceeding 960 hrs/year | 8-hour shift limit |
| India | Cost efficiency | GST complexity | e-Way Bill requirements |

## Required Integrations by Region

### Brazil
- ✅ **SEFAZ API** (Government) - MDF-e/CT-e authorization
- ✅ **CIOT Provider** (Payment) - Pamcard, Repom, Sem Parar
- ⚠️ **Cargo Insurance** (Optional) - Real-time tracking

### Mexico
- ✅ **SAT API** (Government) - Carta de Porte sealing
- ⚠️ **GPS Jammer Detector** (Hardware) - Security

### EU
- ✅ **e-CMR Provider** (Document) - TransFollow, Pionira
- ✅ **CO2 Calculator** (Compliance) - GLEC Framework
- ✅ **Digital Tachograph** (Hardware) - Driver hours

### India
- ✅ **NIC API** (Government) - e-Way Bill generation
- ⚠️ **GST Network** (Tax) - Invoice validation

### China
- ✅ **Beidou Platform** (Government) - Position reporting
- ✅ **WeChat API** (Communication) - Mini-Program
- ✅ **WeChat Pay** (Payment) - Driver payments

### Japan
- ✅ **Zenrin Maps** (Navigation) - Narrow street routing
- ⚠️ **Relay Coordination** (Logic) - Trailer swap points

### USA
- ✅ **ELD Provider** (Hardware) - Samsara, Motive, Geotab
- ✅ **IFTA Reporting** (Tax) - Fuel tax

## Database Schema Changes

### Core Tables (Universal)

```sql
-- All monetary values store currency
ALTER TABLE invoices ADD COLUMN currency_code VARCHAR(3) DEFAULT 'USD';
ALTER TABLE invoices ADD COLUMN exchange_rate_at_transaction DECIMAL(10,6);

-- All distances in kilometers (metric)
ALTER TABLE loads ADD COLUMN distance_km DECIMAL(10,2);
-- UI converts to miles for USA users: miles = km * 0.621371

-- All weights in kilograms (metric)
ALTER TABLE loads ADD COLUMN weight_kg DECIMAL(10,2);
-- UI converts to lbs for USA users: lbs = kg * 2.20462

-- All timestamps in UTC
ALTER TABLE loads ALTER COLUMN pickup_time TYPE TIMESTAMP WITH TIME ZONE;
```

### Company Table (Region Assignment)

```sql
ALTER TABLE company ADD COLUMN operating_region VARCHAR(50) DEFAULT 'usa';
ALTER TABLE company ADD COLUMN regional_data JSONB DEFAULT '{}';
```

**regional_data** stores region-specific fields:
- Brazil: `{"cnpj": "...", "rntrc": "...", "antt_registration": "..."}`
- India: `{"pan_number": "...", "gst_number": "...", "national_permit": "..."}`
- etc.

## Implementation Checklist

### Phase 1: Foundation ✅
- [x] Create `BaseComplianceEngine` interface
- [x] Build `ComplianceEngineRegistry`
- [x] Implement Brazil engine (most complex)
- [x] Implement USA engine (baseline)

### Phase 2: Universal Core (In Progress)
- [ ] Add currency_code, exchange_rate to all transaction tables
- [ ] Convert all distance storage to metric (km)
- [ ] Convert all weight storage to metric (kg)
- [ ] Add unit conversion utilities
- [ ] Update UI to display in user's preferred units

### Phase 3: Additional Regions
- [ ] Mexico compliance engine
- [ ] EU compliance engine
- [ ] India compliance engine
- [ ] China compliance engine
- [ ] Japan compliance engine

### Phase 4: Government API Integrations
- [ ] Brazil: SEFAZ API client
- [ ] Mexico: SAT API client
- [ ] India: NIC e-Way Bill API
- [ ] China: Beidou platform submission

### Phase 5: Payment Providers
- [ ] Brazil: CIOT provider integration (Pamcard/Repom)
- [ ] China: WeChat Pay
- [ ] General: Multi-currency payment rails

## Testing Strategy

Each compliance engine has its own test suite:

```python
# tests/compliance/test_brazil.py
async def test_mdfe_generation():
    engine = BrazilComplianceEngine()
    result = await engine.generate_shipping_document(load, company, driver, vehicle)
    assert result.success
    assert "MDFe" in result.xml_content

async def test_ciot_validation():
    engine = BrazilComplianceEngine()
    payment_without_ciot = {"amount": 5000}
    result = await engine.validate_payment(payment_without_ciot, load)
    assert result.status == ComplianceStatus.ERROR
    assert "CIOT" in result.errors[0]
```

## API Endpoints

```
GET  /regions                    # List all supported regions
GET  /regions/{code}             # Get region config
GET  /regions/{code}/fields      # Get required company fields
GET  /regions/{code}/requirements # Get compliance requirements

POST /compliance/validate-load   # Validate load pre-dispatch
POST /compliance/generate-document # Generate shipping document
POST /compliance/validate-payment # Validate payment compliance
```

## Conclusion

This modular architecture allows FreightOps to:
1. ✅ Support multiple countries without code duplication
2. ✅ Add new regions by implementing one class
3. ✅ Maintain region-specific logic in isolation
4. ✅ Scale globally without breaking existing regions
5. ✅ Meet complex government requirements (Brazil, Mexico, China, India)

**Next Steps**:
1. Complete Universal Core (currency, units, timezone)
2. Implement Mexico and EU engines
3. Build government API clients
4. Add integration tests for each region
