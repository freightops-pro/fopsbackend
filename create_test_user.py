"""
Script to create a test user with proper password hashing
"""
from sqlalchemy import create_engine, text
from passlib.context import CryptContext

# Database setup
DATABASE_URL = "postgresql://neondb_owner:npg_JVQsDGh9lM6S@ep-quiet-moon-adsx2dey-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
engine = create_engine(DATABASE_URL)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_test_user():
    """Create a test user with proper password hashing"""
    try:
        # Hash the password
        password = "password123"
        hashed_password = pwd_context.hash(password)
        
        with engine.connect() as conn:
            # Delete existing test user
            conn.execute(
                text("DELETE FROM users WHERE email = :email"),
                {"email": "test@example.com"}
            )
            
            # Insert new test user
            conn.execute(
                text("""
                    INSERT INTO users (email, password, first_name, last_name, role, company_id) 
                    VALUES (:email, :password, :first_name, :last_name, :role, :company_id)
                """),
                {
                    "email": "test@example.com",
                    "password": hashed_password,
                    "first_name": "Test",
                    "last_name": "User",
                    "role": "admin",
                    "company_id": 1
                }
            )
            conn.commit()
            
        print("Test user created successfully!")
        print(f"Email: test@example.com")
        print(f"Password: password123")
        print(f"Hashed password: {hashed_password}")
        return True
        
    except Exception as e:
        print(f"Error creating test user: {e}")
        return False

if __name__ == "__main__":
    create_test_user()

