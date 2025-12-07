"""Test the OCR to LoadCreate transformation."""
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app.services.document_processing import DocumentProcessingService
from app.core.db import AsyncSessionFactory


async def test_transformation(pdf_path: str):
    """Test document processing with transformation."""
    print("=" * 60)
    print("Testing OCR to LoadCreate Transformation")
    print("=" * 60)
    print(f"\nPDF: {pdf_path}")
    print("-" * 60)

    # Read PDF file
    with open(pdf_path, 'rb') as f:
        file_bytes = f.read()

    # Create a mock UploadFile
    class MockUploadFile:
        def __init__(self, content: bytes, filename: str):
            self.content = content
            self.filename = filename

        async def read(self):
            return self.content

    file = MockUploadFile(file_bytes, Path(pdf_path).name)

    # Create service with database session
    async with AsyncSessionFactory() as db:
        service = DocumentProcessingService(db)

        # Process document
        result = await service.process_document(
            company_id="test-company-123",
            file=file,
            user_id="test-user-123",
        )

        print("\n[SUCCESS] Document processed!")
        print("\n" + "=" * 60)
        print("RAW OCR EXTRACTION:")
        print("=" * 60)
        print(json.dumps(result.parsed_payload, indent=2, default=str))

        if "load_create_data" in result.parsed_payload:
            print("\n" + "=" * 60)
            print("TRANSFORMED LOAD_CREATE DATA:")
            print("=" * 60)
            print(json.dumps(result.parsed_payload["load_create_data"], indent=2, default=str))

            print("\n" + "=" * 60)
            print("VALIDATION:")
            print("=" * 60)
            load_data = result.parsed_payload["load_create_data"]

            # Check required fields for LoadCreate
            required_fields = ["customer_name", "load_type", "commodity", "base_rate", "stops"]
            for field in required_fields:
                if field in load_data:
                    print(f"✓ {field}: {load_data[field]}")
                else:
                    print(f"✗ {field}: MISSING")

            # Validate stops structure
            if "stops" in load_data and load_data["stops"]:
                print(f"\n✓ Stops count: {len(load_data['stops'])}")
                for i, stop in enumerate(load_data["stops"]):
                    print(f"\n  Stop {i+1}:")
                    print(f"    - stop_type: {stop.get('stop_type')}")
                    print(f"    - location_name: {stop.get('location_name')}")
                    print(f"    - city: {stop.get('city')}")
                    print(f"    - state: {stop.get('state')}")
                    print(f"    - postal_code: {stop.get('postal_code')}")

            print("\n" + "=" * 60)
            print("[SUCCESS] Transformation complete!")
            print("=" * 60)
        else:
            print("\n[ERROR] No load_create_data found in response")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_transformation.py <path_to_pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    asyncio.run(test_transformation(pdf_path))
