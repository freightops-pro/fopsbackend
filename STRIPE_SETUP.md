# Stripe Subscription Setup

## Environment Variables Required

Add these to your `.env` file in the backend directory:

```bash
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_publishable_key_here
```

## Getting Your Stripe Keys

1. Create a Stripe account at https://stripe.com
2. Go to Developers → API Keys
3. Copy your "Publishable key" and "Secret key" (use test keys for development)
4. Add them to your `.env` file

## Setting Up Products in Stripe

The subscription system expects these Price IDs in Stripe:

1. **Starter Plan**: `price_starter_monthly` - $99/month
2. **Professional Plan**: `price_professional_monthly` - $199/month  
3. **Enterprise Plan**: `price_enterprise_monthly` - $399/month

### Creating Products in Stripe Dashboard

1. Go to Products in your Stripe dashboard
2. Create three products with the names above
3. For each product, create a recurring price with the monthly amounts
4. Copy the Price IDs and update them in `backend/app/routes/subscription.py` if needed

## Webhook Setup (Optional for Development)

For production, set up webhooks to handle subscription events:

1. Go to Developers → Webhooks in Stripe
2. Add endpoint: `https://yourdomain.com/api/subscription/webhook`
3. Select these events:
   - `customer.subscription.created`
   - `customer.subscription.updated` 
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`

## Testing

After setup:
1. Restart your backend server
2. Go to Settings → Subscription in the web dashboard
3. You should see the subscription plans instead of the setup message
4. Use Stripe's test card numbers for testing payments

## Dependencies

The backend will automatically install the `stripe` Python package when you run:

```bash
pip install -r requirements.txt
```
