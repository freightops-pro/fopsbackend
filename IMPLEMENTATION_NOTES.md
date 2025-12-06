# AI OCR Implementation Notes

## Important: OCR Requires AI

**The old regex-based OCR was not working before AI was added.**

This means:
- ✅ **AI extraction (Gemini/Claude/OpenAI) = Working OCR**
- ❌ **Regex fallback = Poor/broken extraction** (kept for emergency use only)

### Implications

1. **Free tier must be generous enough to provide value**
   - Default: 25 AI extractions/month
   - Gemini provides 45,000 free/month, so we can afford higher limits
   - Users need AI to get working OCR

2. **When quota exceeded**
   - Users should see clear message: "Manual entry required or upgrade"
   - Regex fallback will attempt extraction but likely fail
   - Better UX: disable upload button and show upgrade prompt

3. **Current Default Limits (No Tiers)**
   ```
   All Companies: 25 OCR/month, 100 chat/month, 200 audits/month

   Can increase manually for specific customers via SQL:
   UPDATE ai_usage_quota
   SET monthly_ocr_limit = 100
   WHERE company_id = '...';
   ```

### Cost Analysis

**With Gemini (current default):**
- Free tier from Google: 45,000 requests/month
- Your cost: $0 for first 45,000 docs
- Beyond free tier: $0.50 per 1,000 docs

**Example monthly costs:**
- 10 companies × 25 docs/month = 250 docs = **FREE**
- 100 companies × 25 docs/month = 2,500 docs = **FREE**
- 1000 companies × 25 docs/month = 25,000 docs = **FREE**
- 10,000 companies × 25 docs/month = 250,000 docs = **$100/month**

**Conclusion:** Can afford to be generous with free tier since Gemini gives 45k/month free.

### When Users Hit Their Limit

Show simple message:

```
🎯 You've used all 25 AI document extractions this month

Options:
1. Enter load details manually
2. Contact sales for higher limits: sales@freightopspro.com

Your limit resets on the 1st of next month.
```

**Future:** When pricing tiers are implemented, show upgrade options here.

### Technical Notes

- AI provider defaults to Gemini (cheapest, free tier)
- Can switch to Claude or OpenAI via env var
- Usage is tracked in `ai_usage_log` table
- Quotas are in `ai_usage_quota` table
- Quotas reset monthly based on `current_month` field

### Future Improvements

1. **Better "out of quota" UX**
   - Show remaining quota in UI
   - Disable upload when quota exceeded
   - Prominent upgrade CTA

2. **Improve regex fallback** ✅ DONE
   - Improved patterns with better validation
   - Added sanity checks for rates/weights
   - Better city/state detection
   - Still not as good as AI, but works as emergency fallback

3. **Analytics dashboard**
   - Show AI cost per company
   - Track accuracy rates
   - Identify power users for upsell
