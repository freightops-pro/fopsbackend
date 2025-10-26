#!/usr/bin/env python3
"""
Test main app import and OCR router registration
"""

import os
import sys
import traceback
from pathlib import Path

def test_main_import():
    """Test main app import and check OCR router registration"""
    
    # Set up environment
    os.environ['GEMINI_API_KEY'] = 'AIzaSyBJeSsvOc1UcI0UF78Qfm6bMTuI0UNc1eE'
    
    try:
        print("Testing main app import...")
        print("=" * 50)
        
        # Import main app
        from app.main import app
        
        print("OK Main app imported successfully")
        print(f"Total routes: {len(app.routes)}")
        
        # Check for OCR routes
        ocr_routes = [route for route in app.routes if hasattr(route, 'path') and 'ocr' in route.path]
        print(f"OCR routes: {len(ocr_routes)}")
        
        if len(ocr_routes) > 0:
            print("OK OCR routes found:")
            for route in ocr_routes:
                print(f"  {route.path} - {route.methods}")
        else:
            print("ERROR No OCR routes found")
            
        # Check all routes with 'api' prefix
        api_routes = [route for route in app.routes if hasattr(route, 'path') and route.path.startswith('/api')]
        print(f"\nAPI routes: {len(api_routes)}")
        
        # Show first 10 API routes
        print("First 10 API routes:")
        for i, route in enumerate(api_routes[:10]):
            print(f"  {route.path} - {route.methods}")
        
        return len(ocr_routes) > 0
        
    except Exception as e:
        print(f"ERROR Error importing main app: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_main_import()
    
    if success:
        print("\nSUCCESS Main app import test passed - OCR routes are registered")
    else:
        print("\nERROR Main app import test failed - OCR routes are not registered")

