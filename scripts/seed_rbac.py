"""
Seed RBAC tables with default roles and permissions.

This script should be run after the RBAC migration to populate:
1. System roles (available to all tenants)
2. Permissions (granular access controls)
3. Role-permission mappings

Usage:
    poetry run python scripts/seed_rbac.py
"""

import uuid
import psycopg
from datetime import datetime

# Import RBAC definitions
import sys
sys.path.insert(0, ".")
from app.core.rbac import (
    SystemRole,
    ROLE_METADATA,
    PERMISSIONS,
    ROLE_PERMISSIONS,
    get_permission_key,
)

# Database connection
CONN_STR = "postgresql://neondb_owner:npg_5uN2QZBeqpKo@ep-purple-moon-ahj5tx9w-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=prefer&connect_timeout=10"


def seed_permissions(cur) -> dict:
    """Create all permissions and return a mapping of key -> id."""
    print("\n[PERMISSIONS] Seeding permissions...")
    permission_map = {}

    for resource, action, description, category in PERMISSIONS:
        perm_id = str(uuid.uuid4())
        perm_key = get_permission_key(resource, action)

        # Check if permission already exists
        cur.execute(
            'SELECT id FROM permission WHERE resource = %s AND action = %s',
            (resource.value, action.value)
        )
        existing = cur.fetchone()

        if existing:
            permission_map[perm_key] = existing[0]
            print(f"  [=] Permission exists: {perm_key}")
        else:
            cur.execute(
                '''INSERT INTO permission (id, resource, action, description, category, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s)''',
                (perm_id, resource.value, action.value, description, category, datetime.utcnow())
            )
            permission_map[perm_key] = perm_id
            print(f"  [+] Created permission: {perm_key}")

    return permission_map


def seed_roles(cur) -> dict:
    """Create all system roles and return a mapping of name -> id."""
    print("\n[ROLES] Seeding system roles...")
    role_map = {}

    for role in SystemRole:
        role_id = str(uuid.uuid4())
        metadata = ROLE_METADATA.get(role, {})
        display_name = metadata.get("display_name", role.value)
        description = metadata.get("description", "")

        # Check if role already exists
        cur.execute(
            'SELECT id FROM role WHERE name = %s AND company_id IS NULL',
            (role.value,)
        )
        existing = cur.fetchone()

        if existing:
            role_map[role.value] = existing[0]
            print(f"  [=] Role exists: {role.value}")
        else:
            cur.execute(
                '''INSERT INTO role (id, name, display_name, description, company_id, is_system_role, is_active, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, NULL, true, true, %s, %s)''',
                (role_id, role.value, display_name, description, datetime.utcnow(), datetime.utcnow())
            )
            role_map[role.value] = role_id
            print(f"  [+] Created role: {role.value} ({display_name})")

    return role_map


def seed_role_permissions(cur, role_map: dict, permission_map: dict):
    """Create role-permission mappings."""
    print("\n[MAPPING] Seeding role-permission mappings...")

    for role, permissions in ROLE_PERMISSIONS.items():
        role_id = role_map.get(role.value)
        if not role_id:
            print(f"  [!] Role not found: {role.value}")
            continue

        for perm_key in permissions:
            perm_id = permission_map.get(perm_key)
            if not perm_id:
                print(f"  [!] Permission not found: {perm_key}")
                continue

            # Check if mapping already exists
            cur.execute(
                'SELECT 1 FROM role_permission WHERE role_id = %s AND permission_id = %s',
                (role_id, perm_id)
            )
            if cur.fetchone():
                continue  # Skip if exists

            cur.execute(
                '''INSERT INTO role_permission (role_id, permission_id, created_at)
                   VALUES (%s, %s, %s)''',
                (role_id, perm_id, datetime.utcnow())
            )

        print(f"  [+] Mapped {len(permissions)} permissions to {role.value}")


def migrate_existing_users(cur, role_map: dict):
    """Migrate existing users from legacy role column to user_role table."""
    print("\n[USERS] Migrating existing users to new role system...")

    # Get all users with a legacy role
    cur.execute('SELECT id, email, role FROM "user" WHERE role IS NOT NULL')
    users = cur.fetchall()

    migrated = 0
    for user_id, email, legacy_role in users:
        # Normalize legacy role to uppercase
        normalized_role = legacy_role.upper() if legacy_role else None

        # Map legacy roles to system roles
        role_mapping = {
            "TENANT_ADMIN": "TENANT_ADMIN",
            "ADMIN": "TENANT_ADMIN",
            "OWNER": "TENANT_ADMIN",
            "DISPATCHER": "DISPATCHER",
            "DRIVER": "DRIVER",
            "ACCOUNTANT": "ACCOUNTANT",
            "PAYROLL": "ACCOUNTANT",
            "HR_SPECIALIST": "HR_SPECIALIST",
            "HR": "HR_SPECIALIST",
            "SAFETY": "OPERATIONS_MANAGER",
            "FLEET_MANAGER": "OPERATIONS_MANAGER",
            "SALES_AGENT": "SALES_AGENT",
            "SALES_MANAGER": "SALES_MANAGER",
            "OPERATIONS_MANAGER": "OPERATIONS_MANAGER",
            "HQ_ADMIN": "HQ_ADMIN",
        }

        mapped_role = role_mapping.get(normalized_role, "DISPATCHER")  # Default to DISPATCHER
        role_id = role_map.get(mapped_role)

        if not role_id:
            print(f"  [!] No role found for {email} (legacy: {legacy_role})")
            continue

        # Check if user already has this role
        cur.execute(
            'SELECT 1 FROM user_role WHERE user_id = %s AND role_id = %s',
            (user_id, role_id)
        )
        if cur.fetchone():
            print(f"  [=] {email} already has role {mapped_role}")
            continue

        # Assign role
        cur.execute(
            '''INSERT INTO user_role (user_id, role_id, assigned_at)
               VALUES (%s, %s, %s)''',
            (user_id, role_id, datetime.utcnow())
        )
        print(f"  [+] {email}: {legacy_role} -> {mapped_role}")
        migrated += 1

    print(f"\n  Migrated {migrated} users")


def main():
    print("Starting RBAC seed...")
    print("=" * 60)

    with psycopg.connect(CONN_STR) as conn:
        with conn.cursor() as cur:
            # Check if RBAC tables exist
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'role'
                )
            """)
            if not cur.fetchone()[0]:
                print("[ERROR] RBAC tables not found. Run the migration first:")
                print("   poetry run alembic upgrade head")
                return

            # Seed data
            permission_map = seed_permissions(cur)
            role_map = seed_roles(cur)
            seed_role_permissions(cur, role_map, permission_map)
            migrate_existing_users(cur, role_map)

            conn.commit()

    print("\n" + "=" * 60)
    print("[DONE] RBAC seeding complete!")
    print("\nSummary:")
    print(f"  - {len(PERMISSIONS)} permissions")
    print(f"  - {len(SystemRole)} system roles")
    print("\nNext steps:")
    print("  1. Restart the backend server")
    print("  2. Log out and log back in to get new session with roles")


if __name__ == "__main__":
    main()
