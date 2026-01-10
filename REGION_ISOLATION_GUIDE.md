# Regional Isolation Guide

## Problem Statement

**Question**: "How do we add Brazil/Mexico/India support without breaking existing USA functionality?"

**Answer**: Complete isolation at multiple levels: code, database, and logic.

---

## Isolation Strategy - 3 Layers

### Layer 1: Code Isolation (Python Modules)

**Each region is a separate file** - they can't interfere with each other:

```
app/services/compliance/
  ├── base.py           # Interface definition (no logic)
  ├── usa.py            # US-specific logic (HOS, DOT, ELD)
  ├── brazil.py         # Brazil-specific logic (MDF-e, CIOT, SEFAZ)
  ├── mexico.py         # Mexico-specific logic (Carta de Porte)
  ├── eu.py             # EU-specific logic (Mobility Package)
  └── loader.py         # Registers engines at startup
```

**How it works**:
- USA company? Only `usa.py` loads
- Brazil company? Only `brazil.py` loads
- They never execute each other's code

**Example**:
```python
# For a USA company
engine = ComplianceEngineRegistry.get_engine("usa")
# Only USAComplianceEngine class is instantiated
# Brazil code never runs

# For a Brazil company
engine = ComplianceEngineRegistry.get_engine("brazil")
# Only BrazilComplianceEngine class is instantiated
# USA code never runs
```

---

### Layer 2: Database Isolation (Regional Tables)

**Each region has its own tables** - they don't share data:

```
Core Tables (Universal - All Regions):
  ├── company
  ├── users
  ├── loads
  ├── drivers
  └── vehicles

USA-Specific Tables (Only for US companies):
  ├── usa_hos_logs              # Hours of Service
  ├── usa_eld_events            # Electronic Logging Device data
  ├── usa_ifta_records          # Fuel tax records
  ├── usa_dot_inspections       # Roadside inspections
  └── usa_company_data          # DOT/MC/SCAC numbers

Brazil-Specific Tables (Only for Brazilian companies):
  ├── brazil_mdfe                # Electronic Cargo Manifests
  ├── brazil_cte                 # Transport Documents
  ├── brazil_ciot                # Payment codes
  ├── brazil_sefaz_submissions   # Tax authority API logs
  └── brazil_company_data        # CNPJ/RNTRC/ANTT data

Mexico-Specific Tables (Only for Mexican companies):
  ├── mexico_carta_porte         # Digital waybills
  ├── mexico_sat_submissions     # Tax authority submissions
  └── mexico_company_data        # RFC/SCT permit data
```

**Benefits**:
1. ✅ **No cross-contamination**: USA query never touches Brazil tables
2. ✅ **Schema independence**: Can modify Brazil tables without affecting USA
3. ✅ **Performance**: Smaller tables, faster queries (no filtering by region)
4. ✅ **Migration safety**: Add Brazil tables without altering USA tables

**Example Query**:
```python
# USA company loading HOS data
hos_logs = db.query(USAHOSLog).filter(
    USAHOSLog.company_id == usa_company_id
).all()
# Never queries brazil_mdfe table

# Brazil company loading MDF-e data
mdfe_records = db.query(BrazilMDFe).filter(
    BrazilMDFe.company_id == brazil_company_id
).all()
# Never queries usa_hos_logs table
```

---

### Layer 3: API Route Isolation (Optional)

**For developers** - can separate API endpoints too:

```
Option A: Shared Routes (What we have now):
  POST /loads/validate              # Uses engine based on company.operating_region
  POST /loads/generate-documents    # Uses engine based on company.operating_region

Option B: Regional Routes (More isolation):
  POST /usa/loads/validate          # Only USA logic
  POST /brazil/loads/validate       # Only Brazil logic

Option C: Subdomain (Enterprise-level):
  api-usa.freight ops.com           # USA microservice
  api-brazil.freightops.com         # Brazil microservice
```

**Recommendation**: Start with **Option A** (what we have). Move to Option B/C only if teams get large.

---

## Developer Workflow - No Interference

### Scenario 1: Adding Brazil Feature (Won't Break USA)

**Developer working on Brazil MDF-e:**

```python
# File: app/services/compliance/brazil.py

class BrazilComplianceEngine(BaseComplianceEngine):
    async def generate_shipping_document(...):
        # Generate MDF-e XML
        xml = self._generate_mdfe_xml(...)
        # Submit to SEFAZ
        response = await self._submit_to_sefaz(xml)
        return response
```

**Why USA is safe**:
1. ✅ USA companies never call `BrazilComplianceEngine`
2. ✅ USA tables (usa_hos_logs) are not touched
3. ✅ USA routes continue to work unchanged
4. ✅ USA tests don't need to run Brazil tests

---

### Scenario 2: Fixing USA Bug (Won't Break Brazil)

**Developer fixing USA HOS bug:**

```python
# File: app/services/compliance/usa.py

class USAComplianceEngine(BaseComplianceEngine):
    async def validate_driver_assignment(...):
        # Fix: Correctly check 70-hour/8-day limit
        hours_available = self._calculate_hos_hours(driver_data)
        if hours_available < 2:
            return ComplianceValidationResult(
                status=ComplianceStatus.ERROR,
                errors=["Insufficient HOS hours"]
            )
```

**Why Brazil is safe**:
1. ✅ Brazil companies never call `USAComplianceEngine`
2. ✅ Brazil tables (brazil_mdfe) are not touched
3. ✅ Brazil routes continue to work unchanged
4. ✅ Brazil tests don't need to re-run

---

## Migration Strategy - Additive Only

**Rule**: Never modify existing tables. Always add new tables.

### ❌ BAD (Breaks USA):
```sql
-- DON'T DO THIS - Adds Brazil fields to main company table
ALTER TABLE company ADD COLUMN cnpj VARCHAR;
ALTER TABLE company ADD COLUMN rntrc VARCHAR;
-- Problem: USA companies now have Brazil fields (confusing)
```

### ✅ GOOD (Isolated):
```sql
-- DO THIS - Create separate Brazil table
CREATE TABLE brazil_company_data (
    id VARCHAR PRIMARY KEY,
    company_id VARCHAR UNIQUE NOT NULL,
    cnpj VARCHAR NOT NULL,
    rntrc VARCHAR NOT NULL,
    ...
);
-- USA table untouched ✓
```

### Example Migration:

**File**: `scripts/migrations/add_brazil_support.py`

```python
async def upgrade():
    """
    Add Brazil-specific tables.
    Does NOT modify any existing USA tables.
    """
    # Create Brazil tables
    await db.execute("""
        CREATE TABLE brazil_mdfe (...);
        CREATE TABLE brazil_ciot (...);
        CREATE TABLE brazil_company_data (...);
    """)

    print("✓ Brazil tables added")
    print("✓ USA tables unchanged")
    print("✓ Existing USA data safe")
```

**File**: `scripts/migrations/add_mexico_support.py`

```python
async def upgrade():
    """
    Add Mexico-specific tables.
    Does NOT modify USA or Brazil tables.
    """
    # Create Mexico tables
    await db.execute("""
        CREATE TABLE mexico_carta_porte (...);
        CREATE TABLE mexico_sat_submissions (...);
    """)

    print("✓ Mexico tables added")
    print("✓ USA tables unchanged")
    print("✓ Brazil tables unchanged")
```

---

## Testing Strategy - Isolated Test Suites

**Separate test files** - they don't interfere:

```
tests/compliance/
  ├── test_usa.py           # USA-only tests
  ├── test_brazil.py        # Brazil-only tests
  ├── test_mexico.py        # Mexico-only tests
  └── test_integration.py   # Cross-region tests (rare)
```

**Example**:

```python
# tests/compliance/test_brazil.py
@pytest.mark.brazil
class TestBrazilCompliance:
    async def test_mdfe_generation(self):
        engine = BrazilComplianceEngine()
        result = await engine.generate_shipping_document(...)
        assert result.success
        assert "MDFe" in result.xml_content

    async def test_ciot_validation(self):
        engine = BrazilComplianceEngine()
        # Test CIOT code requirement
        ...

# tests/compliance/test_usa.py
@pytest.mark.usa
class TestUSACompliance:
    async def test_hos_validation(self):
        engine = USAComplianceEngine()
        # Test 11-hour driving limit
        ...
```

**Running tests**:
```bash
# Run only USA tests
pytest -m usa

# Run only Brazil tests
pytest -m brazil

# Run all compliance tests
pytest tests/compliance/
```

---

## Feature Flags (Extra Safety)

**Optional**: Use feature flags for gradual rollout:

```python
# app/core/config.py

class Settings(BaseSettings):
    # Feature flags per region
    ENABLE_BRAZIL_MODULE: bool = False
    ENABLE_MEXICO_MODULE: bool = False
    ENABLE_EU_MODULE: bool = False
    # USA is always enabled (default region)
```

**Usage**:
```python
def get_engine(region: str):
    if region == "brazil" and not settings.ENABLE_BRAZIL_MODULE:
        raise FeatureNotEnabled("Brazil module not enabled")

    return ComplianceEngineRegistry.get_engine(region)
```

**Benefits**:
- Deploy code to production but keep it disabled
- Enable only for specific companies (beta testing)
- Disable instantly if bugs found

---

## Summary - Complete Isolation

| Aspect | USA | Brazil | Mexico | Interference? |
|--------|-----|--------|--------|---------------|
| **Code** | `usa.py` | `brazil.py` | `mexico.py` | ❌ None - separate files |
| **Database** | `usa_*` tables | `brazil_*` tables | `mexico_*` tables | ❌ None - separate tables |
| **Tests** | `test_usa.py` | `test_brazil.py` | `test_mexico.py` | ❌ None - separate suites |
| **Migrations** | USA migrations | Brazil migrations | Mexico migrations | ❌ None - additive only |
| **APIs** | USA endpoints | Brazil endpoints | Mexico endpoints | ❌ None - registry pattern |

---

## Developer Checklist

Before adding a new region, ensure:

- [ ] Create new file: `app/services/compliance/{region}.py`
- [ ] Create regional models: `app/models/regional/{region}.py`
- [ ] Create migration: `scripts/migrations/add_{region}_support.py`
- [ ] Create tests: `tests/compliance/test_{region}.py`
- [ ] Register in loader: `compliance/loader.py`
- [ ] Document requirements: Update `GLOBAL_TMS_ARCHITECTURE.md`
- [ ] **DO NOT modify existing region's tables**
- [ ] **DO NOT modify base company/loads/drivers tables**

---

## Questions & Answers

**Q: What if a field is needed across all regions (e.g., currency)?**

**A**: Add to core `company` or `loads` table, but keep it generic:

```sql
-- ✓ GOOD - Generic field useful for all regions
ALTER TABLE loads ADD COLUMN currency_code VARCHAR(3) DEFAULT 'USD';
ALTER TABLE loads ADD COLUMN distance_km DECIMAL(10,2);

-- ✗ BAD - Region-specific field in core table
ALTER TABLE loads ADD COLUMN mdfe_number VARCHAR;  -- Brazil-specific
```

**Q: Can USA and Brazil share any code?**

**A**: Yes, but only in `base.py` (interface) or `utils/` (helpers):

```python
# ✓ GOOD - Shared utility
from app.utils.units import km_to_miles

# ✓ GOOD - Shared interface
class BaseComplianceEngine(ABC):
    @abstractmethod
    async def validate_load_before_dispatch(...):
        pass

# ✗ BAD - Cross-region imports
from app.services.compliance.brazil import BrazilComplianceEngine  # In usa.py
```

**Q: What if Brazil and Mexico need similar logic (both have digital waybills)?**

**A**: Extract to a shared helper, but keep engines separate:

```python
# app/utils/digital_waybill.py (shared)
def generate_xml_signature(xml: str, certificate: str) -> str:
    # Shared logic for XML signing
    ...

# brazil.py
from app.utils.digital_waybill import generate_xml_signature
class BrazilComplianceEngine:
    async def generate_shipping_document(...):
        xml = self._generate_mdfe_xml(...)
        signed = generate_xml_signature(xml, certificate)

# mexico.py
from app.utils.digital_waybill import generate_xml_signature
class MexicoComplianceEngine:
    async def generate_shipping_document(...):
        xml = self._generate_carta_porte_xml(...)
        signed = generate_xml_signature(xml, certificate)
```

---

## Conclusion

**Isolation = Safety**

By keeping regional logic, data, and tests completely separate, we ensure:

1. ✅ USA developers don't break Brazil
2. ✅ Brazil developers don't break USA
3. ✅ Each region can evolve independently
4. ✅ Database migrations are additive (no risk)
5. ✅ Tests run independently (faster CI/CD)
6. ✅ Easy to disable/enable regions (feature flags)

**Bottom Line**: You can add as many regions as you want without any risk to existing regions.
