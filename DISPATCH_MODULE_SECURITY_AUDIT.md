# 🔍 Dispatch Module Security Audit
## Recurse ML Methodology - Bug Detection Report

**Generated:** January 26, 2025  
**Modules Analyzed:** 5 dispatch-related files  
**Critical Issues:** 8  
**High Priority:** 12  
**Medium Priority:** 6  

---

## ⚠️ CRITICAL SECURITY ISSUES

### 1. ❌ **MISSING MULTI-TENANT ISOLATION** - `loads.py`

**Location:** Lines 38-74 (`list_loads` endpoint)

**Issue:**
```python
# ❌ BAD - No company_id filter
q = db.query(SimpleLoad)
total = q.count()
items = q.order_by(SimpleLoad.createdAt.desc()).offset((page - 1) * limit).limit(limit).all()
```

**Risk Level:** 🔴 **CRITICAL - DATA LEAKAGE**  
**Impact:** Users can see ALL loads from ALL companies

**Fix Required:**
```python
# ✅ GOOD - Proper tenant isolation
company_id = token.get("companyId") or token.get("companyid")
if not company_id:
    raise HTTPException(status_code=400, detail="Missing company context")

q = db.query(SimpleLoad).filter(SimpleLoad.companyId == company_id)
total = q.count()
items = q.order_by(SimpleLoad.createdAt.desc()).offset((page - 1) * limit).limit(limit).all()
```

---

### 2. ❌ **MISSING MULTI-TENANT ISOLATION** - `loads.py`

**Location:** Lines 76-98 (`get_load` endpoint)

**Issue:**
```python
# ❌ BAD - No company_id verification
l: Optional[SimpleLoad] = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
```

**Risk Level:** 🔴 **CRITICAL - UNAUTHORIZED ACCESS**  
**Impact:** Users can access ANY load by ID, bypassing tenant boundaries

**Fix Required:**
```python
# ✅ GOOD - Verify company ownership
company_id = token.get("companyId") or token.get("companyid")
l = db.query(SimpleLoad).filter(
    SimpleLoad.id == load_id,
    SimpleLoad.companyId == company_id
).first()
```

---

### 3. ❌ **MISSING MULTI-TENANT ISOLATION** - `loads.py`

**Location:** Lines 101-151 (`list_scheduled_loads` endpoint)

**Issue:**
```python
# ❌ BAD - No company_id filter
q = (
    db.query(SimpleLoad)
    .filter(...)
)
```

**Risk Level:** 🔴 **CRITICAL - CROSS-TENANT DATA EXPOSURE**  
**Impact:** Scheduled loads from all companies are visible

**Fix Required:**
```python
# ✅ GOOD - Filter by company
company_id = token.get("companyId") or token.get("companyid")
q = (
    db.query(SimpleLoad)
    .filter(SimpleLoad.companyId == company_id)
    .filter(...)
)
```

---

### 4. ❌ **MISSING MULTI-TENANT ISOLATION** - `loads.py`

**Location:** Lines 535-565 (`assign_load` endpoint)

**Issue:**
```python
# ❌ BAD - No company verification before assignment
l: Optional[SimpleLoad] = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
```

**Risk Level:** 🔴 **CRITICAL - UNAUTHORIZED MODIFICATION**  
**Impact:** Users can assign drivers/trucks to loads they don't own

**Fix Required:**
```python
# ✅ GOOD - Verify company ownership
company_id = token.get("companyId") or token.get("companyid")
l = db.query(SimpleLoad).filter(
    SimpleLoad.id == load_id,
    SimpleLoad.companyId == company_id
).first()
```

---

### 5. ❌ **MISSING MULTI-TENANT ISOLATION** - `loads.py`

**Location:** Lines 568-620 (`update_load` endpoint), Lines 623-630 (`delete_load` endpoint)

**Issue:**
```python
# ❌ BAD - No company verification before update/delete
l: Optional[SimpleLoad] = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
```

**Risk Level:** 🔴 **CRITICAL - DATA INTEGRITY BREACH**  
**Impact:** Users can modify or delete ANY load

**Fix Required:**
```python
# ✅ GOOD - Always verify company ownership
company_id = token.get("companyId") or token.get("companyid")
if not company_id:
    raise HTTPException(status_code=400, detail="Missing company context")
    
l = db.query(SimpleLoad).filter(
    SimpleLoad.id == load_id,
    SimpleLoad.companyId == company_id
).first()
```

---

### 6. ❌ **MISSING MULTI-TENANT ISOLATION** - `loads.py`

**Location:** Lines 634-651 (`get_load_billing` endpoint)

**Issue:**
```python
# ❌ BAD - No company_id filter for billing
billing = db.query(LoadBilling).filter(LoadBilling.load_id == load_id).first()
```

**Risk Level:** 🔴 **CRITICAL - FINANCIAL DATA LEAKAGE**  
**Impact:** Users can see billing info for loads they don't own

**Fix Required:**
```python
# ✅ GOOD - Verify company ownership for financial data
company_id = token.get("companyId") or token.get("companyid")
billing = db.query(LoadBilling).filter(
    LoadBilling.load_id == load_id,
    LoadBilling.company_id == company_id
).first()
```

---

### 7. ❌ **MISSING MULTI-TENANT ISOLATION** - `loads.py`

**Location:** Lines 690-713 (`update_load_billing` endpoint)

**Issue:**
```python
# ❌ BAD - No company verification
billing = db.query(LoadBilling).filter(LoadBilling.id == billing_id).first()
```

**Risk Level:** 🔴 **CRITICAL - UNAUTHORIZED BILLING MODIFICATION**  
**Impact:** Users can modify billing for any company

**Fix Required:**
```python
# ✅ GOOD - Filter by company_id
company_id = token.get("companyId") or token.get("companyid")
billing = db.query(LoadBilling).filter(
    LoadBilling.id == billing_id,
    LoadBilling.company_id == company_id
).first()
```

---

### 8. ❌ **MISSING MULTI-TENANT ISOLATION** - `loads.py`

**Location:** Lines 717-735 (`get_load_accessorials` endpoint)

**Issue:**
```python
# ❌ BAD - No company_id filter
accessorials = db.query(LoadAccessorial).filter(LoadAccessorial.load_id == load_id).all()
```

**Risk Level:** 🔴 **CRITICAL - FINANCIAL DATA EXPOSURE**  
**Impact:** Cross-tenant accessorial charges visible

**Fix Required:**
```python
# ✅ GOOD - Verify company ownership
company_id = token.get("companyId") or token.get("companyid")
# First verify load ownership
load = db.query(SimpleLoad).filter(
    SimpleLoad.id == load_id,
    SimpleLoad.companyId == company_id
).first()
if not load:
    raise HTTPException(status_code=404, detail="Load not found")

accessorials = db.query(LoadAccessorial).filter(
    LoadAccessorial.load_id == load_id,
    LoadAccessorial.company_id == company_id
).all()
```

---

## 🟠 HIGH PRIORITY ISSUES

### 9. ⚠️ **Bare Exception Handling** - `loads.py`

**Location:** Lines 354-359, 813-834, 856-880

**Issue:**
```python
except:
    pass  # ❌ BAD - Silent failure
```

**Risk:** Silent failures can hide critical bugs

**Fix:**
```python
except Exception as e:
    logger.warning(f"Geocoding failed for address: {stop_data.address}, error: {str(e)}")
    # Continue without coordinates
```

---

### 10. ⚠️ **Missing Transaction Rollback** - Multiple Locations

**Location:** Lines 208-211, 340-342, 378-380, etc.

**Issue:**
```python
db.add(l)
db.commit()  # ❌ No try/except wrapper
```

**Risk:** Database inconsistency on errors

**Fix:**
```python
try:
    db.add(l)
    db.commit()
    db.refresh(l)
except Exception as e:
    db.rollback()
    raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
```

---

### 11. ⚠️ **Missing Input Validation** - `loads.py`

**Location:** Lines 153-211 (`create_load` endpoint)

**Issue:**
```python
def create_load(payload: dict, ...):  # ❌ Using dict instead of Pydantic model
```

**Risk:** No type safety, validation bypassed

**Fix:**
```python
from app.schema.load_schema import LoadCreate

def create_load(payload: LoadCreate, ...):  # ✅ Use Pydantic model
```

---

### 12. ⚠️ **Missing Response Model** - `loads.py`

**Location:** Lines 38-74, 76-98, 101-151, etc.

**Issue:**
```python
@router.get("/")  # ❌ No response_model
def list_loads(...):
```

**Risk:** Data leakage, no schema validation

**Fix:**
```python
from app.schema.load_schema import LoadListResponse

@router.get("/", response_model=LoadListResponse)
def list_loads(...):
```

---

### 13. ⚠️ **SQL Null Comparison** - `loads.py`

**Location:** Lines 122-128

**Issue:**
```python
(SimpleLoad.pickupDate != None)  # ❌ Python None comparison in SQL
```

**Risk:** May not work correctly in all SQL dialects

**Fix:**
```python
from sqlalchemy import and_, or_

(SimpleLoad.pickupDate.isnot(None))  # ✅ SQLAlchemy proper null check
# OR
(SimpleLoad.pickupDate != null())
```

---

### 14. ⚠️ **Missing Error Context** - `truck_assignment.py`

**Location:** Lines 24-34, 36-46, etc.

**Issue:**
```python
except Exception as e:
    raise HTTPException(status_code=500, detail=f"Failed to...: {str(e)}")
    # ❌ Stack trace exposed to client
```

**Risk:** Information leakage

**Fix:**
```python
except Exception as e:
    logger.error(f"Failed to get truck assignment: {str(e)}", exc_info=True)
    raise HTTPException(status_code=500, detail="Failed to get truck assignment")
```

---

### 15. ⚠️ **No Rate Limiting** - All Endpoints

**Risk:** API abuse, DDoS vulnerability

**Fix:** Add rate limiting middleware:
```python
from app.middleware.rate_limit import rate_limit

@router.post("/", dependencies=[Depends(rate_limit(calls=10, period=60))])
```

---

### 16. ⚠️ **Missing Audit Logging** - Critical Operations

**Location:** Load creation, assignment, billing updates

**Risk:** No audit trail for compliance

**Fix:**
```python
from app.services.audit_service import log_action

log_action(
    user_id=token.get("userId"),
    company_id=company_id,
    action="load_created",
    resource_id=load.id,
    details={"load_number": load.loadNumber}
)
```

---

### 17. ⚠️ **OCR Service Not Imported** - `loads.py`

**Location:** Lines 814, 860

**Issue:**
```python
extracted_data = ocr_service.extract_load_data(...)  # ❌ Not imported
```

**Risk:** Runtime error

**Fix:**
```python
from app.services import ocr_service  # ✅ Add import at top
```

---

### 18. ⚠️ **Inconsistent Token Extraction** - Multiple Files

**Location:** Throughout all files

**Issue:**
```python
company_id = token.get("companyId") or token.get("companyid")  # ❌ Inconsistent
```

**Risk:** Bugs from case sensitivity

**Fix:** Create helper function:
```python
def get_company_id_from_token(token: dict) -> str:
    company_id = token.get("companyId") or token.get("companyid") or token.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="Missing company context")
    return company_id
```

---

### 19. ⚠️ **Missing Pagination** - `loads.py`

**Location:** Lines 717-735 (accessorials)

**Issue:**
```python
accessorials = db.query(LoadAccessorial).filter(...).all()  # ❌ No limit
```

**Risk:** Performance issue with large datasets

**Fix:**
```python
@router.get("/load-accessorials/{load_id}")
def get_load_accessorials(
    load_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    ...
):
    ...
    .offset((page - 1) * limit).limit(limit).all()
```

---

### 20. ⚠️ **No Database Index Verification**

**Risk:** Slow queries on large datasets

**Recommendation:** Ensure indexes exist on:
- `SimpleLoad.companyId`
- `SimpleLoad.status`
- `SimpleLoad.pickupDate`
- `SimpleLoad.deliveryDate`
- `LoadBilling.load_id`
- `LoadAccessorial.load_id`

---

## 🟡 MEDIUM PRIORITY ISSUES

### 21. 📝 **Missing Docstrings** - Multiple Functions

**Location:** Various utility functions

**Recommendation:** Add docstrings:
```python
def parse_dt(value: Optional[str]) -> Optional[datetime]:
    """
    Parse datetime from string in ISO format or YYYY-MM-DD.
    
    Args:
        value: Date string in ISO format or YYYY-MM-DD
        
    Returns:
        datetime object or None if parsing fails
    """
```

---

### 22. 📝 **Inconsistent Status Codes**

**Location:** Multiple error handlers

**Issue:** Some use 500, some use 400 inconsistently

**Fix:** Use appropriate codes:
- 400: Bad Request (client error)
- 404: Not Found
- 403: Forbidden (authorization)
- 500: Internal Server Error (unexpected)

---

### 23. 📝 **Magic Numbers** - `loads.py`

**Location:** Line 321

**Issue:**
```python
load_number = f"LD-{str(uuid4())[:8].upper()}"  # ❌ Magic number 8
```

**Fix:**
```python
LOAD_NUMBER_PREFIX_LENGTH = 8
load_number = f"LD-{str(uuid4())[:LOAD_NUMBER_PREFIX_LENGTH].upper()}"
```

---

### 24. 📝 **Duplicate Code** - Response Serialization

**Location:** Multiple endpoints returning similar load data

**Fix:** Create helper function:
```python
def serialize_load(load: SimpleLoad) -> dict:
    """Convert SimpleLoad model to response dict"""
    return {
        "id": load.id,
        "loadNumber": load.loadNumber,
        # ... etc
    }
```

---

### 25. 📝 **Missing Type Hints** - `loads.py`

**Location:** Line 26

**Issue:**
```python
def parse_dt(value: Optional[str]) -> Optional[datetime]:  # ✅ Good
```

But some functions missing return types.

---

### 26. 📝 **Inconsistent Naming**

**Location:** Throughout

**Issue:** Mix of camelCase and snake_case in dict keys

**Fix:** Standardize on snake_case for Python:
```python
{
    "load_number": l.loadNumber,  # Convert at serialization
    "customer_name": l.customerName,
}
```

---

## 📊 Summary Statistics

| Category | Count |
|----------|-------|
| **Critical (Multi-tenant)** | 8 |
| **High (Security/Data)** | 12 |
| **Medium (Code Quality)** | 6 |
| **Total Issues** | 26 |

---

## 🎯 Priority Fix Order

### Immediate (Do First):
1. **Fix ALL multi-tenant isolation issues** (Issues #1-8)
   - Every query MUST filter by `company_id`
   - Add middleware to enforce this

2. **Fix bare exception handling** (Issue #9)
   - Replace all `except:` with specific exceptions

3. **Add transaction rollbacks** (Issue #10)
   - Wrap all db.commit() in try/except

### Next Sprint:
4. Replace `dict` with Pydantic models (Issue #11)
5. Add response models to all endpoints (Issue #12)
6. Fix SQL null comparisons (Issue #13)
7. Add proper error logging (Issue #14)

### Code Quality:
8. Add rate limiting
9. Add audit logging
10. Fix imports and inconsistencies
11. Add docstrings and type hints

---

## 🔧 Automated Fix Script

Create a helper function in `app/utils/tenant_helpers.py`:

```python
from fastapi import HTTPException
from sqlalchemy.orm import Session, Query
from typing import TypeVar, Optional

T = TypeVar('T')

def get_tenant_filtered_query(
    db: Session,
    model: T,
    token: dict,
    **filters
) -> Query:
    """
    Get a query filtered by company_id for multi-tenant isolation.
    
    Args:
        db: Database session
        model: SQLAlchemy model class
        token: JWT token dict
        **filters: Additional filters
        
    Returns:
        Query object with company_id filter applied
        
    Raises:
        HTTPException: If company_id missing from token
    """
    company_id = token.get("companyId") or token.get("companyid")
    if not company_id:
        raise HTTPException(status_code=400, detail="Missing company context")
    
    query = db.query(model).filter(model.companyId == company_id)
    
    for key, value in filters.items():
        query = query.filter(getattr(model, key) == value)
    
    return query
```

**Usage:**
```python
# Instead of:
l = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()

# Use:
from app.utils.tenant_helpers import get_tenant_filtered_query
l = get_tenant_filtered_query(db, SimpleLoad, token, id=load_id).first()
```

---

## ✅ Recommended Actions

1. **URGENT:** Fix all multi-tenant isolation issues before next deployment
2. **HIGH:** Add integration tests for multi-tenant scenarios
3. **MEDIUM:** Refactor to use Pydantic models consistently
4. **LOW:** Improve code documentation

---

**Report Generated by:** Recurse ML Methodology  
**Scan Type:** Multi-Tenant Security & Bug Detection  
**Date:** January 26, 2025


