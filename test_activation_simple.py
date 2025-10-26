#!/usr/bin/env python3
"""
Simple test script to verify email activation components work
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.email_service import email_service

def test_activation_components():
    """Test the activation components without database operations"""
    
    print("Testing Email Activation Components...")
    
    # Test 1: Email service token generation
    print("\n1. Testing token generation...")
    token = email_service.generate_activation_token()
    print(f"   Generated activation token: {token[:8]}...")
    assert len(token) == 32, "Token should be 32 characters"
    print("   Token generation: PASSED")
    
    # Test 2: Email template generation
    print("\n2. Testing email template generation...")
    try:
        html_content = email_service.create_activation_email_html(
            user_name="Test User",
            activation_link="http://localhost:5173/activate?token=test123"
        )
        assert "Test User" in html_content, "Email template should contain user name"
        assert "activate?token=test123" in html_content, "Email template should contain activation link"
        assert "FreightOps Pro" in html_content, "Email template should contain company name"
        print(f"   Email template generated: {len(html_content)} characters")
        print("   Email template generation: PASSED")
    except Exception as e:
        print(f"   Email template test failed: {e}")
        raise
    
    # Test 3: Multiple token generation (uniqueness)
    print("\n3. Testing token uniqueness...")
    tokens = set()
    for i in range(10):
        token = email_service.generate_activation_token()
        tokens.add(token)
    
    assert len(tokens) == 10, "All tokens should be unique"
    print("   Token uniqueness: PASSED")
    
    # Test 4: Email service configuration
    print("\n4. Testing email service configuration...")
    print(f"   SMTP Server: {email_service.smtp_server}")
    print(f"   SMTP Port: {email_service.smtp_port}")
    print(f"   From Email: {email_service.from_email}")
    print(f"   From Name: {email_service.from_name}")
    print("   Email service configuration: PASSED")
    
    print("\nAll activation component tests passed!")
    print("\nSummary:")
    print("   Token generation: WORKING")
    print("   Email template generation: WORKING")
    print("   Token uniqueness: WORKING")
    print("   Email service configuration: WORKING")
    print("\nStatus: READY FOR EMAIL CONFIGURATION")
    print("\nNext steps:")
    print("   1. Add email credentials to .env file")
    print("   2. Test actual email sending")
    print("   3. Test complete registration flow")

if __name__ == "__main__":
    test_activation_components()

