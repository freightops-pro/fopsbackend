# Data Isolation Fixes - Multi-Tenant Security

## Problem Summary

The application had data isolation vulnerabilities where users from one company could potentially access data from another company if they knew the entity IDs. This was caused by:

1. **Missing `get_current_company` dependency** - Each router was creating its own `_company_id` helper
2. **Direct `db.get()` calls without company_id filtering** - Queries were fetching entities first, then checking company_id, which could leak information
3. **Inconsistent filtering patterns** - Some queries filtered in the query, others checked after fetching

## Fixes Implemented

### 1. Added `get_current_company` Dependency (`app/api/deps.py`)

Created a standardized dependency that extracts `company_id` from the authenticated user:

```python
async def get_current_company(
    current_user: User = Depends(get_current_user),
) -> str:
    """Extracts company_id from the current user for tenant isolation."""
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company"
        )
    return current_user.company_id
```

**Usage:**
```python
@router.get("/items")
async def list_items(company_id: str = Depends(get_current_company)):
    # company_id is guaranteed to be from authenticated user
    ...
```

### 2. Fixed Roles Router (`app/routers/roles.py`)

Replaced all `db.get()` calls with proper `select()` queries that filter by `company_id`:

**Before (VULNERABLE):**
```python
role = await db.get(Role, role_id)
if role.company_id != current_user.company_id:
    raise HTTPException(...)  # Too late - already fetched!
```

**After (SECURE):**
```python
result = await db.execute(
    select(Role).where(
        Role.id == role_id,
        (
            (Role.company_id == None) |  # System roles
            (Role.company_id == current_user.company_id)  # Tenant's custom roles
        )
    )
)
role = result.scalar_one_or_none()
```

### 3. Created Tenant Isolation Utilities (`app/core/tenant_isolation.py`)

Added helper functions for safe entity retrieval:

- `get_entity_by_id()` - Safely retrieves entities with company_id filtering
- `verify_entity_belongs_to_company()` - Verifies ownership without exceptions

## Security Principles Applied

### ✅ Always Filter in Query, Not After Fetching

**BAD:**
```python
entity = await db.get(Model, entity_id)
if entity.company_id != company_id:
    raise HTTPException(...)  # Information leaked!
```

**GOOD:**
```python
result = await db.execute(
    select(Model).where(
        Model.id == entity_id,
        Model.company_id == company_id
    )
)
entity = result.scalar_one_or_none()
```

### ✅ Use `get_current_company` Dependency

Instead of manually extracting `company_id` from `current_user`, use the dependency:

```python
# OLD (inconsistent)
async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.company_id

# NEW (standardized)
company_id: str = Depends(deps.get_current_company)
```

### ✅ Service Layer Should Also Filter

Even if the router filters, the service layer should also enforce company_id:

```python
async def get_load(self, company_id: str, load_id: str) -> Load:
    result = await self.db.execute(
        select(Load).where(
            Load.company_id == company_id,
            Load.id == load_id
        )
    )
    load = result.scalar_one_or_none()
    if not load:
        raise ValueError("Load not found")
    return load
```

## Files Modified

1. ✅ `app/api/deps.py` - Added `get_current_company` dependency
2. ✅ `app/routers/roles.py` - Fixed all `db.get()` calls to use filtered queries
3. ✅ `app/core/tenant_isolation.py` - Created utility functions (NEW FILE)

## Files That Are Safe

These files already properly filter by company_id:

- ✅ `app/routers/loads.py` - Uses service layer with company_id filtering
- ✅ `app/routers/company.py` - Uses `current_user.company_id` (safe)
- ✅ `app/routers/drivers.py` - Uses service layer with company_id filtering
- ✅ `app/routers/fleet.py` - Uses service layer with company_id filtering
- ✅ `app/routers/dispatch.py` - Uses service layer with company_id filtering

## Remaining Recommendations

### 1. Audit All Routers

While we've fixed the most critical issues, you should audit all routers for:

- Direct `db.get()` calls on tenant-scoped entities
- Queries that don't filter by `company_id`
- Service methods that accept entity IDs without company_id

### 2. Use Tenant Isolation Utilities

For new code, use the helper functions:

```python
from app.core.tenant_isolation import get_entity_by_id

# Instead of:
role = await db.get(Role, role_id)
if role.company_id != company_id:
    raise HTTPException(...)

# Use:
role = await get_entity_by_id(
    db, Role, role_id, company_id,
    error_message="Role not found or access denied"
)
```

### 3. Add Integration Tests

Create tests that verify data isolation:

```python
async def test_cross_tenant_isolation():
    # User from Company A tries to access Company B's data
    user_a = await create_test_user(company_id="company-a")
    user_b = await create_test_user(company_id="company-b")
    
    # Create load for Company B
    load_b = await create_test_load(company_id="company-b")
    
    # User A should not be able to access Company B's load
    with pytest.raises(HTTPException) as exc:
        await get_load(company_id="company-a", load_id=load_b.id)
    assert exc.value.status_code == 404
```

### 4. Database-Level Constraints (Optional)

Consider adding database-level constraints to prevent accidental cross-tenant data:

```sql
-- Example: Ensure all queries must include company_id
-- (This would require application-level enforcement, not SQL)
```

## Testing Checklist

- [ ] Test that users from Company A cannot access Company B's data
- [ ] Test that system roles (company_id=NULL) are accessible to all tenants
- [ ] Test that custom roles are only accessible to their tenant
- [ ] Test that 404 errors don't leak information about other tenants' data
- [ ] Test all GET/PUT/PATCH/DELETE endpoints with cross-tenant IDs

## Notes

- **Permission model**: The `Permission` table is system-wide (no company_id), so `db.get(Permission, perm_id)` is safe
- **HQ routes**: Routes under `/hq` are for platform administrators and may intentionally access cross-tenant data
- **System roles**: Roles with `company_id=NULL` are system roles accessible to all tenants

