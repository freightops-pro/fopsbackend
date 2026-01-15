# HQ Employee Database Hotfix - January 14, 2026

## Problem

The production HQ login was failing with error:
```
column hq_employee.referral_code_generated_at does not exist
```

## Root Cause

The `HQEmployee` model (app/models/hq_employee.py) was updated with new columns for Master Spec Module 4, but the migration (20260112_master_spec_alignment.py) didn't include all the columns.

### Missing from Database:
1. `referral_code_generated_at` - Timestamp when referral code was generated
2. `commission_rate_mrr` - Commission % on MRR
3. `commission_rate_setup` - Commission % on setup fees
4. `commission_rate_fintech` - Commission % on fintech revenue
5. Naming mismatch: Model uses `lifetime_*` but migration created `total_*` columns

### Extra in Database (not in model):
1. `is_affiliate` - Boolean flag (not in model)
2. `commission_rate` - Single rate column (model has 3 separate rate columns)

## Solution

Created migration `20260114_fix_hq_employee_columns.py` that:
- ✅ Adds missing `referral_code_generated_at` column
- ✅ Adds granular commission rate columns (mrr, setup, fintech)
- ✅ Renames `total_referrals` → `lifetime_referrals`
- ✅ Renames `total_commission_earned` → `lifetime_commission_earned`
- ✅ Migrates data from old columns to new columns
- ✅ Removes `is_affiliate` column
- ✅ Removes single `commission_rate` column

## How to Apply

### Option 1: Run the migration script
```bash
cd c:\Users\rcarb\Downloads\FOPS\fopsbackend
python scripts/run_hq_employee_migration.py
```

### Option 2: Manual alembic command
```bash
cd c:\Users\rcarb\Downloads\FOPS\fopsbackend
alembic upgrade 20260114_hq_employee_fix
```

### Option 3: Upgrade to head (applies all pending migrations)
```bash
cd c:\Users\rcarb\Downloads\FOPS\fopsbackend
alembic upgrade head
```

## Verification

After running the migration, verify the columns exist:
```sql
\d hq_employee
```

You should see:
- `referral_code_generated_at` (timestamp)
- `commission_rate_mrr` (numeric(5,4))
- `commission_rate_setup` (numeric(5,4))
- `commission_rate_fintech` (numeric(5,4))
- `lifetime_referrals` (integer)
- `lifetime_commission_earned` (numeric(12,2))

And these should be GONE:
- `total_referrals`
- `total_commission_earned`
- `is_affiliate`
- `commission_rate`

## Impact

After this migration:
- ✅ HQ login will work again
- ✅ Referral code generation will work
- ✅ Sales commission tracking will work properly
- ✅ My Earnings page will load correctly

## Files Changed

1. **Migration**: `alembic/versions/20260114_fix_hq_employee_columns.py` (NEW)
2. **Script**: `scripts/run_hq_employee_migration.py` (NEW)
3. **Model**: `app/models/hq_employee.py` (already correct)
4. **Service**: `app/services/hq.py` (already correct)
5. **Schemas**: `app/schemas/hq.py` (already correct)

## Timeline

- **2026-01-12**: Original Master Spec migration applied (incomplete)
- **2026-01-14**: Production error discovered - HQ login failing
- **2026-01-14**: Hotfix migration created and documented
