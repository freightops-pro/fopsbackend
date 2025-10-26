#!/usr/bin/env python3
"""
Test script for Gemini API OCR functionality
"""

import os
import sys
import base64
import httpx
from pathlib import Path

def test_gemini_api():
    """Test Gemini API with a simple request"""
    gemini_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    
    if not gemini_key:
        print("ERROR: No Gemini API key found!")
        print("Set GEMINI_API_KEY environment variable with your API key")
        print("Get one at: https://makersuite.google.com/app/apikey")
        return False
    
        print(f"OK Gemini API key found: {gemini_key[:10]}...")
    
    # Test with a simple text request first
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={gemini_key}"
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": "Hello, can you respond with 'OCR test successful'?"
                        }
                    ]
                }
            ]
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        print("Testing Gemini API connection...")
        response = httpx.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                response_text = result['candidates'][0]['content']['parts'][0]['text']
                print(f"OK Gemini API working! Response: {response_text}")
                return True
            else:
                print("ERROR: Unexpected response format")
                return False
        else:
            print(f"ERROR: API error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"ERROR: Error testing Gemini API: {e}")
        return False

def test_ocr_service():
    """Test the OCR service with Gemini API"""
    try:
        # Import the OCR service
        sys.path.append(str(Path(__file__).parent))
        import os
        from app.services.ocr_service import OCRService
        
        print("\nTesting OCR Service with Gemini API...")
        ocr_service = OCRService()
        
        if ocr_service.use_gemini:
            print("OK OCR Service configured to use Gemini API")
            
            # Create a simple test image (1x1 pixel PNG)
            import io
            from PIL import Image
            
            img = Image.new('RGB', (100, 100), color='white')
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes = img_bytes.getvalue()
            
            # Test OCR extraction
            result = ocr_service.extract_load_data(img_bytes, "test-image.png")
            
            print(f"OK OCR test completed!")
            print(f"  Confidence Score: {result.get('confidence_score', 0)}")
            print(f"  Extracted Fields: {len([k for k, v in result.items() if v and k != 'confidence_score'])}")
            
            return True
        else:
            print("ERROR: OCR Service not configured for Gemini API")
            return False
            
    except Exception as e:
        print(f"ERROR: Error testing OCR service: {e}")
        return False

if __name__ == "__main__":
    print("Gemini API OCR Test")
    print("=" * 30)
    
    # Test Gemini API connection
    api_working = test_gemini_api()
    
    if api_working:
        # Test OCR service
        ocr_working = test_ocr_service()
        
        if ocr_working:
            print("\nSUCCESS: Gemini API OCR is working!")
            print("You can now upload rate confirmations and BOLs for OCR processing.")
        else:
            print("\nERROR: OCR service test failed")
    else:
        print("\nERROR: Gemini API test failed")
        print("\nTo fix this:")
        print("1. Go to: https://makersuite.google.com/app/apikey")
        print("2. Create a new API key")
        print("3. Set: export GEMINI_API_KEY='your-key-here'")
        print("4. Run this test again")
