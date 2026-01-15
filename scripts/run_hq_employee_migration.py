#!/usr/bin/env python3
"""
Run the HQ Employee hotfix migration to add missing columns.

This script applies the migration that fixes the mismatch between
the HQEmployee model and the database schema.
"""
import subprocess
import sys
from pathlib import Path

def run_migration():
    """Run the alembic migration."""
    backend_dir = Path(__file__).parent.parent

    print("=" * 80)
    print("Running HQ Employee Hotfix Migration")
    print("=" * 80)
    print("\nThis will:")
    print("  - Add referral_code_generated_at column")
    print("  - Add commission_rate_mrr, commission_rate_setup, commission_rate_fintech columns")
    print("  - Rename total_referrals to lifetime_referrals")
    print("  - Rename total_commission_earned to lifetime_commission_earned")
    print("  - Remove is_affiliate column")
    print("  - Remove single commission_rate column")
    print("\n" + "=" * 80)

    # Show current alembic head
    print("\n[-] Current migration status:")
    result = subprocess.run(
        ["alembic", "current"],
        cwd=backend_dir,
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"[ERROR] Error checking current migration: {result.stderr}")
        return False

    # Run the upgrade
    print("\n[*] Applying migration 20260114_hq_employee_fix...")
    result = subprocess.run(
        ["alembic", "upgrade", "20260114_hq_employee_fix"],
        cwd=backend_dir,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("[OK] Migration completed successfully!")
        print(result.stdout)

        # Show new status
        print("\n[-] New migration status:")
        result = subprocess.run(
            ["alembic", "current"],
            cwd=backend_dir,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        return True
    else:
        print(f"[ERROR] Migration failed: {result.stderr}")
        print(result.stdout)
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
