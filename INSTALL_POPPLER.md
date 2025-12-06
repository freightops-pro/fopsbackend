# Installing Poppler for Windows

Poppler is required for `pdf2image` to convert PDFs to images for AI OCR.

## Option 1: Quick Install with Chocolatey (Easiest)

If you have Chocolatey installed:

```powershell
choco install poppler
```

## Option 2: Manual Install

1. **Download Poppler:**
   - Go to: https://github.com/oschwartz10612/poppler-windows/releases/
   - Download the latest release (e.g., `Release-24.08.0-0.zip`)

2. **Extract:**
   - Extract to `C:\poppler`
   - You should have `C:\poppler\Library\bin` folder

3. **Add to PATH:**
   - Press `Win + R`, type `sysdm.cpl`, press Enter
   - Go to "Advanced" tab → "Environment Variables"
   - Under "System variables", find "Path", click "Edit"
   - Click "New" and add: `C:\poppler\Library\bin`
   - Click OK on all dialogs

4. **Verify Installation:**
   ```bash
   # Open NEW terminal (important!)
   pdftoppm -v
   ```

5. **Test OCR Again:**
   ```bash
   cd c:\Users\rcarb\Downloads\FOPS\fopsbackend
   poetry run python test_ocr.py "C:\Users\rcarb\Desktop\WAL-240055-DO(1).pdf"
   ```

## Option 3: Alternative - Use Text-Based Extraction (No Poppler Needed)

If the PDF has text (not scanned image), we can extract text directly without poppler.

I can update the OCR service to try text extraction first before image conversion.
