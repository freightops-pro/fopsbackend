#!/usr/bin/env python3
"""
Simple test script to verify backend setup
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test if all modules can be imported successfully"""
    try:
        from app.config.settings import settings
        print("✓ Settings imported successfully")
        
        from app.config.db import get_db, create_tables
        print("✓ Database configuration imported successfully")
        
        from app.models.userModels import Users, Companies, UserCreate, CompanyCreate
        print("✓ Models imported successfully")
        
        from app.controllers.userControllers import UserController, CompanyController
        print("✓ Controllers imported successfully")
        
        from app.routes.user import router
        print("✓ Routes imported successfully")
        
        from app.main import app
        print("✓ FastAPI app imported successfully")
        
        print("\n🎉 All imports successful! Backend is properly configured.")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_settings():
    """Test if settings are properly configured"""
    try:
        from app.config.settings import settings
        
        print(f"\n📋 Current Settings:")
        print(f"  Environment: {settings.ENVIRONMENT}")
        print(f"  Debug: {settings.DEBUG}")
        print(f"  Database URL: {settings.DATABASE_URL}")
        print(f"  API Version: {settings.API_V1_STR}")
        print(f"  Project Name: {settings.PROJECT_NAME}")
        
        return True
        
    except Exception as e:
        print(f"❌ Settings test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing FreightOps Backend Configuration...\n")
    
    import_success = test_imports()
    settings_success = test_settings()
    
    if import_success and settings_success:
        print("\n✅ Backend configuration is ready!")
        print("\nTo start the server, run:")
        print("  python run.py")
        print("  or")
        print("  python -m uvicorn app.main:app --reload")
    else:
        print("\n❌ Backend configuration has issues. Please check the errors above.")
        sys.exit(1)
