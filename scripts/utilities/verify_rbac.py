import psycopg

conn_str = "postgresql://neondb_owner:npg_5uN2QZBeqpKo@ep-purple-moon-ahj5tx9w-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=prefer&connect_timeout=10"

with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:
        # Count records in RBAC tables
        cur.execute('SELECT COUNT(*) FROM role')
        roles = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM permission')
        perms = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM user_role')
        user_roles = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM role_permission')
        role_perms = cur.fetchone()[0]

        print("RBAC Tables Summary:")
        print("-" * 40)
        print(f"Roles:                  {roles}")
        print(f"Permissions:            {perms}")
        print(f"User-Role assignments:  {user_roles}")
        print(f"Role-Permission maps:   {role_perms}")

        # Show roles
        print("\nSystem Roles:")
        cur.execute('SELECT name, display_name FROM role WHERE is_system_role = true ORDER BY name')
        for row in cur.fetchall():
            print(f"  - {row[0]}: {row[1]}")

        # Show user-role assignments
        print("\nUser Role Assignments (from user_role table):")
        cur.execute('''
            SELECT u.email, r.name
            FROM user_role ur
            JOIN "user" u ON u.id = ur.user_id
            JOIN role r ON r.id = ur.role_id
            ORDER BY u.email
        ''')
        for row in cur.fetchall():
            print(f"  - {row[0]}: {row[1]}")
