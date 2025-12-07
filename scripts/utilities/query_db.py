import psycopg

# Connect to database
conn_str = "postgresql://neondb_owner:npg_5uN2QZBeqpKo@ep-purple-moon-ahj5tx9w-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=prefer&connect_timeout=10"

with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:
        # Check for the user
        cur.execute("SELECT id, email, first_name, last_name, is_active, company_id FROM \"user\" WHERE email = %s", ('freightopsdispatch@gmail.com',))
        user = cur.fetchone()

        if user:
            print(f"User found:")
            print(f"  ID: {user[0]}")
            print(f"  Email: {user[1]}")
            print(f"  First Name: {user[2]}")
            print(f"  Last Name: {user[3]}")
            print(f"  Active: {user[4]}")
            print(f"  Company ID: {user[5]}")

            # Check company
            cur.execute('SELECT id, name, "dotNumber", "mcNumber", "isActive" FROM company WHERE id = %s', (user[5],))
            company = cur.fetchone()
            if company:
                print(f"\nCompany found:")
                print(f"  ID: {company[0]}")
                print(f"  Name: {company[1]}")
                print(f"  DOT Number: {company[2]}")
                print(f"  MC Number: {company[3]}")
                print(f"  Active: {company[4]}")
        else:
            print("User NOT found with email: freightopsdispatch@gmail.com")

            # Check if there's a similar email
            cur.execute("SELECT email FROM \"user\" WHERE email LIKE %s LIMIT 10", ('%freight%',))
            users = cur.fetchall()
            if users:
                print(f"\nFound {len(users)} users with 'freight' in email:")
                for u in users:
                    print(f"  - {u[0]}")
