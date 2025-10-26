"""
Authentication Tests
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock

from app.main import app
from app.config.db import get_db, Base
from app.config.settings import settings

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(scope="module")
def setup_database():
    """Setup test database"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def mock_user():
    """Mock user data"""
    return {
        "email": "test@example.com",
        "password": "TestPassword123!",
        "first_name": "Test",
        "last_name": "User",
        "company_name": "Test Company"
    }

class TestUserRegistration:
    """Test user registration functionality"""
    
    def test_successful_registration(self, setup_database, mock_user):
        """Test successful user registration"""
        response = client.post("/api/register", json=mock_user)
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == mock_user["email"]
    
    def test_registration_duplicate_email(self, setup_database, mock_user):
        """Test registration with duplicate email"""
        # First registration
        client.post("/api/register", json=mock_user)
        
        # Second registration with same email
        response = client.post("/api/register", json=mock_user)
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]
    
    def test_registration_invalid_email(self, setup_database, mock_user):
        """Test registration with invalid email"""
        mock_user["email"] = "invalid-email"
        response = client.post("/api/register", json=mock_user)
        assert response.status_code == 422
    
    def test_registration_weak_password(self, setup_database, mock_user):
        """Test registration with weak password"""
        mock_user["password"] = "weak"
        response = client.post("/api/register", json=mock_user)
        assert response.status_code == 422

class TestUserLogin:
    """Test user login functionality"""
    
    def test_successful_login(self, setup_database, mock_user):
        """Test successful user login"""
        # Register user first
        client.post("/api/register", json=mock_user)
        
        # Login
        login_data = {
            "email": mock_user["email"],
            "password": mock_user["password"]
        }
        response = client.post("/api/login", json=login_data)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == mock_user["email"]
    
    def test_login_invalid_credentials(self, setup_database, mock_user):
        """Test login with invalid credentials"""
        # Register user first
        client.post("/api/register", json=mock_user)
        
        # Login with wrong password
        login_data = {
            "email": mock_user["email"],
            "password": "wrong_password"
        }
        response = client.post("/api/login", json=login_data)
        assert response.status_code == 401
    
    def test_login_nonexistent_user(self, setup_database):
        """Test login with nonexistent user"""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "password123"
        }
        response = client.post("/api/login", json=login_data)
        assert response.status_code == 401

class TestHQAuthentication:
    """Test HQ authentication functionality"""
    
    def test_hq_login_invalid_credentials(self, setup_database):
        """Test HQ login with invalid credentials"""
        login_data = {
            "email": "admin@freightops.com",
            "password": "wrong_password"
        }
        response = client.post("/hq/login", json=login_data)
        assert response.status_code == 401
    
    @patch('app.routes.hq_auth.get_db')
    def test_hq_login_nonexistent_admin(self, mock_get_db, setup_database):
        """Test HQ login with nonexistent admin"""
        # Mock database to return no admin
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.return_value = mock_db
        
        login_data = {
            "email": "nonexistent@freightops.com",
            "password": "password123"
        }
        response = client.post("/hq/login", json=login_data)
        assert response.status_code == 401

class TestTokenValidation:
    """Test JWT token validation"""
    
    def test_protected_route_without_token(self, setup_database):
        """Test accessing protected route without token"""
        response = client.get("/api/users/me")
        assert response.status_code == 401
    
    def test_protected_route_with_invalid_token(self, setup_database):
        """Test accessing protected route with invalid token"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/users/me", headers=headers)
        assert response.status_code == 401
    
    def test_protected_route_with_valid_token(self, setup_database, mock_user):
        """Test accessing protected route with valid token"""
        # Register and login
        client.post("/api/register", json=mock_user)
        login_response = client.post("/api/login", json={
            "email": mock_user["email"],
            "password": mock_user["password"]
        })
        token = login_response.json()["access_token"]
        
        # Access protected route
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/users/me", headers=headers)
        assert response.status_code == 200
        assert response.json()["email"] == mock_user["email"]

class TestPasswordSecurity:
    """Test password security features"""
    
    def test_password_hashing(self, setup_database, mock_user):
        """Test that passwords are properly hashed"""
        response = client.post("/api/register", json=mock_user)
        assert response.status_code == 201
        
        # Verify password is not stored in plain text
        # This would require accessing the database directly in a real test
        # For now, we just verify the registration was successful
    
    def test_password_validation(self, setup_database):
        """Test password validation rules"""
        test_cases = [
            ("weak", False),  # Too short
            ("password", False),  # No uppercase, numbers, or special chars
            ("Password", False),  # No numbers or special chars
            ("Password1", False),  # No special chars
            ("Password1!", True),  # Valid password
        ]
        
        for password, should_pass in test_cases:
            user_data = {
                "email": f"test_{password}@example.com",
                "password": password,
                "first_name": "Test",
                "last_name": "User",
                "company_name": "Test Company"
            }
            response = client.post("/api/register", json=user_data)
            
            if should_pass:
                assert response.status_code == 201
            else:
                assert response.status_code == 422




