# Stripe Billing Integration - Setup Complete

## Overview
Complete Stripe billing integration for FreightOps TMS with support for:
- 14-day trial period for new signups
- Truck-based pricing ($49/truck monthly, $39/truck annual)
- Add-on services (Port Integration, Check Payroll)
- Self-serve and contract subscription types
- HQ admin oversight and management

## Database Schema

### Tables Created
1. **billing_subscription** - Main subscription data
2. **billing_subscription_addon** - Add-on services
3. **billing_payment_method** - Customer payment methods
4. **billing_stripe_invoice** - Invoice records
5. **billing_stripe_webhook_event** - Webhook event log

### Migration Status
✅ Migration applied: `20251212_000001_add_billing_tables`
✅ Merged migration: `27da85cbf832_merge_billing_and_main_migrations`

## Environment Variables Required

Add these to your `.env` file:

```bash
# Stripe Mode Toggle - Switch between test and live mode
# Set to true for production, false for development/staging
STRIPE_USE_LIVE_MODE=false

# Stripe Test Mode Keys (for development/staging)
# Get from: https://dashboard.stripe.com/test/apikeys
STRIPE_TEST_SECRET_KEY=sk_test_...
STRIPE_TEST_PUBLISHABLE_KEY=pk_test_...
STRIPE_TEST_WEBHOOK_SECRET=whsec_...
STRIPE_TEST_PRODUCT_ID=prod_...
STRIPE_TEST_ADDON_PRODUCTS='{"port_integration": "prod_...", "check_payroll": "prod_..."}'

# Stripe Live Mode Keys (for production)
# Get from: https://dashboard.stripe.com/apikeys
STRIPE_LIVE_SECRET_KEY=sk_live_...
STRIPE_LIVE_PUBLISHABLE_KEY=pk_live_...
STRIPE_LIVE_WEBHOOK_SECRET=whsec_...
STRIPE_LIVE_PRODUCT_ID=prod_...
STRIPE_LIVE_ADDON_PRODUCTS='{"port_integration": "prod_...", "check_payroll": "prod_..."}'
```

### Switching Between Test and Live Mode

The system automatically selects the correct Stripe keys based on `STRIPE_USE_LIVE_MODE`:

**Development/Staging** (Test Mode):
```bash
STRIPE_USE_LIVE_MODE=false
```
- Uses test keys (sk_test_*, pk_test_*)
- All payments are simulated
- Use test card numbers: `4242 4242 4242 4242`
- No real money charged

**Production** (Live Mode):
```bash
STRIPE_USE_LIVE_MODE=true
```
- Uses live keys (sk_live_*, pk_live_*)
- Real payments processed
- Real money charged to customer cards

**Benefits**:
- Keep both test and live credentials in your `.env` file
- Switch between modes with a single environment variable
- Prevent accidental use of live keys in development
- Easily test against Stripe test mode before going live

## API Endpoints

### Tenant Endpoints (Protected)
All endpoints require authentication and belong to the tenant's company.

**GET /api/billing**
- Returns complete billing data (subscription, add-ons, payment method, invoices)

**PATCH /api/billing/subscription**
- Update truck count or billing cycle
- Self-serve customers only

**POST /api/billing/add-ons**
- Activate Port Integration or Check Payroll
- ⚠️ Charged immediately without trial period

**DELETE /api/billing/add-ons/{service}**
- Deactivate add-on service
- Can cancel immediately or at period end

**POST /api/billing/checkout-session**
- Create Stripe Checkout session for adding payment method
- Used when trial expires

**POST /api/billing/portal-session**
- Create Stripe Customer Portal session
- Redirects to Stripe-hosted payment management

**POST /api/billing/subscription/cancel**
- Cancel subscription (self-serve only)

**POST /api/billing/subscription/reactivate**
- Reactivate canceled subscription (self-serve only)

**POST /api/billing/webhook**
- Stripe webhook endpoint (called by Stripe)
- Handles: subscription updates, payment success/failure, trial ending

### HQ Admin Endpoints (HQ_ADMIN role required)

**GET /api/admin/billing/all-subscriptions**
- View all tenant subscriptions with revenue metrics
- Filter by status and subscription type

**GET /api/admin/billing/company/{company_id}**
- View specific company's billing data

**PATCH /api/admin/billing/company/{company_id}/subscription-type**
- Change between self_serve and contract

**POST /api/admin/billing/company/{company_id}/pause**
- Pause subscription (for non-payment, abuse, etc.)

**POST /api/admin/billing/company/{company_id}/unpause**
- Reactivate paused subscription

## Subscription Business Logic

### Trial Period
- **Duration**: 14 days for new signups
- **Trial Type**: Self-serve customers only
- **Payment Gate**: Dashboard access blocked when trial expires without payment
- **Add-ons**: No trial - charged immediately

### Pricing Structure
**Base Subscription**
- Monthly: $49 per truck
- Annual: $39 per truck (20% discount)

**Add-ons** (charged immediately)
- Port Integration: $99/month
- Check Payroll: $39/month + $6 per employee

### Subscription Types
1. **Self-Serve**
   - Can update truck count and billing cycle
   - Can activate/deactivate add-ons
   - Can cancel subscription
   - Subject to payment gate when trial expires

2. **Contract**
   - Managed by FreightOps HQ staff
   - Cannot self-service changes
   - No payment gates
   - Custom pricing possible

### Payment Gate
When trial expires and no payment method is on file:
- Dashboard access blocked
- User sees payment required screen
- Redirected to Stripe Checkout
- Access restored after successful payment setup

## Stripe Webhook Configuration

### Required Webhooks
Configure these in Stripe Dashboard → Developers → Webhooks:

**Endpoint URL**: `https://your-domain.com/api/billing/webhook`

**Events to subscribe to**:
- `customer.subscription.updated` - Subscription status changes
- `customer.subscription.deleted` - Subscription canceled
- `invoice.payment_succeeded` - Successful payment
- `invoice.payment_failed` - Payment failure
- `customer.subscription.trial_will_end` - 3 days before trial ends

### Webhook Verification
All webhook events are verified using the `STRIPE_WEBHOOK_SECRET` to prevent spoofing.

## Frontend Integration

### Payment Required Gate
Located at: `src/components/billing/payment-required-gate.tsx`
- Automatically shown when trial expires without payment
- Only for self-serve customers
- Contract customers never see payment gate

### Billing Gate Wrapper
Located at: `src/components/routing/billing-gate.tsx`
- Wraps all protected routes
- Checks subscription status before allowing access
- HQ admins bypass all billing checks

### Settings Pages
All settings pages functional:
- **Subscriptions** (`/settings/subscriptions`) - Full Stripe integration
- **Security** (`/settings/security`) - 2FA, session timeout
- **Roles & Access** (`/settings/roles`) - Team member management
- **Integrations** (`/settings/integrations`) - API connections
- **Automation** (`/settings/automation`) - Alerts and rules

## Testing Checklist

### Backend Tests
- [ ] Create new company → subscription automatically created in trial
- [ ] Trial expires → subscription status changes to "unpaid"
- [ ] Add payment method → subscription activates
- [ ] Activate Port Integration → charged immediately
- [ ] Activate Check Payroll → charged based on employee count
- [ ] Update truck count → prorated charge/credit
- [ ] Cancel subscription → status changes, access at period end
- [ ] Stripe webhook processing → events logged and processed

### Frontend Tests
- [ ] Trial user sees trial banner with days remaining
- [ ] Trial expires → payment gate blocks dashboard access
- [ ] Click "Add Payment" → redirects to Stripe Checkout
- [ ] After payment → dashboard access restored
- [ ] Contract customer never sees payment gate
- [ ] HQ admin can view all subscriptions
- [ ] Settings pages all functional and navigable

### Integration Tests
- [ ] Webhook signature verification works
- [ ] Payment succeeded webhook → subscription activates
- [ ] Payment failed webhook → subscription marked past_due
- [ ] Subscription updated webhook → local status synced
- [ ] Trial ending webhook → notification sent (when implemented)

## Next Steps

### Required Before Production
1. **Add Stripe API keys to production `.env`**
2. **Create products in Stripe Dashboard**:
   - Base subscription product
   - Port Integration add-on product
   - Check Payroll add-on product
3. **Configure webhook endpoint in Stripe**
4. **Test webhook delivery in Stripe Dashboard**

### Recommended Enhancements
1. **Notification System**
   - Email when trial ending (3 days before)
   - Email when payment fails
   - Email receipts after successful payment

2. **HQ Admin Dashboard**
   - MRR (Monthly Recurring Revenue) metrics
   - Churn analysis
   - Trial conversion rates

3. **Usage-Based Billing**
   - Track actual truck usage
   - Automatic truck count adjustments
   - Overage charges for exceeding plan limits

4. **Payment Retry Logic**
   - Automatic retry for failed payments
   - Dunning emails
   - Grace period before access suspension

## Files Modified/Created

### Backend
- ✅ `app/models/billing.py` - Database models
- ✅ `app/schemas/billing.py` - Pydantic schemas
- ✅ `app/services/billing.py` - Stripe service integration
- ✅ `app/routers/billing.py` - Tenant billing endpoints + webhook
- ✅ `app/routers/admin.py` - HQ admin billing endpoints
- ✅ `app/core/config.py` - Stripe configuration
- ✅ `app/api/router.py` - Billing router registration
- ✅ `app/models/company.py` - Subscription relationship
- ✅ `alembic/versions/20251212_000001_add_billing_tables.py` - Migration

### Frontend
- ✅ `src/types/billing.ts` - TypeScript types
- ✅ `src/hooks/use-billing.ts` - React hooks for API calls
- ✅ `src/components/billing/payment-required-gate.tsx` - Payment gate
- ✅ `src/components/routing/billing-gate.tsx` - Route wrapper
- ✅ `src/components/routing/protected-route.tsx` - Billing integration
- ✅ `src/pages/settings/subscriptions-settings.tsx` - Full Stripe UI
- ✅ `src/pages/settings/security-settings.tsx` - Security settings
- ✅ `src/pages/settings/roles-access-settings.tsx` - Roles management
- ✅ `src/App.tsx` - Settings routes
- ✅ `src/lib/module-nav.tsx` - Dashboard navigation fix
- ✅ `src/components/navigation/tenant-sidebar.tsx` - Logo link fix

### Dependencies
- ✅ `stripe` - Python Stripe SDK (v14.0.1)

## Support

For Stripe-specific issues:
- Stripe Dashboard: https://dashboard.stripe.com
- Stripe Docs: https://stripe.com/docs/api
- Webhook Logs: https://dashboard.stripe.com/webhooks

For FreightOps billing questions:
- Contact HQ Admin team
- Review this documentation
- Check application logs for errors
