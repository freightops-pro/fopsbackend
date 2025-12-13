# Stripe Products Setup Guide

## Overview
You need to create 3 products in Stripe for FreightOps billing to work:

1. **Base Subscription** - Per-truck pricing
2. **Port Integration Add-on** - Flat monthly fee
3. **Check Payroll Add-on** - Base fee + per-employee pricing

## Step-by-Step Instructions

### 1. Access Stripe Dashboard

**For Test Mode (Development):**
1. Go to https://dashboard.stripe.com/test/products
2. Make sure you're in **Test mode** (toggle in top-left)

**For Live Mode (Production):**
1. Go to https://dashboard.stripe.com/products
2. Make sure you're in **Live mode** (toggle in top-left)

---

### 2. Create Base Subscription Product

**Steps:**
1. Click **"+ Add product"** button
2. Fill in the details:

**Product Information:**
- **Name**: `FreightOps Base Subscription`
- **Description**: `Per-truck subscription for FreightOps TMS platform`
- **Statement descriptor**: `FreightOps` (appears on customer's credit card statement)

**Pricing:**
- **Pricing model**: `Standard pricing`
- **Price**: `$75.00` USD
- **Billing period**: `Monthly`
- **Usage is metered**: Leave unchecked
- **Charge per unit**: Check this box
- **Unit label**: `truck` (plural: `trucks`)

**Advanced pricing options:**
- Click "Add another price" to add annual pricing:
  - Price: `$720.00` USD ($60/month × 12 months = 20% discount off $900)
  - Billing period: `Yearly`
  - Charge per unit: Check this box
  - Unit label: `truck` (plural: `trucks`)

3. Click **"Save product"**
4. **Copy the Product ID** (starts with `prod_...`)
   - Add to `.env`: `STRIPE_TEST_PRODUCT_ID=prod_...` (or `STRIPE_LIVE_PRODUCT_ID` for live)

---

### 3. Create Port Integration Add-on

**Steps:**
1. Click **"+ Add product"** button
2. Fill in the details:

**Product Information:**
- **Name**: `Port Integration Add-on`
- **Description**: `Container tracking and port terminal access integration`
- **Statement descriptor**: `FreightOps Port`

**Pricing:**
- **Pricing model**: `Standard pricing`
- **Price**: `$99.00` USD
- **Billing period**: `Monthly`
- **Usage is metered**: Leave unchecked

3. Click **"Save product"**
4. **Copy the Product ID** (starts with `prod_...`)
   - Add to `.env` JSON:
   ```bash
   STRIPE_TEST_ADDON_PRODUCTS='{"port_integration": "prod_...", "check_payroll": "prod_..."}'
   ```

---

### 4. Create Check Payroll Add-on

**Steps:**
1. Click **"+ Add product"** button
2. Fill in the details:

**Product Information:**
- **Name**: `Check Payroll Service`
- **Description**: `Full-service payroll processing powered by Check`
- **Statement descriptor**: `FreightOps Payroll`

**Pricing:**
- **Pricing model**: `Standard pricing`
- **Price**: `$39.00` USD (base price)
- **Billing period**: `Monthly`
- **Usage is metered**: Leave unchecked

**Note:** The $6/employee charge is calculated in our code and added to the base $39. So this product should just be $39, and we'll create the subscription with the total amount.

3. Click **"Save product"**
4. **Copy the Product ID** (starts with `prod_...`)
   - Add to `.env` JSON alongside port_integration:
   ```bash
   STRIPE_TEST_ADDON_PRODUCTS='{"port_integration": "prod_xxx", "check_payroll": "prod_yyy"}'
   ```

---

## Environment Variables to Update

After creating all products, update your `.env` file:

### Test Mode Example:
```bash
STRIPE_USE_LIVE_MODE=false

# Test Mode Keys
STRIPE_TEST_SECRET_KEY=sk_test_51...
STRIPE_TEST_PUBLISHABLE_KEY=pk_test_51...
STRIPE_TEST_WEBHOOK_SECRET=whsec_...
STRIPE_TEST_PRODUCT_ID=prod_ABC123  # Base subscription
STRIPE_TEST_ADDON_PRODUCTS='{"port_integration": "prod_DEF456", "check_payroll": "prod_GHI789"}'
```

### Live Mode Example:
```bash
STRIPE_USE_LIVE_MODE=true

# Live Mode Keys
STRIPE_LIVE_SECRET_KEY=sk_live_51...
STRIPE_LIVE_PUBLISHABLE_KEY=pk_live_51...
STRIPE_LIVE_WEBHOOK_SECRET=whsec_...
STRIPE_LIVE_PRODUCT_ID=prod_ABC123  # Base subscription
STRIPE_LIVE_ADDON_PRODUCTS='{"port_integration": "prod_DEF456", "check_payroll": "prod_GHI789"}'
```

---

## Pricing Summary

| Product | Price | Billing | Notes |
|---------|-------|---------|-------|
| Base Subscription | $75/truck/month | Monthly | Per unit pricing |
| Base Subscription | $60/truck/year | Annual | 20% discount |
| Port Integration | $99/month | Monthly | Flat rate add-on |
| Check Payroll | $39 + $6/employee | Monthly | Base + per-employee |

---

## Testing

### Test Card Numbers
Use these in Stripe test mode:

**Successful Payment:**
- Card: `4242 4242 4242 4242`
- Exp: Any future date
- CVC: Any 3 digits
- ZIP: Any 5 digits

**Payment Declines:**
- Generic decline: `4000 0000 0000 0002`
- Insufficient funds: `4000 0000 0000 9995`

**3D Secure (requires authentication):**
- Card: `4000 0027 6000 3184`

---

## Verification Steps

After creating products:

1. **Verify product IDs** are added to `.env`
2. **Restart your backend** to load new environment variables
3. **Test subscription creation:**
   - Register a new company
   - Check Stripe Dashboard → Customers
   - Verify customer and subscription were created
4. **Test trial period:**
   - Subscription should show status: `trialing`
   - Trial end date should be 14 days from creation
5. **Test add-ons:**
   - Activate Port Integration
   - Check Stripe Dashboard → Subscriptions
   - Should see separate subscription for add-on

---

## Troubleshooting

### "Product not found" error
- Check that `STRIPE_TEST_PRODUCT_ID` matches the product ID from Stripe Dashboard
- Make sure you're in the correct mode (test vs live)
- Product IDs start with `prod_`, not `price_`

### Add-ons not working
- Verify `STRIPE_TEST_ADDON_PRODUCTS` is valid JSON
- Use double quotes for keys and values
- Format: `'{"port_integration": "prod_...", "check_payroll": "prod_..."}'`
- Make sure there's no trailing comma

### Webhook secret missing
- Go to Stripe Dashboard → Developers → Webhooks
- Add endpoint: `https://your-domain.com/api/billing/webhook`
- Select events (listed in STRIPE_SETUP.md)
- Copy signing secret to `STRIPE_TEST_WEBHOOK_SECRET`

---

## Important Notes

1. **Create products in BOTH test and live mode** when going to production
2. **Product IDs are different** between test and live - update both in `.env`
3. **Prices cannot be edited** after creation - create new prices if needed
4. **Use test mode** for all development and staging environments
5. **Only switch to live mode** when ready for real payments

---

## Quick Checklist

- [ ] Created "FreightOps Base Subscription" product
- [ ] Created "Port Integration Add-on" product
- [ ] Created "Check Payroll Service" product
- [ ] Copied all product IDs
- [ ] Updated `.env` with product IDs
- [ ] Restarted backend server
- [ ] Tested customer creation
- [ ] Tested subscription creation
- [ ] Tested trial period
- [ ] Configured webhook endpoint
- [ ] Tested webhook delivery

---

## Support

**Stripe Documentation:**
- Products & Pricing: https://stripe.com/docs/billing/prices-guide
- Subscriptions: https://stripe.com/docs/billing/subscriptions/overview
- Testing: https://stripe.com/docs/testing

**FreightOps:**
- See `STRIPE_SETUP.md` for complete integration details
- See `STRIPE_FLOW.md` for billing flow documentation
