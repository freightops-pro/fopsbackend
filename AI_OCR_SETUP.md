# AI-Powered OCR Setup Guide

This guide will help you set up AI-powered document extraction using Google Gemini API (recommended) or other providers.

## 📊 **Cost Comparison**

| Provider | Cost per 1,000 documents | Free Tier |
|----------|-------------------------|-----------|
| **Gemini 2.0 Flash** (Recommended) | **$0.50** | **1,500/day** (45,000/month) |
| GPT-4o-mini | $1.50 | Limited |
| Claude 3.5 Sonnet | $20.00 | No |

---

## 🚀 **Quick Setup (Gemini - Recommended)**

### Step 1: Get Google AI API Key (FREE)

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click "Get API Key"
3. Click "Create API key in new project" (or select existing project)
4. Copy your API key (starts with `AIza...`)

**Free Tier Limits:**
- ✅ 1,500 requests/day = **45,000 documents/month FREE**
- ✅ 15 requests/minute
- ✅ No credit card required

### Step 2: Install Dependencies

```bash
cd c:\Users\rcarb\Downloads\FOPS\fopsbackend
poetry install
```

This will install:
- `google-generativeai` - Gemini API client
- `pillow` - Image processing
- `pdf2image` - PDF to image conversion

**Note:** `pdf2image` requires [poppler](https://github.com/oschwartz10612/poppler-windows/releases/) on Windows.

**To install poppler on Windows:**
1. Download latest release from [https://github.com/oschwartz10612/poppler-windows/releases/](https://github.com/oschwartz10612/poppler-windows/releases/)
2. Extract to `C:\poppler`
3. Add `C:\poppler\Library\bin` to your PATH

### Step 3: Set Environment Variables

Add to your `.env` file or Railway environment:

```bash
# AI OCR Configuration
AI_OCR_PROVIDER=gemini                  # Options: gemini, claude, openai
GOOGLE_AI_API_KEY=AIzaSy...             # Your Gemini API key
ENABLE_AI_OCR=true                      # Enable/disable AI OCR globally
```

### Step 4: Run Database Migration

```bash
cd c:\Users\rcarb\Downloads\FOPS\fopsbackend
poetry run alembic upgrade head
```

This creates:
- `ai_usage_log` table - Tracks all AI operations
- `ai_usage_quota` table - Manages usage limits per company

### Step 5: Restart Backend

```bash
cd c:\Users\rcarb\Downloads\FOPS\fopsbackend
poetry run uvicorn app.main:app --reload --port 8000
```

### Step 6: Test OCR

Upload a rate confirmation PDF through the frontend, or test via API:

```bash
curl -X POST "http://localhost:8000/api/documents/ocr" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@rate_confirmation.pdf"
```

---

## 🎯 **How It Works**

### 1. **Free Tier (Default)**
Every company starts with:
- **10 OCR documents/month** (AI-powered)
- **50 chat messages/month** (for FreightBot)
- **100 audits/month** (for Smart Audit)

### 2. **When Quota Exceeded**
- System automatically falls back to **regex extraction** (free, lower accuracy)
- User sees message: "Monthly OCR limit reached (10 documents). Upgrade plan for more."
- Regex extraction still works, just less accurate

### 3. **Extraction Flow**
```
Upload PDF → Check Quota → Within Limit?
                  ↓                 ↓
                 YES               NO
                  ↓                 ↓
             Gemini API      Regex Fallback
             (95% accuracy)  (70% accuracy)
                  ↓                 ↓
           Extract Fields    Extract Fields
                  ↓                 ↓
           Return JSON       Return JSON
```

### 4. **Usage Tracking**
All operations are logged in `ai_usage_log`:
- Operation type (ocr, chat, audit)
- Tokens used
- Cost estimate
- Success/failure status
- Timestamps

### 5. **Viewing Usage Stats**

```bash
# Get current usage
GET /api/ai/usage/stats

# Get quota details
GET /api/ai/usage/quota
```

Response:
```json
{
  "plan_tier": "free",
  "is_unlimited": false,
  "current_month": "2025-12",
  "ocr": {
    "used": 18,
    "limit": 25,
    "remaining": 7
  },
  "chat": {
    "used": 45,
    "limit": 100,
    "remaining": 55
  },
  "audit": {
    "used": 123,
    "limit": 200,
    "remaining": 77
  }
}
```

---

## 💰 **Upgrading Plans**

To upgrade a company's quota:

```sql
-- Example: Upgrade to Pro tier
UPDATE ai_usage_quota
SET
  plan_tier = 'pro',
  monthly_ocr_limit = 500,
  monthly_chat_limit = 1000,
  monthly_audit_limit = 5000
WHERE company_id = '<company_id>';
```

Or via API (HQ admin only):
```python
from app.services.ai_usage import AIUsageService

await ai_usage_service.upgrade_plan(
    company_id="...",
    plan_tier="pro",
    ocr_limit=500,
    chat_limit=1000,
    audit_limit=5000,
)
```

### Default Limits (No Pricing Tiers Yet)

All companies get:
- 25 OCR extractions/month
- 100 AI chat messages/month
- 200 Smart Audits/month

**To increase limits for specific customers:**
```sql
UPDATE ai_usage_quota
SET monthly_ocr_limit = 100,
    monthly_chat_limit = 500
WHERE company_id = 'customer-id-here';
```

**Note:** Since Gemini provides 45,000 requests/month free, your actual cost is $0 for most usage.

---

## 🔧 **Alternative Providers**

### Using Claude (Higher Accuracy, More Expensive)

```bash
# .env
AI_OCR_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-api03-...
ENABLE_AI_OCR=true
```

Then:
```bash
poetry add anthropic
```

### Using OpenAI (GPT-4o-mini)

```bash
# .env
AI_OCR_PROVIDER=openai
OPENAI_API_KEY=sk-proj-...
ENABLE_AI_OCR=true
```

Then:
```bash
poetry add openai
```

---

## 🔍 **Troubleshooting**

### Issue: "google-generativeai package not installed"
```bash
cd c:\Users\rcarb\Downloads\FOPS\fopsbackend
poetry add google-generativeai
```

### Issue: "pdf2image error: Unable to get page count"
- Install poppler (see Step 2 above)
- Add poppler to PATH
- Restart terminal

### Issue: "API key not configured"
- Check `.env` file has `GOOGLE_AI_API_KEY=...`
- Restart backend after adding env var

### Issue: "No valid JSON found in response"
- PDF quality too low
- Scanned image (not searchable text)
- Try uploading a better quality document

### Issue: "Quota exceeded" but shouldn't be
- Check current month in database: `SELECT * FROM ai_usage_quota WHERE company_id='...'`
- Usage resets on 1st of month
- Manually reset: `UPDATE ai_usage_quota SET current_ocr_usage=0 WHERE company_id='...'`

---

## 📊 **Monitoring**

### View Recent AI Operations
```sql
SELECT
  operation_type,
  status,
  created_at,
  cost_usd
FROM ai_usage_log
WHERE company_id = '<company_id>'
ORDER BY created_at DESC
LIMIT 20;
```

### Monthly Cost Report
```sql
SELECT
  DATE_TRUNC('month', created_at) as month,
  operation_type,
  COUNT(*) as operations,
  SUM(cost_usd) as total_cost
FROM ai_usage_log
WHERE company_id = '<company_id>'
GROUP BY month, operation_type
ORDER BY month DESC;
```

---

## 🎉 **Success!**

You now have:
- ✅ AI-powered OCR with Gemini (45,000 free docs/month)
- ✅ Automatic quota tracking and limits
- ✅ Fallback to regex when quota exceeded
- ✅ Usage analytics and cost tracking
- ✅ Multi-provider support (Gemini, Claude, OpenAI)

**Next Steps:**
1. Update frontend to show usage stats
2. Implement FreightBot AI chat
3. Add Smart Audit engine
4. Create pricing page for plan upgrades
