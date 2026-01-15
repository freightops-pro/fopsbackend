#!/usr/bin/env python3
"""Verify HQ Employee columns exist in database."""
from app.db import SessionLocal
from sqlalchemy import text

db = SessionLocal()

print("\n" + "=" * 80)
print("Verifying HQ Employee Columns")
print("=" * 80)

# Check for new columns
new_columns = [
    'referral_code_generated_at',
    'commission_rate_mrr',
    'commission_rate_setup',
    'commission_rate_fintech',
    'lifetime_referrals',
    'lifetime_commission_earned'
]

query = text("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'hq_employee'
    AND column_name IN :columns
    ORDER BY column_name
""")

result = db.execute(query, {"columns": tuple(new_columns)})

print("\n[OK] New columns in hq_employee table:")
print("-" * 80)
print(f"{'Column Name':<40} {'Data Type':<20} {'Nullable'}")
print("-" * 80)

found_columns = []
for row in result:
    found_columns.append(row[0])
    print(f"{row[0]:<40} {row[1]:<20} {row[2]}")

# Check for old columns that should be removed
old_columns = [
    'total_referrals',
    'total_commission_earned',
    'is_affiliate',
    'commission_rate'
]

query_old = text("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'hq_employee'
    AND column_name IN :columns
""")

result_old = db.execute(query_old, {"columns": tuple(old_columns)})
old_found = [row[0] for row in result_old]

if old_found:
    print("\n[ERROR] Old columns still exist (should be removed):")
    for col in old_found:
        print(f"  - {col}")
else:
    print("\n[OK] Old columns successfully removed")

# Summary
print("\n" + "=" * 80)
print("Summary:")
print(f"  Expected new columns: {len(new_columns)}")
print(f"  Found new columns: {len(found_columns)}")
print(f"  Old columns remaining: {len(old_found)}")

if len(found_columns) == len(new_columns) and len(old_found) == 0:
    print("\n[OK] Migration successful! All columns are correct.")
else:
    print("\n[ERROR] Migration incomplete!")
    if len(found_columns) < len(new_columns):
        missing = set(new_columns) - set(found_columns)
        print(f"  Missing columns: {missing}")

print("=" * 80 + "\n")

db.close()
