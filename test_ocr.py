"""
Quick test script to verify AI OCR is working.

Usage:
    python test_ocr.py path/to/rate_confirmation.pdf
"""
import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.claude_ocr import ClaudeOCRService


async def test_ocr(pdf_path: str):
    """Test OCR on a sample PDF."""
    print("=" * 60)
    print("Testing AI OCR Configuration")
    print("=" * 60)

    # Check environment
    provider = os.getenv("AI_OCR_PROVIDER", "gemini")
    api_key = os.getenv("GOOGLE_AI_API_KEY", "")
    enabled = os.getenv("ENABLE_AI_OCR", "true")

    print(f"\nConfiguration:")
    print(f"  Provider: {provider}")
    print(f"  API Key: {'[OK] Set' if api_key and api_key != 'REPLACE_WITH_YOUR_GEMINI_API_KEY' else '[X] NOT SET - GET KEY AT https://aistudio.google.com/app/apikey'}")
    print(f"  Enabled: {enabled}")

    # Initialize service
    ocr_service = ClaudeOCRService()

    if not ocr_service.enabled:
        print("\n[X] ERROR: AI OCR is not enabled!")
        print("\nTo enable:")
        print("1. Get free API key: https://aistudio.google.com/app/apikey")
        print("2. Add to .env file: GOOGLE_AI_API_KEY=AIza...")
        print("3. Restart this test")
        return

    print(f"\n[OK] OCR Service initialized with model: {ocr_service.model}")

    # Test with PDF if provided
    if pdf_path and Path(pdf_path).exists():
        print(f"\nTesting extraction on: {pdf_path}")
        print("-" * 60)

        try:
            with open(pdf_path, 'rb') as f:
                file_bytes = f.read()

            print("Sending to Gemini API...")
            parsed_data, confidence, raw_text = await ocr_service.extract_from_document(
                file_bytes=file_bytes,
                filename=Path(pdf_path).name,
                document_type="rate_confirmation"
            )

            print("\n[SUCCESS!] OCR is working!")
            print("\nExtracted Data:")
            print("-" * 60)
            for key, value in parsed_data.items():
                conf = confidence.get(key, 0)
                print(f"  {key}: {value} (confidence: {conf:.0%})")

            print("\n" + "=" * 60)
            print("[SUCCESS] AI OCR IS WORKING CORRECTLY!")
            print("=" * 60)

        except Exception as e:
            print(f"\n[X] ERROR: {str(e)}")
            print("\nPossible issues:")
            print("- Invalid API key")
            print("- API rate limit exceeded")
            print("- Network connection issue")
            print("- PDF format not supported")

    else:
        print("\n[!] No PDF provided for testing")
        print("\nTo test with a PDF:")
        print("  python test_ocr.py path/to/rate_confirmation.pdf")
        print("\n[OK] Configuration looks good - ready to use!")


if __name__ == "__main__":
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(test_ocr(pdf_path))
