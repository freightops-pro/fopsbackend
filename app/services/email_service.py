"""
Email Service for FreightOps Pro
Handles sending activation emails, notifications, etc.
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import secrets
import string
from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_server = getattr(settings, 'SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = getattr(settings, 'SMTP_PORT', 587)
        self.smtp_username = getattr(settings, 'SMTP_USERNAME', None)
        self.smtp_password = getattr(settings, 'SMTP_PASSWORD', None)
        self.from_email = getattr(settings, 'FROM_EMAIL', 'noreply@freightopspro.com')
        self.from_name = getattr(settings, 'FROM_NAME', 'FreightOps Pro')
        
    def generate_activation_token(self, length: int = 32) -> str:
        """Generate a secure activation token"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def create_activation_email_html(self, user_name: str, activation_link: str) -> str:
        """Create HTML email template for account activation"""
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Activate Your FreightOps Pro Account</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f8fafc;
                }}
                .container {{
                    background: white;
                    border-radius: 8px;
                    padding: 40px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .logo {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #1e40af;
                    margin-bottom: 10px;
                }}
                .title {{
                    font-size: 28px;
                    font-weight: bold;
                    color: #1f2937;
                    margin-bottom: 20px;
                }}
                .content {{
                    margin-bottom: 30px;
                }}
                .button {{
                    display: inline-block;
                    background: linear-gradient(135deg, #1e40af, #3b82f6);
                    color: white;
                    text-decoration: none;
                    padding: 16px 32px;
                    border-radius: 8px;
                    font-weight: bold;
                    text-align: center;
                    margin: 20px 0;
                    transition: transform 0.2s;
                }}
                .button:hover {{
                    transform: translateY(-2px);
                }}
                .footer {{
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #e5e7eb;
                    font-size: 14px;
                    color: #6b7280;
                    text-align: center;
                }}
                .warning {{
                    background: #fef3c7;
                    border: 1px solid #f59e0b;
                    border-radius: 6px;
                    padding: 15px;
                    margin: 20px 0;
                    color: #92400e;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">FreightOps Pro</div>
                    <h1 class="title">Activate Your Account</h1>
                </div>
                
                <div class="content">
                    <p>Hi {user_name},</p>
                    
                    <p>Welcome to FreightOps Pro! Thank you for registering with us. To complete your account setup and start managing your transportation operations, please activate your account by clicking the button below:</p>
                    
                    <div style="text-align: center;">
                        <a href="{activation_link}" class="button">Activate Account</a>
                    </div>
                    
                    <p>If the button doesn't work, you can copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; background: #f3f4f6; padding: 10px; border-radius: 4px; font-family: monospace;">
                        {activation_link}
                    </p>
                    
                    <div class="warning">
                        <strong>Important:</strong> This activation link will expire in 24 hours. If you don't activate your account within this time, you'll need to register again.
                    </div>
                    
                    <p>Once activated, you'll have access to:</p>
                    <ul>
                        <li>Fleet management and tracking</li>
                        <li>Load dispatch and scheduling</li>
                        <li>Financial management and reporting</li>
                        <li>Driver and equipment management</li>
                        <li>Compliance monitoring</li>
                    </ul>
                    
                    <p>If you didn't create an account with FreightOps Pro, please ignore this email.</p>
                </div>
                
                <div class="footer">
                    <p>This email was sent by FreightOps Pro<br>
                    If you have any questions, please contact our support team.</p>
                    <p style="margin-top: 20px;">
                        <a href="mailto:support@freightopspro.com" style="color: #3b82f6;">support@freightopspro.com</a>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def send_activation_email(self, email: str, user_name: str, activation_token: str) -> bool:
        """Send activation email to user"""
        try:
            if not self.smtp_username or not self.smtp_password:
                logger.warning("SMTP credentials not configured. Email not sent.")
                return False
            
            # Create activation link
            activation_link = f"{settings.FRONTEND_URL}/activate?token={activation_token}"
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = 'Activate Your FreightOps Pro Account'
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = email
            
            # Create HTML content
            html_content = self.create_activation_email_html(user_name, activation_link)
            
            # Attach HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Activation email sent successfully to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send activation email to {email}: {str(e)}")
            return False
    
    def send_welcome_email(self, email: str, user_name: str, company_name: str) -> bool:
        """Send welcome email after successful activation"""
        try:
            if not self.smtp_username or not self.smtp_password:
                logger.warning("SMTP credentials not configured. Email not sent.")
                return False
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = 'Welcome to FreightOps Pro - Your Account is Active!'
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = email
            
            # Create HTML content
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Welcome to FreightOps Pro</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                        background-color: #f8fafc;
                    }}
                    .container {{
                        background: white;
                        border-radius: 8px;
                        padding: 40px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    }}
                    .header {{
                        text-align: center;
                        margin-bottom: 30px;
                    }}
                    .logo {{
                        font-size: 24px;
                        font-weight: bold;
                        color: #1e40af;
                        margin-bottom: 10px;
                    }}
                    .title {{
                        font-size: 28px;
                        font-weight: bold;
                        color: #1f2937;
                        margin-bottom: 20px;
                    }}
                    .success {{
                        background: #d1fae5;
                        border: 1px solid #10b981;
                        border-radius: 6px;
                        padding: 15px;
                        margin: 20px 0;
                        color: #065f46;
                    }}
                    .button {{
                        display: inline-block;
                        background: linear-gradient(135deg, #1e40af, #3b82f6);
                        color: white;
                        text-decoration: none;
                        padding: 16px 32px;
                        border-radius: 8px;
                        font-weight: bold;
                        text-align: center;
                        margin: 20px 0;
                    }}
                    .footer {{
                        margin-top: 40px;
                        padding-top: 20px;
                        border-top: 1px solid #e5e7eb;
                        font-size: 14px;
                        color: #6b7280;
                        text-align: center;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <div class="logo">FreightOps Pro</div>
                        <h1 class="title">Welcome Aboard!</h1>
                    </div>
                    
                    <div class="success">
                        <strong>Account Activated Successfully!</strong><br>
                        Your FreightOps Pro account is now active and ready to use.
                    </div>
                    
                    <p>Hi {user_name},</p>
                    
                    <p>Congratulations! Your account for <strong>{company_name}</strong> has been successfully activated. You can now access all the powerful features of FreightOps Pro.</p>
                    
                    <div style="text-align: center;">
                        <a href="{settings.FRONTEND_URL}/login" class="button">Sign In to Your Account</a>
                    </div>
                    
                    <p>Here's what you can do next:</p>
                    <ul>
                        <li>Set up your fleet and equipment</li>
                        <li>Add drivers and manage schedules</li>
                        <li>Create and dispatch loads</li>
                        <li>Track shipments in real-time</li>
                        <li>Generate financial reports</li>
                    </ul>
                    
                    <p>Need help getting started? Our support team is here to assist you every step of the way.</p>
                </div>
                
                <div class="footer">
                    <p>Thank you for choosing FreightOps Pro!<br>
                    <a href="mailto:support@freightopspro.com" style="color: #3b82f6;">support@freightopspro.com</a></p>
                </div>
            </body>
            </html>
            """
            
            # Attach HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Welcome email sent successfully to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send welcome email to {email}: {str(e)}")
            return False

# Global email service instance
email_service = EmailService()

