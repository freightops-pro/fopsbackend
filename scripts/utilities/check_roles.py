import psycopg

conn_str = "postgresql://neondb_owner:npg_5uN2QZBeqpKo@ep-purple-moon-ahj5tx9w-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=prefer&connect_timeout=10"

with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:
        cur.execute('SELECT email, role, is_active FROM "user" ORDER BY created_at DESC')
        users = cur.fetchall()
        print("Users and their roles:")
        print("-" * 60)
        for user in users:
            print(f"{user[0]:<35} | Role: {user[1]:<15} | Active: {user[2]}")
