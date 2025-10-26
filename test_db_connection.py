"""
Test script to verify database connection and user authentication
"""
import os
from sqlalchemy import create_engine, text
from passlib.context import CryptContext

# Database setup
DATABASE_URL = "postgresql://neondb_owner:npg_JVQsDGh9lM6S@ep-quiet-moon-adsx2dey-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
engine = create_engine(DATABASE_URL)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def test_connection():
    """Test database connection"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test")).fetchone()
            print(f"Database connection successful: {result.test}")
            return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False

def test_user_query():
    """Test user query"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT id, email, first_name, last_name FROM users WHERE email = :email"),
                {"email": "test@example.com"}
            ).fetchone()
            
            if result:
                print(f"User found: {result.email} - {result.first_name} {result.last_name}")
                return True
            else:
                print("User not found")
                return False
    except Exception as e:
        print(f"User query failed: {e}")
        return False

def test_password_verification():
    """Test password verification"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT password FROM users WHERE email = :email"),
                {"email": "test@example.com"}
            ).fetchone()
            
            if result:
                # Test with wrong password
                wrong_password = "wrongpassword"
                is_valid = pwd_context.verify(wrong_password, result.password)
                print(f"Wrong password test: {is_valid} (should be False)")
                
                # Test with correct password
                correct_password = "password123"
                is_valid = pwd_context.verify(correct_password, result.password)
                print(f"Correct password test: {is_valid} (should be True)")
                
                return True
            else:
                print("User not found for password test")
                return False
    except Exception as e:
        print(f"Password verification test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing database connection and authentication...")
    
    if test_connection():
        if test_user_query():
            test_password_verification()
    
    print("Test completed!")

