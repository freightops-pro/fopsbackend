#!/usr/bin/env python3
"""
Google Cloud Vision OCR Setup Script

This script helps set up Google Cloud Vision API for OCR processing.
Run this script to check your setup and get instructions.
"""

import os
import sys
import json
from pathlib import Path

def check_gemini_setup():
    """Check if Gemini API key is available (easier alternative)"""
    print("Checking Gemini API Setup (Alternative to Google Cloud Vision)...")
    print("=" * 60)
    
    gemini_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    
    if gemini_key:
        print("✓ Gemini API key found!")
        print("  This is an easier alternative to Google Cloud Vision.")
        print("  Just set GEMINI_API_KEY environment variable with your API key.")
        print("\nTo get a Gemini API key:")
        print("1. Go to: https://makersuite.google.com/app/apikey")
        print("2. Create a new API key")
        print("3. Set environment variable: export GEMINI_API_KEY='your-key-here'")
        return True
    else:
        print("No Gemini API key found.")
        return False

def check_google_cloud_setup():
    """Check if Google Cloud Vision is properly configured"""
    print("Checking Google Cloud Vision OCR Setup...")
    print("=" * 50)
    
    # Check if credentials file exists
    credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    project_id = os.environ.get('GOOGLE_CLOUD_PROJECT')
    
    print(f"Credentials Path: {credentials_path or 'Not set'}")
    print(f"Project ID: {project_id or 'Not set'}")
    
    if credentials_path and os.path.exists(credentials_path):
        print("OK: Credentials file found!")
        
        # Check if it's a valid JSON file
        try:
            with open(credentials_path, 'r') as f:
                creds = json.load(f)
                print(f"OK: Valid JSON credentials file")
                print(f"Service Account Email: {creds.get('client_email', 'Unknown')}")
                print(f"Project ID in file: {creds.get('project_id', 'Unknown')}")
        except Exception as e:
            print(f"ERROR: Invalid credentials file: {e}")
            return False
    else:
        print("ERROR: Credentials file not found or not set")
        print_instructions()
        return False
    
    # Test Google Cloud Vision import
    try:
        from google.cloud import vision
        print("OK: Google Cloud Vision library available")
    except ImportError:
        print("ERROR: Google Cloud Vision library not installed")
        print("Run: pip install google-cloud-vision")
        return False
    
    # Test client initialization
    try:
        client = vision.ImageAnnotatorClient()
        print("OK: Google Cloud Vision client initialized successfully")
        print("SUCCESS: OCR setup is complete and ready to use!")
        return True
    except Exception as e:
        print(f"ERROR: Failed to initialize Google Cloud Vision client: {e}")
        print_instructions()
        return False

def print_instructions():
    """Print setup instructions"""
    print("\nSetup Instructions:")
    print("=" * 30)
    print("1. Go to Google Cloud Console: https://console.cloud.google.com/")
    print("2. Create a new project or select existing one")
    print("3. Enable Vision API:")
    print("   - Go to APIs & Services > Library")
    print("   - Search for 'Cloud Vision API'")
    print("   - Click 'Enable'")
    print("4. Create Service Account:")
    print("   - Go to IAM & Admin > Service Accounts")
    print("   - Click 'Create Service Account'")
    print("   - Name: 'freightops-ocr-service'")
    print("   - Role: 'Cloud Vision API User'")
    print("5. Create and download key:")
    print("   - Click on the service account")
    print("   - Go to 'Keys' tab")
    print("   - Click 'Add Key' > 'Create new key'")
    print("   - Choose 'JSON' format")
    print("   - Download the file")
    print("6. Set environment variables:")
    print("   export GOOGLE_APPLICATION_CREDENTIALS='/path/to/your/key.json'")
    print("   export GOOGLE_CLOUD_PROJECT='your-project-id'")
    print("7. Install dependencies:")
    print("   pip install google-cloud-vision")

def create_sample_env_file():
    """Create a sample .env file with Google Cloud settings"""
    env_content = """# Google Cloud Vision OCR Configuration
GOOGLE_CLOUD_PROJECT_ID=your-project-id-here
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json
OCR_ENABLED=true

# Example:
# GOOGLE_CLOUD_PROJECT_ID=freightops-ocr-123456
# GOOGLE_APPLICATION_CREDENTIALS=./google-cloud-key.json
# OCR_ENABLED=true
"""
    
    env_file = Path('.env.google_cloud')
    with open(env_file, 'w') as f:
        f.write(env_content)
    
    print(f"\nCreated sample environment file: {env_file}")
    print("Edit this file with your actual Google Cloud settings")

def test_ocr_with_sample():
    """Test OCR with a sample image if available"""
    print("\nTesting OCR with sample data...")
    
    try:
        from app.services.ocr_service import ocr_service
        
        # Create a simple test image (1x1 pixel PNG)
        import io
        from PIL import Image
        
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='white')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes = img_bytes.getvalue()
        
        # Test OCR extraction
        result = ocr_service.extract_load_data(img_bytes, "test-image.png")
        
        print("OK: OCR service working!")
        print(f"Confidence Score: {result.get('confidence_score', 0)}")
        print(f"Extracted Fields: {len([k for k, v in result.items() if v])}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: OCR test failed: {e}")
        return False

if __name__ == "__main__":
    print("FreightOps OCR Setup (Gemini API or Google Cloud Vision)")
    print("=" * 60)
    
    # Check for Gemini API first (easier setup)
    gemini_available = check_gemini_setup()
    
    if gemini_available:
        print("\n✓ Using Gemini API for OCR processing!")
        print("This is the recommended approach - much easier to set up.")
        
        # Test OCR with Gemini
        test_ocr_with_sample()
        print("\nSUCCESS: Gemini OCR setup complete!")
        
    else:
        print("\nFalling back to Google Cloud Vision setup...")
        # Check Google Cloud Vision setup
        setup_complete = check_google_cloud_setup()
        
        if not setup_complete:
            print("\n" + "="*60)
            print("RECOMMENDATION: Use Gemini API instead!")
            print("="*60)
            print("Gemini API is much easier to set up:")
            print("1. Go to: https://makersuite.google.com/app/apikey")
            print("2. Create a new API key")
            print("3. Set: export GEMINI_API_KEY='your-key-here'")
            print("4. Run this script again")
            print("\nOr continue with Google Cloud Vision setup:")
            print_instructions()
            create_sample_env_file()
            sys.exit(1)
        
        # Test OCR with Google Cloud Vision
        test_ocr_with_sample()
        print("\nSUCCESS: Google Cloud Vision setup complete!")
    
    print("\nUpload rate confirmations and BOLs to test the functionality.")
