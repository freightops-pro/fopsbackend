"""Quick test to see what text is extracted from the PDF."""
import io
import pdfplumber
from pathlib import Path

pdf_path = r"C:\Users\rcarb\Desktop\WAL-240055-DO(1).pdf"

print(f"Testing text extraction from: {pdf_path}")
print("=" * 60)

try:
    with open(pdf_path, 'rb') as f:
        file_bytes = f.read()

    print(f"PDF size: {len(file_bytes)} bytes")

    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        print(f"Pages: {len(pdf.pages)}")
        for i, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
                print(f"\nPage {i} extracted: {len(page_text)} characters")
                print("First 200 chars:")
                print(page_text[:200])
            else:
                print(f"\nPage {i}: No text extracted")

    full_text = "\n".join(text_parts)

    if full_text.strip():
        print("\n" + "=" * 60)
        print(f"SUCCESS! Extracted {len(full_text)} total characters")
        print("\nThis PDF has extractable text - AI OCR should work!")
    else:
        print("\n" + "=" * 60)
        print("NO TEXT FOUND - This is a scanned/image-only PDF")
        print("Poppler is required for OCR on this type of PDF")

except Exception as e:
    print(f"ERROR: {str(e)}")
