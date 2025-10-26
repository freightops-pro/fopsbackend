#!/usr/bin/env python3
"""
Test script to verify email activation flow without sending actual emails
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.config.db import SessionLocal
from app.models.userModels import Users, Companies
from app.services.email_service import email_service
from datetime import datetime, timedelta
import uuid

def test_activation_flow():
    """Test the complete activation flow without sending emails"""
    
    print("Testing Email Activation Flow...")
    
    # Test 1: Email service token generation
    print("\n1. Testing token generation...")
    token = email_service.generate_activation_token()
    print(f"   Generated activation token: {token[:8]}...")
    assert len(token) == 32, "Token should be 32 characters"
    
    # Test 2: Database operations
    print("\n2. Testing database operations...")
    db = SessionLocal()
    try:
        # Create test user data
        test_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
        test_user = Users(
            id=str(uuid.uuid4()),
            email=test_email,
            firstname="Test",
            lastname="User",
            password="hashed_password",
            phone="555-0123",
            role="user",
            companyid=str(uuid.uuid4()),
            isactive=False,
            emailverified=False,
            activationtoken=token,
            activationtokenexpiry=datetime.utcnow() + timedelta(hours=24)
        )
        
        # Test creating user with activation fields
        db.add(test_user)
        db.flush()
        print(f"   Created test user: {test_email}")
        
        # Test finding user by activation token
        found_user = db.query(Users).filter(
            Users.activationtoken == token,
            Users.activationtokenexpiry > datetime.utcnow()
        ).first()
        
        assert found_user is not None, "Should find user by activation token"
        print(f"   Found user by activation token: {found_user.email}")
        
        # Test activation
        found_user.emailverified = True
        found_user.isactive = True
        found_user.activationtoken = None
        found_user.activationtokenexpiry = None
        db.commit()
        
        # Verify activation
        activated_user = db.query(Users).filter(Users.email == test_email).first()
        assert activated_user.emailverified == True, "User should be email verified"
        assert activated_user.isactive == True, "User should be active"
        assert activated_user.activationtoken is None, "Activation token should be cleared"
        print(f"   User activated successfully")
        
        # Clean up test data
        db.delete(activated_user)
        db.commit()
        print(f"   Test data cleaned up")
        
    except Exception as e:
        db.rollback()
        print(f"   Database test failed: {e}")
        raise
    finally:
        db.close()
    
    # Test 3: Email template generation (without sending)
    print("\n3. Testing email template generation...")
    try:
        html_content = email_service.create_activation_email_html(
            user_name="Test User",
            activation_link="http://localhost:5173/activate?token=test123"
        )
        assert "Test User" in html_content, "Email template should contain user name"
        assert "activate?token=test123" in html_content, "Email template should contain activation link"
        print(f"   Email template generated successfully ({len(html_content)} characters)")
    except Exception as e:
        print(f"   Email template test failed: {e}")
        raise
    
    # Test 4: Token expiry logic
    print("\n4. Testing token expiry logic...")
    try:
        # Test expired token
        expired_token = email_service.generate_activation_token()
        db = SessionLocal()
        
        expired_user = Users(
            id=str(uuid.uuid4()),
            email=f"expired-{uuid.uuid4().hex[:8]}@example.com",
            firstname="Expired",
            lastname="User",
            password="hashed_password",
            phone="555-0123",
            role="user",
            companyid=str(uuid.uuid4()),
            isactive=False,
            emailverified=False,
            activationtoken=expired_token,
            activationtokenexpiry=datetime.utcnow() - timedelta(hours=1)  # Expired 1 hour ago
        )
        
        db.add(expired_user)
        db.flush()
        
        # Try to find expired token
        found_expired = db.query(Users).filter(
            Users.activationtoken == expired_token,
            Users.activationtokenexpiry > datetime.utcnow()  # This should fail
        ).first()
        
        assert found_expired is None, "Should not find expired token"
        print(f"   Expired token correctly rejected")
        
        # Clean up
        db.delete(expired_user)
        db.commit()
        db.close()
        
    except Exception as e:
        print(f"   Token expiry test failed: {e}")
        raise
    
    print("\nAll activation flow tests passed!")
    print("\nSummary:")
    print("   Token generation working")
    print("   Database operations working")
    print("   Email template generation working")
    print("   Token expiry logic working")
    print("\nNext steps:")
    print("   1. Configure email credentials in .env file")
    print("   2. Test actual email sending")
    print("   3. Test complete registration flow")

if __name__ == "__main__":
    test_activation_flow()
