import psycopg

# Connect to database
conn_str = "postgresql://neondb_owner:npg_5uN2QZBeqpKo@ep-purple-moon-ahj5tx9w-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=prefer&connect_timeout=10"

with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:
        # List all users
        cur.execute('SELECT id, email, first_name, last_name, is_active, company_id, created_at FROM "user" ORDER BY created_at DESC')
        users = cur.fetchall()

        print(f"Total users in database: {len(users)}\n")

        if users:
            print("All users:")
            for user in users:
                print(f"\n  Email: {user[1]}")
                print(f"    ID: {user[0]}")
                print(f"    Name: {user[2]} {user[3]}")
                print(f"    Active: {user[4]}")
                print(f"    Company ID: {user[5]}")
                print(f"    Created: {user[6]}")

                # Get company details
                cur.execute('SELECT name, "dotNumber", "mcNumber" FROM company WHERE id = %s', (user[5],))
                company = cur.fetchone()
                if company:
                    print(f"    Company: {company[0]} (DOT: {company[1]}, MC: {company[2]})")
        else:
            print("No users found in database!")

        # Check if table exists and has correct structure
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'user'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        print(f"\n\nUser table structure ({len(columns)} columns):")
        for col in columns:
            print(f"  - {col[0]}: {col[1]}")
