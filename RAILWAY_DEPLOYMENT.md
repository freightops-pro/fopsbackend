# FreightOps Railway Deployment Guide

Complete guide for deploying FreightOps frontend and backend to Railway.app

## Table of Contents
- [Prerequisites](#prerequisites)
- [Backend Deployment](#backend-deployment)
- [Frontend Deployment](#frontend-deployment)
- [Database Setup](#database-setup)
- [Environment Variables](#environment-variables)
- [Post-Deployment](#post-deployment)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### 1. Railway Account
- Sign up at [railway.app](https://railway.app)
- Install Railway CLI (optional): `npm install -g @railway/cli`

### 2. Git Repositories
- **Backend**: https://github.com/freightops-pro/fopsbackend.git
- **Frontend**: https://github.com/freightops-pro/fopsfrontend.git

### 3. Required Services
- PostgreSQL database
- Redis (for caching)
- Cloudflare R2 or AWS S3 (for file storage)

---

## Backend Deployment

### Step 1: Create New Project
1. Go to [railway.app/new](https://railway.app/new)
2. Click "Deploy from GitHub repo"
3. Select `freightops-pro/fopsbackend`
4. Railway will auto-detect it as a Python project

### Step 2: Add PostgreSQL
1. In your project, click "New" → "Database" → "Add PostgreSQL"
2. Railway will automatically create and link the database
3. The `DATABASE_URL` variable will be available automatically

### Step 3: Add Redis
1. Click "New" → "Database" → "Add Redis"
2. Railway will provide `REDIS_URL` automatically

### Step 4: Configure Build Settings

Railway will use the existing `railway.json` configuration:

```json
{
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "pip install -r requirements.txt && pip install gunicorn"
  },
  "deploy": {
    "startCommand": "gunicorn app.main:app -w 8 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT",
    "healthcheckPath": "/health/status",
    "restartPolicyType": "ON_FAILURE"
  }
}
```

### Step 5: Set Environment Variables

Go to your backend service → "Variables" → "Raw Editor" and paste:

```bash
# Copy from fopsbackend/.env.railway.example
# Replace all <placeholder> values with actual credentials
ENVIRONMENT=production
DEBUG=False

# JWT & Security
JWT_SECRET_KEY=<run: openssl rand -hex 32>
ENCRYPTION_KEY=<run: openssl rand -base64 32>
SSN_ENCRYPTION_KEY=<run: openssl rand -base64 32>

# Database (automatically provided by Railway)
DATABASE_URL=${{Postgres.DATABASE_URL}}
DB_POOL_SIZE=50
DB_MAX_OVERFLOW=100
DB_SSL_MODE=require

# Redis (automatically provided by Railway)
REDIS_URL=${{Redis.REDIS_URL}}

# Application URLs
FRONTEND_URL=https://your-frontend.railway.app
BACKEND_URL=${{RAILWAY_PUBLIC_DOMAIN}}
CORS_ORIGINS=https://your-frontend.railway.app

# Synctera Banking
SYNCTERA_API_KEY=<your-synctera-api-key>
SYNCTERA_API_URL=https://api.synctera.com
SYNCTERA_ENVIRONMENT=production

# ELD Integrations
SAMSARA_CLIENT_ID=<your-samsara-client-id>
SAMSARA_CLIENT_SECRET=<your-samsara-client-secret>
MOTIVE_API_KEY=<your-motive-api-key>

# Fuel Cards
WEX_API_KEY=<your-wex-api-key>
COMDATA_API_KEY=<your-comdata-api-key>

# Payment Processing
STRIPE_SECRET_KEY=<your-stripe-secret-key>
STRIPE_WEBHOOK_SECRET=<your-stripe-webhook-secret>

# QuickBooks
QUICKBOOKS_CLIENT_ID=<your-quickbooks-client-id>
QUICKBOOKS_CLIENT_SECRET=<your-quickbooks-client-secret>
QUICKBOOKS_REDIRECT_URI=https://your-backend.railway.app/quickbooks/callback

# File Storage (S3/R2)
AWS_ACCESS_KEY_ID=<your-access-key>
AWS_SECRET_ACCESS_KEY=<your-secret-key>
AWS_S3_BUCKET=freightops-documents
AWS_REGION=us-east-1

# Email (SendGrid)
SENDGRID_API_KEY=<your-sendgrid-key>
FROM_EMAIL=noreply@yourcompany.com

# SMS (Twilio)
TWILIO_ACCOUNT_SID=<your-twilio-sid>
TWILIO_AUTH_TOKEN=<your-twilio-token>
TWILIO_PHONE_NUMBER=<your-phone>

# Monitoring
SENTRY_DSN=<your-sentry-dsn>
SENTRY_ENVIRONMENT=production

# Feature Flags
ENABLE_BANKING_MODULE=true
ENABLE_ELD_INTEGRATION=true
ENABLE_FUEL_CARDS=true
```

### Step 6: Run Database Migrations

After deployment, run migrations:

```bash
# Using Railway CLI
railway run alembic upgrade head

# Or via Railway's service shell
alembic upgrade head
```

### Step 7: Verify Backend
- Check deployment logs for errors
- Visit `https://your-backend.railway.app/docs` for API documentation
- Test health endpoint: `https://your-backend.railway.app/health/status`

---

## Frontend Deployment

### Step 1: Create Frontend Service
1. In the same Railway project, click "New" → "GitHub Repo"
2. Select `freightops-pro/fopsfrontend`
3. Railway will auto-detect it as a Node.js/Vite project

### Step 2: Configure Build Settings

Create a `railway.json` in the frontend repo:

```json
{
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "npm install && npm run build"
  },
  "deploy": {
    "startCommand": "npx serve -s dist -l $PORT",
    "restartPolicyType": "ON_FAILURE"
  }
}
```

### Step 3: Install Serve Package

Add to `package.json` dependencies:

```json
{
  "dependencies": {
    "serve": "^14.2.1"
  }
}
```

### Step 4: Set Environment Variables

Go to frontend service → "Variables" → "Raw Editor":

```bash
# Copy from frontend/.env.railway.example
# Replace with actual values

# API Configuration
VITE_API_BASE_URL=https://your-backend.railway.app
VITE_WEBSOCKET_URL=wss://your-backend.railway.app/ws

# Supabase
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=<your-supabase-anon-key>

# Maps
VITE_GOOGLE_MAPS_API_KEY=<your-google-maps-key>
VITE_MAPBOX_ACCESS_TOKEN=<your-mapbox-token>

# Analytics
VITE_GOOGLE_ANALYTICS_ID=<your-ga-id>
VITE_SENTRY_DSN=<your-sentry-dsn>
VITE_SENTRY_ENVIRONMENT=production

# Payments
VITE_STRIPE_PUBLISHABLE_KEY=<your-stripe-publishable-key>

# Feature Flags
VITE_ENABLE_BANKING_MODULE=true
VITE_ENABLE_ELD_INTEGRATION=true
VITE_ENABLE_FUEL_CARDS=true

# Environment
VITE_ENVIRONMENT=production
NODE_ENV=production
```

### Step 5: Update CORS Origins

Go back to backend variables and update:

```bash
CORS_ORIGINS=https://your-actual-frontend-url.railway.app
FRONTEND_URL=https://your-actual-frontend-url.railway.app
```

### Step 6: Verify Frontend
- Visit your frontend Railway URL
- Check that it connects to the backend
- Test login and API calls

---

## Database Setup

### Initial Database Schema

After deploying backend and running migrations:

1. **Create Admin User** (via Railway shell or API):
```python
# Run in Railway shell
python scripts/create_admin_user.py
```

2. **Seed Initial Data** (if needed):
```python
# Company, roles, default settings
python scripts/seed_data.py
```

### Database Backups

Railway automatically backs up PostgreSQL databases. Configure:
1. Go to PostgreSQL service → "Backups"
2. Set retention policy (7 days recommended)
3. Enable automatic daily backups

---

## Environment Variables Reference

### Critical Security Variables

These MUST be unique and secure:

```bash
# Generate with: openssl rand -hex 32
JWT_SECRET_KEY=<256-bit-hex-key>

# Generate with: openssl rand -base64 32
ENCRYPTION_KEY=<32-byte-base64-key>
SSN_ENCRYPTION_KEY=<32-byte-base64-key>
```

### Service Integration Keys

Obtain from respective providers:

- **Synctera**: [synctera.com/dashboard](https://synctera.com)
- **Samsara**: [cloud.samsara.com/settings/api](https://cloud.samsara.com)
- **Stripe**: [dashboard.stripe.com/apikeys](https://dashboard.stripe.com)
- **Google Maps**: [console.cloud.google.com/apis](https://console.cloud.google.com)
- **SendGrid**: [app.sendgrid.com/settings/api_keys](https://app.sendgrid.com)
- **Twilio**: [console.twilio.com](https://console.twilio.com)
- **Sentry**: [sentry.io/settings](https://sentry.io)

---

## Post-Deployment

### 1. Custom Domain Setup

**Frontend**:
1. Go to frontend service → "Settings" → "Networking"
2. Click "Add Custom Domain"
3. Add your domain (e.g., `app.yourcompany.com`)
4. Update DNS CNAME record to point to Railway domain

**Backend**:
1. Add API subdomain (e.g., `api.yourcompany.com`)
2. Update all `FRONTEND_URL` and `BACKEND_URL` variables

### 2. SSL/TLS Configuration

Railway provides automatic HTTPS. Verify:
- ✅ HTTPS enforced
- ✅ Valid SSL certificate
- ✅ HTTP → HTTPS redirect

### 3. Webhook Configuration

Update webhook URLs in third-party services:

**Stripe Webhooks**:
- URL: `https://your-backend.railway.app/webhooks/stripe`
- Events: `payment_intent.succeeded`, `payment_intent.failed`

**Synctera Webhooks**:
- URL: `https://your-backend.railway.app/webhooks/synctera`
- Events: KYB status updates, account events

**Samsara Webhooks** (if using):
- URL: `https://your-backend.railway.app/webhooks/samsara`

### 4. Monitoring Setup

**Health Checks**:
- Backend: `https://your-backend.railway.app/health/status`
- Database connectivity
- Redis connectivity

**Sentry Integration**:
- Both frontend and backend send errors to Sentry
- Configure alert rules in Sentry dashboard

### 5. Performance Optimization

**Backend**:
- Worker count: 8 (configurable in railway.json)
- Database pool: 50 connections
- Redis max connections: 50

**Frontend**:
- Build output is in `dist/` folder
- Served with `npx serve`
- Gzip compression enabled

---

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution**:
- Verify `DATABASE_URL` is set correctly
- Check database service is running
- Verify `DB_SSL_MODE=require` is set

#### 2. CORS Errors in Frontend

```
Access to fetch at 'https://backend.railway.app' has been blocked by CORS
```

**Solution**:
- Update `CORS_ORIGINS` in backend to include frontend URL
- Restart backend service
- Clear browser cache

#### 3. Build Failures

**Frontend**:
```
npm ERR! code ELIFECYCLE
```

**Solution**:
- Check `NODE_VERSION` is set to `20.x`
- Verify all dependencies are in `package.json`
- Check build logs for specific error

**Backend**:
```
ERROR: Could not find a version that satisfies the requirement
```

**Solution**:
- Verify Python version in runtime.txt or Nixpacks config
- Check all dependencies are in requirements.txt

#### 4. Environment Variables Not Loading

**Solution**:
- Variables must be set in Railway UI, not in `.env` files
- Restart service after adding variables
- Use `${{SERVICE.VARIABLE}}` syntax for cross-service references

#### 5. High Memory Usage

Backend using > 512MB:

**Solution**:
- Reduce `DB_POOL_SIZE` to 20-30
- Reduce worker count to 4
- Scale up to Railway's Pro plan

---

## Scaling Considerations

### Vertical Scaling (Upgrading Resources)

Railway Plans:
- **Hobby**: $5/month, 512MB RAM, 1GB storage
- **Pro**: $20/month, 8GB RAM, 100GB storage
- **Enterprise**: Custom

Recommended for production: **Pro plan**

### Horizontal Scaling

For high-traffic applications:

1. **Multiple Backend Instances**:
   - Deploy backend to multiple regions
   - Use Railway's autoscaling (Pro plan)

2. **CDN for Frontend**:
   - Use Cloudflare in front of Railway
   - Cache static assets

3. **Database Read Replicas**:
   - Add PostgreSQL read replicas
   - Route read queries to replicas

---

## Maintenance

### Regular Tasks

**Weekly**:
- Review error logs in Sentry
- Check database performance metrics
- Monitor disk usage

**Monthly**:
- Update dependencies (security patches)
- Review and rotate API keys
- Backup database manually (in addition to auto backups)

**Quarterly**:
- Review and optimize database indexes
- Analyze slow queries
- Update documentation

---

## Support

**Railway Support**:
- Documentation: [docs.railway.app](https://docs.railway.app)
- Community: [Discord](https://discord.gg/railway)
- Email: team@railway.app

**FreightOps Support**:
- GitHub Issues: [Frontend](https://github.com/freightops-pro/fopsfrontend/issues) | [Backend](https://github.com/freightops-pro/fopsbackend/issues)

---

## Deployment Checklist

Before going live:

- [ ] All environment variables configured
- [ ] Database migrations run successfully
- [ ] Admin user created
- [ ] Custom domains configured
- [ ] SSL certificates active
- [ ] Webhooks configured in third-party services
- [ ] Sentry monitoring active
- [ ] Health checks passing
- [ ] CORS configured correctly
- [ ] API rate limiting configured
- [ ] Backup strategy in place
- [ ] Security headers configured
- [ ] Load testing completed
- [ ] Documentation updated

---

🚀 **Your FreightOps application is now deployed on Railway!**
