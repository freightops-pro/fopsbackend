#!/usr/bin/env python3
"""
Test OCR endpoint directly
"""

import os
import sys
import requests
from pathlib import Path

def test_ocr_endpoint():
    """Test OCR endpoint with actual PDF document"""
    
    # Set up environment
    os.environ['GEMINI_API_KEY'] = 'AIzaSyBJeSsvOc1UcI0UF78Qfm6bMTuI0UNc1eE'
    
    print("Testing OCR endpoint with WAL-240055-DO(1).pdf")
    print("=" * 50)
    
    # Path to the PDF file
    pdf_path = Path.home() / "Desktop" / "WAL-240055-DO(1).pdf"
    
    if not pdf_path.exists():
        print(f"ERROR PDF file not found at: {pdf_path}")
        return False
    
    print(f"OK Found PDF file: {pdf_path}")
    
    try:
        # Test the OCR endpoint
        url = "http://127.0.0.1:8000/api/loads/ocr/extract-from-rate-confirmation"
        
        # Prepare the file upload
        with open(pdf_path, 'rb') as f:
            files = {'rateConfirmation': ('WAL-240055-DO(1).pdf', f, 'application/pdf')}
            
            print(f"Testing endpoint: {url}")
            print("Sending POST request...")
            
            # Make the request
            response = requests.post(url, files=files, timeout=30)
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("SUCCESS OCR endpoint working!")
                print(f"Confidence: {result.get('confidence', 0)}")
                print(f"Extracted fields: {len(result.get('extractedFields', []))}")
                return True
            else:
                print(f"ERROR Endpoint failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"ERROR Error testing endpoint: {e}")
        return False

if __name__ == "__main__":
    success = test_ocr_endpoint()
    
    if success:
        print("\nSUCCESS OCR endpoint is working!")
        print("The API endpoint is properly configured and accessible.")
    else:
        print("\nERROR OCR endpoint test failed.")
        print("The API endpoint needs to be fixed.")

