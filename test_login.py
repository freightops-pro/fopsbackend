#!/usr/bin/env python3
"""
Simple test script to verify the login route works correctly.
Run this after starting the FastAPI server.
"""

import requests
import json

# Test configuration
BASE_URL = "http://localhost:8000"
LOGIN_URL = f"{BASE_URL}/api/v1/users/api/login"

def test_login():
    """Test the login endpoint"""
    
    # Test data
    test_payload = {
        "email": "test@example.com",
        "password": "testpassword123",
        "customerId": "test-customer-123"
    }
    
    print("🧪 Testing login endpoint...")
    print(f"URL: {LOGIN_URL}")
    print(f"Payload: {json.dumps(test_payload, indent=2)}")
    
    try:
        # Make the request
        response = requests.post(
            LOGIN_URL,
            json=test_payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"\n📊 Response Status: {response.status_code}")
        print(f"📊 Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("✅ Login endpoint is working!")
            response_data = response.json()
            print(f"📄 Response Data: {json.dumps(response_data, indent=2)}")
        else:
            print(f"❌ Login failed with status {response.status_code}")
            print(f"📄 Error Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the FastAPI server is running on http://localhost:8000")
    except Exception as e:
        print(f"❌ Error occurred: {str(e)}")

def test_server_health():
    """Test if the server is running"""
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print("✅ Server is running!")
            return True
        else:
            print(f"❌ Server responded with status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running. Start it with: uvicorn app.main:app --reload")
        return False

if __name__ == "__main__":
    print("🚀 FreightOps Login Route Test")
    print("=" * 50)
    
    # First check if server is running
    if test_server_health():
        test_login()
    else:
        print("\n💡 To start the server:")
        print("1. cd backend")
        print("2. pip install -r requirements.txt")
        print("3. uvicorn app.main:app --reload")
        print("4. Then run this test script again")
