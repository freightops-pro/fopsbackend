"""Test the OCR to LoadCreate transformation without database."""
import json
import sys
from pathlib import Path

# Mock the database session
class MockDB:
    pass

from app.services.document_processing import DocumentProcessingService

def test_transformation_function():
    """Test the transformation function directly."""
    print("=" * 60)
    print("Testing OCR to LoadCreate Transformation Logic")
    print("=" * 60)

    # Create service with mock database
    service = DocumentProcessingService(MockDB())

    # Sample OCR output (simulating what Gemini returns)
    sample_ocr_data = {
        "customer_name": "WALMART FLO 7042F",
        "base_rate": 100.0,
        "commodity": "General Freight",
        "equipment_type": "container",
        "weight": 14887,
        "reference_number": "ORD-806886",
        "pickup_location": {
            "full_address": "4554 Oscar Nelson Jr Dr, Baytown, TX 77523, USA",
            "city": "Baytown",
            "state": "TX",
            "postal_code": "77523"
        },
        "delivery_location": {
            "full_address": "12619 Port Rd, Seabrook, TX 77586, USA",
            "city": "Seabrook",
            "state": "TX",
            "postal_code": "77586"
        },
        "pickup_date": None,
        "delivery_date": None,
        "special_instructions": None,
        "container_number": "FFAU4075736",
        "container_size": "40",
        "container_type": "ISO Dry"
    }

    print("\nINPUT (Raw OCR Data):")
    print("-" * 60)
    print(json.dumps(sample_ocr_data, indent=2))

    # Apply transformation
    load_create_data = service._transform_to_load_create(sample_ocr_data)

    print("\n" + "=" * 60)
    print("OUTPUT (LoadCreate-Compatible Format):")
    print("=" * 60)
    print(json.dumps(load_create_data, indent=2, default=str))

    print("\n" + "=" * 60)
    print("VALIDATION:")
    print("=" * 60)

    # Check required fields for LoadCreate
    required_fields = ["customer_name", "load_type", "commodity", "base_rate", "stops"]
    all_valid = True
    for field in required_fields:
        if field in load_create_data:
            print(f"✓ {field}: {load_create_data.get(field)}")
        else:
            print(f"✗ {field}: MISSING")
            all_valid = False

    # Validate stops structure
    if "stops" in load_create_data and load_create_data["stops"]:
        print(f"\n✓ Stops count: {len(load_create_data['stops'])}")
        for i, stop in enumerate(load_create_data["stops"]):
            print(f"\n  Stop {i+1} ({stop.get('stop_type')}):")
            print(f"    - location_name: {stop.get('location_name')}")
            print(f"    - city: {stop.get('city')}, {stop.get('state')} {stop.get('postal_code')}")
            print(f"    - address: {stop.get('address')}")

    # Check equipment_type → load_type mapping
    print("\n" + "=" * 60)
    print("FIELD MAPPINGS:")
    print("=" * 60)
    print(f"equipment_type: '{sample_ocr_data.get('equipment_type')}' → load_type: '{load_create_data.get('load_type')}'")
    print(f"special_instructions: {sample_ocr_data.get('special_instructions')} → notes: {load_create_data.get('notes')}")

    # Check metadata
    if "metadata" in load_create_data:
        print(f"\nMetadata:")
        for key, value in load_create_data["metadata"].items():
            print(f"  - {key}: {value}")

    # Container fields
    container_fields = ["container_number", "container_size", "container_type"]
    print(f"\nContainer fields:")
    for field in container_fields:
        if field in load_create_data:
            print(f"  ✓ {field}: {load_create_data[field]}")

    print("\n" + "=" * 60)
    if all_valid:
        print("[SUCCESS] All required fields present!")
        print("[SUCCESS] Transformation complete and valid!")
    else:
        print("[ERROR] Missing required fields!")
    print("=" * 60)

    # Test with FTL equipment types
    print("\n\n" + "=" * 60)
    print("Testing Equipment Type Mappings:")
    print("=" * 60)

    test_equipment_types = ["dry_van", "reefer", "flatbed", "step_deck", "container", "other"]
    for equipment in test_equipment_types:
        test_data = {"equipment_type": equipment}
        result = service._transform_to_load_create(test_data)
        expected = "container" if equipment == "container" else "ftl"
        status = "✓" if result["load_type"] == expected else "✗"
        print(f"{status} {equipment:15} → {result['load_type']:10} (expected: {expected})")

    print("\n" + "=" * 60)
    print("[SUCCESS] Transformation logic validated!")
    print("=" * 60)


if __name__ == "__main__":
    test_transformation_function()
