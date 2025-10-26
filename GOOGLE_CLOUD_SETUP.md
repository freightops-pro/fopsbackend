# Google Cloud Vision OCR Setup

## Prerequisites

1. **Google Cloud Account**: You need a Google Cloud account with billing enabled
2. **Google Cloud Project**: Create a new project or use an existing one
3. **Vision API**: Enable the Cloud Vision API

## Setup Steps

### 1. Create Google Cloud Project
```bash
# Install Google Cloud CLI
# https://cloud.google.com/sdk/docs/install

# Create new project
gcloud projects create freightops-ocr --name="FreightOps OCR"

# Set project
gcloud config set project freightops-ocr
```

### 2. Enable Vision API
```bash
# Enable Cloud Vision API
gcloud services enable vision.googleapis.com
```

### 3. Create Service Account
```bash
# Create service account
gcloud iam service-accounts create freightops-ocr-service \
    --display-name="FreightOps OCR Service Account"

# Grant Vision API access
gcloud projects add-iam-policy-binding freightops-ocr \
    --member="serviceAccount:freightops-ocr-service@freightops-ocr.iam.gserviceaccount.com" \
    --role="roles/ml.developer"

# Create and download key
gcloud iam service-accounts keys create ./google-cloud-key.json \
    --iam-account=freightops-ocr-service@freightops-ocr.iam.gserviceaccount.com
```

### 4. Environment Variables

Add to your `.env` file:
```env
# Google Cloud Vision OCR
GOOGLE_CLOUD_PROJECT_ID=freightops-ocr
GOOGLE_APPLICATION_CREDENTIALS=./google-cloud-key.json
OCR_ENABLED=true
```

### 5. Install Dependencies

The required dependencies are already added to `requirements.txt`:
```bash
pip install google-cloud-vision==3.4.4
pip install google-cloud-storage==2.10.0
pip install Pillow==10.1.0
```

## Usage

### With Google Cloud (Production)
- Real OCR text extraction
- High accuracy
- Handles complex documents
- Requires billing

### Without Google Cloud (Development)
- Fallback text extraction
- Mock data generation
- No billing required
- Good for testing

## API Endpoints

### Rate Confirmation OCR
```http
POST /api/loads/extract-from-rate-confirmation
Content-Type: multipart/form-data

rateConfirmation: [image file]
```

### Bill of Lading OCR
```http
POST /api/loads/extract-from-bol
Content-Type: multipart/form-data

bol: [image file]
```

## Supported File Types
- PNG
- JPEG/JPG
- PDF
- TIFF
- BMP
- WEBP

## Error Handling

The OCR service gracefully handles:
- Missing Google Cloud credentials
- API rate limits
- Invalid file types
- Network errors
- Poor image quality

## Cost Estimation

Google Cloud Vision API pricing (as of 2024):
- First 1,000 requests/month: Free
- Additional requests: $1.50 per 1,000 requests
- Document text detection: $1.50 per 1,000 requests

## Testing

Test with sample documents:
```bash
# Test rate confirmation
curl -X POST "http://localhost:8000/api/loads/extract-from-rate-confirmation" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "rateConfirmation=@sample-rate-confirmation.jpg"

# Test BOL
curl -X POST "http://localhost:8000/api/loads/extract-from-bol" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "bol=@sample-bol.pdf"
```

## Troubleshooting

### Common Issues

1. **Authentication Error**
   - Check `GOOGLE_APPLICATION_CREDENTIALS` path
   - Verify service account permissions
   - Ensure key file is valid

2. **API Not Enabled**
   - Run: `gcloud services enable vision.googleapis.com`

3. **Billing Not Enabled**
   - Enable billing in Google Cloud Console
   - Add payment method

4. **Import Error**
   - Install dependencies: `pip install -r requirements.txt`

### Logs
Check application logs for OCR processing details:
```bash
# Backend logs
tail -f backend/logs/app.log

# Google Cloud logs
gcloud logging read "resource.type=cloud_function"
```

