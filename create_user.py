import uuid
import psycopg
from passlib.context import CryptContext

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# Connect to database
conn_str = "postgresql://neondb_owner:npg_5uN2QZBeqpKo@ep-purple-moon-ahj5tx9w-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=prefer&connect_timeout=10"

with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:
        # Check if user already exists
        cur.execute('SELECT id FROM "user" WHERE email = %s', ('freightopsdispatch@gmail.com',))
        existing = cur.fetchone()

        if existing:
            print("User already exists!")
        else:
            # Create company first
            company_id = str(uuid.uuid4())
            cur.execute('''
                INSERT INTO company (
                    id, name, email, phone, subscription_plan, business_type,
                    dot_number, mc_number, primary_contact_name, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                company_id,
                'FreightOps Dispatch',
                'freightopsdispatch@gmail.com',
                '555-1234',
                'pro',
                'carrier',
                '3988790',
                None,
                'Freight Ops',
                True
            ))
            print(f"Created company: {company_id}")

            # Create user
            user_id = str(uuid.uuid4())
            hashed_password = hash_password('zkorpio18!')

            cur.execute('''
                INSERT INTO "user" (
                    id, email, hashed_password, first_name, last_name,
                    company_id, role, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                user_id,
                'freightopsdispatch@gmail.com',
                hashed_password,
                'Freight',
                'Ops',
                company_id,
                'TENANT_ADMIN',
                True
            ))

            conn.commit()
            print(f"Created user: {user_id}")
            print(f"Email: freightopsdispatch@gmail.com")
            print(f"Password: zkorpio18!")
            print(f"DOT Number: 3988790")
            print("\nUser created successfully!")
