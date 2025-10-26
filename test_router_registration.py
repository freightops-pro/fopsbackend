#!/usr/bin/env python3
"""
Test OCR router registration
"""

import os
import sys
from pathlib import Path

def test_router_registration():
    """Test if OCR router can be registered properly"""
    
    # Set up environment
    os.environ['GEMINI_API_KEY'] = 'AIzaSyBJeSsvOc1UcI0UF78Qfm6bMTuI0UNc1eE'
    
    try:
        # Import FastAPI and create a test app
        from fastapi import FastAPI
        from app.routes.ocr import router as ocr_router
        
        print("Testing OCR router registration...")
        print("=" * 50)
        
        # Create a test FastAPI app
        app = FastAPI()
        
        # Try to register the OCR router
        print("Registering OCR router...")
        app.include_router(ocr_router)
        
        print("OK OCR router registered successfully")
        
        # Check if routes are registered
        print("\nRegistered routes:")
        for route in app.routes:
            if hasattr(route, 'path') and 'ocr' in route.path:
                print(f"  {route.path} - {route.methods}")
        
        # Test if the routes are accessible
        print(f"\nTotal routes in app: {len(app.routes)}")
        ocr_routes = [route for route in app.routes if hasattr(route, 'path') and 'ocr' in route.path]
        print(f"OCR routes: {len(ocr_routes)}")
        
        if len(ocr_routes) > 0:
            print("OK OCR routes are properly registered")
            return True
        else:
            print("ERROR OCR routes are not registered")
            return False
            
    except Exception as e:
        print(f"ERROR Error during router registration: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_router_registration()
    
    if success:
        print("\nSUCCESS OCR router registration test passed")
    else:
        print("\nERROR OCR router registration test failed")
