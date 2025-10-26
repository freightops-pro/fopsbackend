#!/usr/bin/env python3
"""
Test OCR functionality directly with the PDF document
"""

import os
import sys
from pathlib import Path

def test_ocr_with_pdf():
    """Test OCR with the actual PDF document"""
    
    # Set up environment
    os.environ['GEMINI_API_KEY'] = 'AIzaSyBJeSsvOc1UcI0UF78Qfm6bMTuI0UNc1eE'
    
    # Import OCR service
    sys.path.append(str(Path(__file__).parent))
    from app.services.ocr_service import OCRService
    
    print("Testing OCR with WAL-240055-DO(1).pdf")
    print("=" * 50)
    
    # Initialize OCR service
    ocr_service = OCRService()
    
    if ocr_service.use_gemini:
        print("OK Using Gemini API for OCR processing")
    else:
        print("WARNING Using fallback OCR processing")
    
    # Path to the PDF file
    pdf_path = Path.home() / "Desktop" / "WAL-240055-DO(1).pdf"
    
    if not pdf_path.exists():
        print(f"ERROR PDF file not found at: {pdf_path}")
        return False
    
    print(f"OK Found PDF file: {pdf_path}")
    
    try:
        # Read the PDF file
        with open(pdf_path, 'rb') as f:
            file_content = f.read()
        
        print(f"OK Read PDF file ({len(file_content)} bytes)")
        
        # Extract data using OCR
        print("Processing document with OCR...")
        result = ocr_service.extract_load_data(file_content, "WAL-240055-DO(1).pdf")
        
        print("\nSUCCESS OCR Processing Complete!")
        print("=" * 50)
        
        # Display results
        print("Extracted Data:")
        for key, value in result.items():
            if value and key not in ['source', 'extraction_date', 'original_filename', 'confidence_score']:
                print(f"  {key}: {value}")
        
        print(f"\nConfidence Score: {result.get('confidence_score', 0):.2f}")
        print(f"Source: {result.get('source', 'unknown')}")
        
        return True
        
    except Exception as e:
        print(f"ERROR Error processing PDF: {e}")
        return False

if __name__ == "__main__":
    success = test_ocr_with_pdf()
    
    if success:
        print("\nSUCCESS OCR test completed successfully!")
        print("The OCR functionality is working with your PDF document.")
    else:
        print("\nERROR OCR test failed.")
        print("Please check the error messages above.")
