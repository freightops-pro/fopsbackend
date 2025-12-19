import psycopg

conn_str = "postgresql://neondb_owner:npg_5uN2QZBeqpKo@ep-purple-moon-ahj5tx9w-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=prefer&connect_timeout=10"

with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:
        # Update all demofreight.com users to TENANT_ADMIN
        cur.execute('''
            UPDATE "user"
            SET role = 'TENANT_ADMIN'
            WHERE email LIKE '%@demofreight.com'
            RETURNING email, role
        ''')
        updated = cur.fetchall()
        conn.commit()

        print(f"Updated {len(updated)} users to TENANT_ADMIN:")
        for user in updated:
            print(f"  - {user[0]}")

        print()
        print("Verifying all users:")
        cur.execute('SELECT email, role FROM "user" ORDER BY created_at DESC')
        for user in cur.fetchall():
            print(f"  {user[0]:<35} | {user[1]}")
