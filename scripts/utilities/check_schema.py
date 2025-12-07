import psycopg

conn_str = "postgresql://neondb_owner:npg_5uN2QZBeqpKo@ep-purple-moon-ahj5tx9w-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=prefer&connect_timeout=10"

with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:
        # Check company table structure
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'company'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        print(f"Company table structure ({len(columns)} columns):")
        for col in columns:
            print(f"  - {col[0]}: {col[1]}")

        print("\n" + "="*50 + "\n")

        # Check user table structure
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'user'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        print(f"User table structure ({len(columns)} columns):")
        for col in columns:
            print(f"  - {col[0]}: {col[1]}")
