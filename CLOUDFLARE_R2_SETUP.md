# Cloudflare R2 Storage Setup Guide

This guide explains how to configure Cloudflare R2 for document storage in FreightOps.

## Overview

FreightOps uses Cloudflare R2 (S3-compatible object storage) for storing driver documents, BOL files, and other compliance documents. R2 provides:

- **Cost-effective storage**: No egress fees (unlike AWS S3)
- **S3-compatible API**: Works with standard boto3 library
- **Global CDN**: Fast access worldwide
- **Secure**: Presigned URLs for temporary access

## Prerequisites

1. Cloudflare account
2. R2 bucket created in Cloudflare dashboard
3. R2 API token with read/write permissions

## Step 1: Create R2 Bucket

1. Log in to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Navigate to **R2** → **Create bucket**
3. Choose a bucket name (e.g., `freightops-documents`)
4. Select a location (choose closest to your users)

## Step 2: Create API Token

1. In Cloudflare Dashboard, go to **R2** → **Manage R2 API Tokens**
2. Click **Create API Token**
3. Set permissions:
   - **Object Read & Write** (for uploads/downloads)
   - **Admin Read** (for bucket management)
4. Copy the following values:
   - **Account ID**
   - **Access Key ID**
   - **Secret Access Key**
   - **Endpoint URL** (format: `https://<account-id>.r2.cloudflarestorage.com`)

## Step 3: Configure Environment Variables

Add these variables to your `.env` file in `backend_v2/`:

```bash
# Cloudflare R2 Configuration
R2_ACCOUNT_ID=your_account_id_here
R2_ACCESS_KEY_ID=your_access_key_id_here
R2_SECRET_ACCESS_KEY=your_secret_access_key_here
R2_BUCKET_NAME=freightops-documents
R2_ENDPOINT_URL=https://your_account_id.r2.cloudflarestorage.com

# Optional: Custom domain/CDN URL (if using Cloudflare CDN)
# R2_PUBLIC_URL=https://files.yourdomain.com
```

## Step 4: Install Dependencies

```bash
cd backend_v2
poetry install
```

This will install `boto3` which is used for R2 interactions.

## Step 5: Verify Configuration

Start your backend and test the upload endpoint:

```bash
poetry run uvicorn app.main:app --reload
```

## Usage Examples

### Upload Driver Document

```bash
curl -X POST "http://localhost:8000/api/drivers/{driver_id}/documents?document_type=cdl" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/document.pdf"
```

### Get Presigned Download URL

```bash
curl -X GET "http://localhost:8000/api/drivers/documents/{document_id}/download-url?expires_in=3600" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "document_id": "abc123",
  "url": "https://...presigned-url...",
  "expires_in": 3600
}
```

## Storage Structure

Files are organized in R2 with the following structure:

```
drivers/
  {company_id}/
    {driver_id}/
      {filename}_{timestamp}_{unique_id}.{ext}
```

Example:
```
drivers/company-123/driver-456/cdl_20240115_a1b2c3d4.pdf
```

## Security Considerations

1. **Presigned URLs**: All document access uses time-limited presigned URLs (default: 1 hour)
2. **Company Isolation**: Files are organized by company_id to prevent cross-tenant access
3. **Access Control**: Backend validates company_id before generating download URLs
4. **No Public Access**: R2 bucket should be configured as private (default)

## Optional: Custom Domain Setup

To use a custom domain for file access:

1. In Cloudflare Dashboard, go to **R2** → Your bucket → **Settings**
2. Add a custom domain (e.g., `files.yourdomain.com`)
3. Update `R2_PUBLIC_URL` in your `.env` file
4. Files will be accessible via: `https://files.yourdomain.com/drivers/...`

## Troubleshooting

### Error: "R2 configuration incomplete"
- Check that all R2 environment variables are set
- Verify values are correct (no extra spaces)

### Error: "Failed to upload file to R2"
- Verify API token has write permissions
- Check bucket name matches `R2_BUCKET_NAME`
- Ensure endpoint URL format is correct

### Error: "Access denied" on download
- Verify the document belongs to the user's company
- Check that the document_id is correct

## Migration from Local Storage

If you're migrating from local filesystem storage:

1. Upload existing files to R2 using the storage service
2. Update database `file_url` fields to use R2 keys instead of local paths
3. Remove local `uploads/` directory after verification

## Cost Optimization

- **Lifecycle Rules**: Set up R2 lifecycle rules to archive old documents
- **Compression**: Compress large files before upload
- **Cleanup**: Regularly delete unused documents to reduce storage costs

## Support

For issues or questions:
- Cloudflare R2 Docs: https://developers.cloudflare.com/r2/
- Cloudflare Community: https://community.cloudflare.com/


