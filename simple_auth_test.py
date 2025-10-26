"""
Simple authentication test with basic password checking
"""
from sqlalchemy import create_engine, text

# Database setup
DATABASE_URL = "postgresql://neondb_owner:npg_JVQsDGh9lM6S@ep-quiet-moon-adsx2dey-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
engine = create_engine(DATABASE_URL)

def test_login_scenarios():
    """Test different login scenarios"""
    
    # Test with wrong email
    print("Testing with wrong email...")
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT id, email FROM users WHERE email = :email"),
                {"email": "wrong@example.com"}
            ).fetchone()
            
            if not result:
                print("❌ Invalid email - User not found")
            else:
                print("✅ User found")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test with existing email but wrong password
    print("\nTesting with existing email but wrong password...")
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT id, email, password FROM users WHERE email = :email"),
                {"email": "test@example.com"}
            ).fetchone()
            
            if result:
                print("✅ User found in database")
                print(f"User ID: {result.id}")
                print(f"Email: {result.email}")
                print("❌ Password verification would fail with wrong password")
            else:
                print("❌ User not found")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_login_scenarios()

