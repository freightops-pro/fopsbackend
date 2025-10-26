# 📧 Email Activation Setup Guide

This guide will help you configure email activation for FreightOps Pro user registration.

## 🚀 Quick Setup

### 1. **Environment Variables**

Add these variables to your `.env` file:

```bash
# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=noreply@freightopspro.com
FROM_NAME=FreightOps Pro
FRONTEND_URL=http://localhost:5173
```

### 2. **Gmail Setup (Recommended)**

1. Launch Gmail and navigate to your account settings.
2. Enable 2-factor authentication if not already enabled.
3. Generate an app password:
   - Go to Google Account settings
   - Navigate to "Security" → "2-Step Verification" → "App passwords"
   - Generate a new app password for "Mail"
   - Use this password as `SMTP_PASSWORD` in your `.env` file

### 3. **Alternative Email Providers**

#### **SendGrid**
```bash
SMTP_SERVER=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=your-sendgrid-api-key
```

#### **Mailgun**
```bash
SMTP_SERVER=smtp.mailgun.org
SMTP_PORT=587
SMTP_USERNAME=your-mailgun-username
SMTP_PASSWORD=your-mailgun-password
```

#### **AWS SES**
```bash
SMTP_SERVER=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USERNAME=your-ses-username
SMTP_PASSWORD=your-ses-password
```

## 🔧 Testing Email Configuration

### 1. **Test Email Service**

Create a test script to verify your email configuration:

```python
# test_email.py
from app.services.email_service import email_service

# Test sending an activation email
success = email_service.send_activation_email(
    email="test@example.com",
    user_name="Test User",
    activation_token="test-token-123"
)

print(f"Email sent successfully: {success}")
```

### 2. **Test Registration Flow**

1. Start your backend server: `python production_main.py`
2. Start your frontend: `npm run dev`
3. Navigate to `/register`
4. Fill out the registration form
5. Check your email inbox for the activation email
6. Click the activation link to activate your account

## 📋 Email Activation Flow

### **Registration Process:**
1. User fills out registration form
2. Backend creates user account (inactive)
3. Activation token generated (24-hour expiry)
4. Activation email sent to user
5. User redirected to login with message to check email

### **Activation Process:**
1. User clicks activation link in email
2. Frontend calls `/api/auth/activate/{token}`
3. Backend verifies token and activates account
4. Welcome email sent to user
5. User redirected to login page

### **Login Process:**
1. User enters credentials + US DOT/MC number
2. Backend verifies email is activated
3. If not activated, user gets error message
4. If activated, user can log in normally

## 🛡️ Security Features

### **Activation Token Security:**
- 32-character random token
- 24-hour expiration
- Single-use (cleared after activation)
- Indexed for fast lookup

### **Email Verification:**
- Prevents unauthorized account creation
- Ensures valid email addresses
- Reduces spam and fake accounts
- Required before any login attempts

### **Rate Limiting:**
- Registration endpoint rate limited
- Resend activation endpoint rate limited
- Prevents abuse and spam

## 🚨 Troubleshooting

### **Common Issues:**

#### **Email Not Sending**
```bash
# Check SMTP credentials
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # NOT your regular password
```

#### **Gmail "Less Secure Apps" Error**
- Enable 2-factor authentication
- Use app password instead of regular password
- Ensure "Less secure app access" is disabled

#### **Activation Link Not Working**
- Check `FRONTEND_URL` in environment variables
- Ensure frontend server is running
- Verify activation route is registered

#### **Token Expired Error**
- Tokens expire after 24 hours
- Use resend activation feature
- Check server time is correct

### **Debug Mode:**

Enable debug logging in your email service:

```python
import logging
logging.getLogger('email_service').setLevel(logging.DEBUG)
```

## 📊 Email Templates

### **Activation Email Features:**
- Professional HTML design
- Mobile-responsive layout
- Clear call-to-action button
- Security warnings about expiry
- Company branding

### **Welcome Email Features:**
- Success confirmation
- Next steps guidance
- Feature highlights
- Support contact information

## 🔄 Production Deployment

### **Environment Variables for Production:**

```bash
# Production Email Settings
SMTP_SERVER=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=your-production-api-key
FROM_EMAIL=noreply@freightopspro.com
FROM_NAME=FreightOps Pro
FRONTEND_URL=https://yourdomain.com
```

### **Email Provider Recommendations:**

1. **SendGrid** - Best for high volume, excellent deliverability
2. **Mailgun** - Good for transactional emails
3. **AWS SES** - Cost-effective for AWS users
4. **Gmail** - Good for development/testing only

## 📈 Monitoring

### **Email Metrics to Track:**
- Activation email delivery rate
- Activation link click rate
- Account activation completion rate
- Failed activation attempts

### **Logging:**
- All email sending attempts logged
- Activation token usage logged
- Failed activations logged
- Security events logged

## 🎯 Next Steps

1. Configure your email provider
2. Test the registration flow
3. Monitor email delivery
4. Set up email analytics
5. Configure production email service

---

**Need Help?** Contact support at support@freightopspro.com

