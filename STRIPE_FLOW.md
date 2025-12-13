# Stripe Integration Flow - Source of Truth

## Overview
**Stripe is the source of truth** for all billing, trial, and payment status. Our database mirrors Stripe's state through webhooks and API syncing.

## How It Works

### 1. Company Signs Up (First Time)

**What Happens:**
1. User registers company account in FreightOps
2. Backend creates:
   - ✅ **Stripe Customer** (immediately)
   - ✅ **Stripe Subscription** with 14-day trial (immediately)
   - ✅ **Local subscription record** that mirrors Stripe

**Stripe API Call:**
```python
# Create customer
stripe.Customer.create(
    email=company.email,
    name=company.name,
    metadata={"company_id": company_id}
)

# Create subscription with trial
stripe.Subscription.create(
    customer=stripe_customer_id,
    items=[{...}],  # Base subscription
    trial_end=timestamp_14_days_from_now,
    payment_behavior="default_incomplete"  # No payment required during trial
)
```

**Result:**
- Stripe subscription status: `trialing`
- User has 14 days free access
- No payment method required yet

### 2. During Trial Period

**What Stripe Does:**
- ✅ Tracks trial automatically
- ✅ User has full access
- ✅ Sends webhook 3 days before trial ends: `customer.subscription.trial_will_end`
- ✅ No charges made

**What We Do:**
- Show trial banner: "X days remaining in trial"
- Encourage user to add payment method
- Sync status from Stripe on every billing data fetch

**Status Check:**
```python
# Every time user views billing page, we sync from Stripe
stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
# Update our database with Stripe's authoritative status
```

### 3. Trial Ends - Two Scenarios

#### Scenario A: Payment Method Already Added
**What Stripe Does:**
1. Trial ends automatically
2. Stripe attempts to charge the saved payment method
3. **If payment succeeds:**
   - Stripe sends webhook: `invoice.payment_succeeded`
   - Subscription status → `active`
4. **If payment fails:**
   - Stripe sends webhook: `invoice.payment_failed`
   - Subscription status → `past_due`
   - Stripe retries payment automatically (Smart Retries)

**What We Do:**
- Webhook handler updates our database status
- User continues to have access (if payment succeeded)
- User sees "Payment failed" banner (if payment failed)

#### Scenario B: No Payment Method Added
**What Stripe Does:**
1. Trial ends automatically
2. No payment method to charge
3. Subscription status → `unpaid`
4. Stripe sends webhook: `customer.subscription.updated`

**What We Do:**
- Webhook updates status to `unpaid`
- Frontend shows **Payment Required Gate**
- User must add payment to continue

### 4. User Adds Payment Method

**Frontend:**
- Stripe Elements collects card info
- Creates Stripe PaymentMethod
- Sends `payment_method_id` to backend

**Backend:**
```python
# Attach payment method to customer
stripe.PaymentMethod.attach(
    payment_method_id,
    customer=stripe_customer_id
)

# Set as default
stripe.Customer.modify(
    stripe_customer_id,
    invoice_settings={"default_payment_method": payment_method_id}
)

# Stripe automatically charges for the subscription
```

**What Stripe Does:**
- Immediately attempts to charge
- If successful → sends `invoice.payment_succeeded` webhook
- If failed → sends `invoice.payment_failed` webhook
- Updates subscription status accordingly

### 5. Ongoing Billing

**What Stripe Handles:**
- ✅ Monthly/annual billing automatically
- ✅ Pro-rated charges when truck count changes
- ✅ Payment retries if card declines
- ✅ Invoice generation
- ✅ Email receipts

**What We Track via Webhooks:**
- `customer.subscription.updated` → Status changes
- `invoice.payment_succeeded` → Successful payments
- `invoice.payment_failed` → Failed payments
- `customer.subscription.deleted` → Cancellations

### 6. Add-ons (Port Integration, Check Payroll)

**When User Activates Add-on:**
```python
# Create separate Stripe subscription for add-on
stripe.Subscription.create(
    customer=stripe_customer_id,
    items=[{...}],  # Add-on product
    proration_behavior="create_prorations"  # Charge immediately, prorated
)
```

**What Stripe Does:**
- ✅ Charges immediately (no trial for add-ons)
- ✅ Pro-rates charge for current billing period
- ✅ Sends `invoice.payment_succeeded` if payment works
- ✅ Sends `invoice.payment_failed` if payment fails

### 7. Subscription Changes

**When User Changes Truck Count:**
```python
stripe.Subscription.modify(
    subscription_id,
    items=[{"quantity": new_truck_count}],
    proration_behavior="create_prorations"
)
```

**What Stripe Does:**
- ✅ Calculates pro-rated charge/credit
- ✅ Applies to next invoice
- ✅ Sends webhook with updated subscription

## Webhook Event Handlers

### `customer.subscription.updated`
**Fired when:** Subscription status changes, trial ends, etc.
**We do:**
- Update subscription status in database
- Update trial dates
- Update period dates

### `invoice.payment_succeeded`
**Fired when:** Payment successful
**We do:**
- Save invoice to database
- Update subscription status to `active`
- User keeps access

### `invoice.payment_failed`
**Fired when:** Payment failed
**We do:**
- Update subscription status to `past_due`
- Show payment failure message
- Stripe will retry automatically

### `customer.subscription.trial_will_end`
**Fired when:** 3 days before trial ends
**We do:**
- Send email reminder (TODO)
- Show "trial ending soon" banner

### `customer.subscription.deleted`
**Fired when:** Subscription canceled
**We do:**
- Update status to `canceled`
- Block access (or allow until period end, depending on settings)

## Payment Status Flow

```
Company Signs Up
    ↓
[Stripe Customer Created]
    ↓
[Stripe Subscription Created with trial_end]
    ↓
Status: trialing
    ↓
14 Days Pass
    ↓
Trial Ends Automatically
    ↓
┌─────────────────┴─────────────────┐
│                                   │
Payment Method Exists          No Payment Method
│                                   │
Stripe Charges                 Status → unpaid
│                                   │
├─Success: active              Payment Gate Shown
├─Failed: past_due                  │
│                              User Adds Card
│                                   │
│                              Stripe Charges
│                                   │
└──────────────┬────────────────────┘
               ↓
        User Has Access
```

## Key Principles

1. **Stripe is the source of truth** - Always sync from Stripe, never assume
2. **Webhooks update our database** - Real-time status changes
3. **API sync on data fetch** - Refresh from Stripe when user views billing
4. **No manual trial tracking** - Stripe manages trial automatically
5. **Payment status from webhooks** - Don't guess, wait for Stripe to tell us

## Testing Checklist

- [ ] Company signs up → Stripe customer created
- [ ] Company signs up → Stripe subscription created with trial
- [ ] Trial shows correct days remaining (from Stripe)
- [ ] Trial ends → status changes to unpaid (if no payment)
- [ ] Trial ends → payment charged (if payment method exists)
- [ ] Add payment method → Stripe charges immediately
- [ ] Payment succeeds → webhook updates status to active
- [ ] Payment fails → webhook updates status to past_due
- [ ] Add-on activated → immediate prorated charge
- [ ] Truck count changed → prorated charge applied
- [ ] Webhook signature validation works
- [ ] Failed webhooks logged but don't crash

## Error Handling

**If Stripe API call fails:**
- Log error
- Show user-friendly message
- Don't update database with incorrect state
- Retry on next request

**If webhook fails:**
- Log to `billing_stripe_webhook_event` table
- Alert on repeated failures
- Manual reconciliation may be needed

**If sync from Stripe fails:**
- Use cached database values
- Show warning banner
- Retry automatically on next data fetch
