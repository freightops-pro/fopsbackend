"""
Email service for sending driver invitations and notifications.

Supports multiple email providers:
1. SendGrid (primary) - Set SENDGRID_API_KEY in environment
2. AWS SES (fallback) - Set AWS_SES_REGION and AWS credentials
3. Console logging (development) - When no provider is configured
"""

import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Base URL for invitation links
APP_BASE_URL = os.getenv("APP_BASE_URL", "https://freightopspro.com")


class EmailService:
    """Service for sending emails with multi-provider support."""

    def __init__(self):
        self.sendgrid_key = os.getenv("SENDGRID_API_KEY")
        self.ses_region = os.getenv("AWS_SES_REGION")
        self.from_email = os.getenv("EMAIL_FROM_ADDRESS", "noreply@freightops.com")
        self.from_name = os.getenv("EMAIL_FROM_NAME", "FreightOps")

    def _get_provider(self) -> str:
        """Determine which email provider to use."""
        if self.sendgrid_key:
            return "sendgrid"
        if self.ses_region and os.getenv("AWS_ACCESS_KEY_ID"):
            return "ses"
        return "console"

    @staticmethod
    def send_driver_invitation(
        email: str,
        first_name: str,
        last_name: str,
        temporary_password: str,
        company_name: Optional[str] = None,
    ) -> bool:
        """
        Send an invitation email to a new driver with their temporary credentials.

        Args:
            email: Driver's email address
            first_name: Driver's first name
            last_name: Driver's last name
            temporary_password: Temporary password for first login
            company_name: Optional company name

        Returns:
            bool: True if email was sent successfully
        """
        service = EmailService()
        company = company_name or "FreightOps"

        subject = f"Welcome to {company} - Your Account is Ready"
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #2563eb; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 30px; background-color: #f9fafb; }}
        .credentials {{ background-color: #fff; border: 1px solid #e5e7eb; padding: 20px; margin: 20px 0; border-radius: 8px; }}
        .credential-label {{ color: #6b7280; font-size: 12px; text-transform: uppercase; }}
        .credential-value {{ font-size: 16px; font-weight: bold; color: #111827; }}
        .warning {{ background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px; margin: 20px 0; }}
        .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Welcome to {company}!</h1>
        </div>
        <div class="content">
            <p>Hi {first_name} {last_name},</p>
            <p>Your driver account has been created. You can now access the FreightOps platform to view loads, update delivery status, and more.</p>

            <div class="credentials">
                <p class="credential-label">Email Address</p>
                <p class="credential-value">{email}</p>

                <p class="credential-label" style="margin-top: 15px;">Temporary Password</p>
                <p class="credential-value">{temporary_password}</p>
            </div>

            <div class="warning">
                <strong>Important:</strong> You will be required to change your password upon first login for security purposes.
            </div>

            <p>If you have any questions, please contact your dispatcher or fleet manager.</p>

            <p>Best regards,<br>The {company} Team</p>
        </div>
        <div class="footer">
            <p>This email was sent by {company} via FreightOps TMS</p>
        </div>
    </div>
</body>
</html>
"""

        text_content = f"""
Welcome to {company}!

Hi {first_name} {last_name},

Your driver account has been created.

LOGIN CREDENTIALS:
-------------------
Email: {email}
Temporary Password: {temporary_password}

IMPORTANT: You will be required to change your password upon first login.

If you have any questions, please contact your dispatcher.

Best regards,
The {company} Team
"""

        return service._send_email(
            to_email=email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )

    @staticmethod
    def send_password_reset(email: str, reset_link: str) -> bool:
        """
        Send a password reset email.

        Args:
            email: User's email address
            reset_link: Password reset link

        Returns:
            bool: True if email was sent successfully
        """
        service = EmailService()

        subject = "Password Reset Request - FreightOps"
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #2563eb; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 30px; background-color: #f9fafb; }}
        .button {{ display: inline-block; background-color: #2563eb; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
        .warning {{ background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px; margin: 20px 0; }}
        .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Password Reset Request</h1>
        </div>
        <div class="content">
            <p>Hello,</p>
            <p>We received a request to reset your password for your FreightOps account.</p>

            <p style="text-align: center;">
                <a href="{reset_link}" class="button">Reset My Password</a>
            </p>

            <div class="warning">
                <strong>Note:</strong> This link will expire in 1 hour. If you didn't request this password reset, please ignore this email or contact support.
            </div>

            <p>If the button doesn't work, copy and paste this link into your browser:</p>
            <p style="word-break: break-all; color: #2563eb;">{reset_link}</p>
        </div>
        <div class="footer">
            <p>FreightOps TMS - Secure Transportation Management</p>
        </div>
    </div>
</body>
</html>
"""

        text_content = f"""
Password Reset Request

Hello,

We received a request to reset your password for your FreightOps account.

Click here to reset your password: {reset_link}

This link will expire in 1 hour.

If you didn't request this password reset, please ignore this email.

FreightOps TMS
"""

        return service._send_email(
            to_email=email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )

    @staticmethod
    def send_user_invitation(
        email: str,
        token: str,
        company_name: str,
        inviter_name: str,
        expires_at: datetime,
        message: Optional[str] = None,
    ) -> bool:
        """
        Send an invitation email to a new team member.

        Args:
            email: Invitee's email address
            token: Secure invitation token
            company_name: Name of the company
            inviter_name: Name of the person who sent the invite
            expires_at: When the invitation expires
            message: Optional personal message from inviter

        Returns:
            bool: True if email was sent successfully
        """
        service = EmailService()

        invite_link = f"{APP_BASE_URL}/accept-invitation?token={token}"
        expires_formatted = expires_at.strftime("%B %d, %Y at %I:%M %p UTC")

        message_section = ""
        message_text = ""
        if message:
            message_section = f"""
            <div style="background-color: #f0f9ff; border-left: 4px solid #2563eb; padding: 12px; margin: 20px 0;">
                <p style="margin: 0; font-style: italic;">"{message}"</p>
                <p style="margin: 5px 0 0 0; font-size: 12px; color: #6b7280;">— {inviter_name}</p>
            </div>
            """
            message_text = f'\nPersonal message from {inviter_name}:\n"{message}"\n'

        subject = f"You're invited to join {company_name} on FreightOps"
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #2563eb; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ padding: 30px; background-color: #f9fafb; }}
        .button {{ display: inline-block; background-color: #2563eb; color: white; padding: 14px 40px; text-decoration: none; border-radius: 6px; margin: 20px 0; font-weight: bold; }}
        .button:hover {{ background-color: #1d4ed8; }}
        .info {{ background-color: #fff; border: 1px solid #e5e7eb; padding: 15px; margin: 20px 0; border-radius: 8px; }}
        .warning {{ background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px; margin: 20px 0; }}
        .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>You're Invited! 🎉</h1>
        </div>
        <div class="content">
            <p>Hello,</p>
            <p><strong>{inviter_name}</strong> has invited you to join <strong>{company_name}</strong> on FreightOps, the modern transportation management platform.</p>

            {message_section}

            <div style="text-align: center;">
                <a href="{invite_link}" class="button">Accept Invitation</a>
            </div>

            <div class="info">
                <p style="margin: 0;"><strong>What happens next?</strong></p>
                <ul style="margin: 10px 0; padding-left: 20px;">
                    <li>Click the button above to accept your invitation</li>
                    <li>Create your password and complete your profile</li>
                    <li>Start using FreightOps with your team!</li>
                </ul>
            </div>

            <div class="warning">
                <strong>Note:</strong> This invitation expires on {expires_formatted}. If the button doesn't work, copy and paste this link into your browser:
                <p style="word-break: break-all; color: #2563eb; margin: 10px 0 0 0;">{invite_link}</p>
            </div>
        </div>
        <div class="footer">
            <p>FreightOps TMS - Modern Transportation Management</p>
            <p style="font-size: 11px;">If you didn't expect this invitation, you can safely ignore this email.</p>
        </div>
    </div>
</body>
</html>
"""

        text_content = f"""
You're Invited to Join {company_name}!

Hello,

{inviter_name} has invited you to join {company_name} on FreightOps.
{message_text}
ACCEPT YOUR INVITATION:
-----------------------
Click here to accept: {invite_link}

WHAT HAPPENS NEXT:
- Click the link above to accept your invitation
- Create your password and complete your profile
- Start using FreightOps with your team!

This invitation expires on {expires_formatted}.

If you didn't expect this invitation, you can safely ignore this email.

FreightOps TMS
"""

        return service._send_email(
            to_email=email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )

    def _send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> bool:
        """Send email using the configured provider."""
        provider = self._get_provider()

        if provider == "sendgrid":
            return self._send_via_sendgrid(to_email, subject, html_content, text_content)
        elif provider == "ses":
            return self._send_via_ses(to_email, subject, html_content, text_content)
        else:
            return self._send_via_console(to_email, subject, text_content)

    def _send_via_sendgrid(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> bool:
        """Send email via SendGrid."""
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To, Content

            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject,
            )
            message.add_content(Content("text/plain", text_content))
            message.add_content(Content("text/html", html_content))

            sg = SendGridAPIClient(self.sendgrid_key)
            response = sg.send(message)

            if response.status_code in (200, 201, 202):
                logger.info(f"Email sent via SendGrid to {to_email}")
                return True
            else:
                logger.error(f"SendGrid error: {response.status_code}")
                return False

        except ImportError:
            logger.error("SendGrid package not installed. Run: pip install sendgrid")
            return self._send_via_console(to_email, subject, text_content)
        except Exception as e:
            logger.error(f"SendGrid error: {e}")
            return False

    def _send_via_ses(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str,
    ) -> bool:
        """Send email via AWS SES."""
        try:
            import boto3
            from botocore.exceptions import ClientError

            client = boto3.client("ses", region_name=self.ses_region)

            response = client.send_email(
                Source=f"{self.from_name} <{self.from_email}>",
                Destination={"ToAddresses": [to_email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": text_content, "Charset": "UTF-8"},
                        "Html": {"Data": html_content, "Charset": "UTF-8"},
                    },
                },
            )

            logger.info(f"Email sent via SES to {to_email}, MessageId: {response['MessageId']}")
            return True

        except ImportError:
            logger.error("boto3 package not installed. Run: pip install boto3")
            return self._send_via_console(to_email, subject, text_content)
        except Exception as e:
            logger.error(f"SES error: {e}")
            return False

    def _send_via_console(
        self,
        to_email: str,
        subject: str,
        text_content: str,
    ) -> bool:
        """Log email to console (development mode)."""
        print("\n" + "=" * 80)
        print("EMAIL (Console Mode - No provider configured)")
        print("=" * 80)
        print(f"To: {to_email}")
        print(f"From: {self.from_name} <{self.from_email}>")
        print(f"Subject: {subject}")
        print("-" * 80)
        print(text_content)
        print("-" * 80 + "\n")

        logger.warning(f"Email logged to console (no provider configured): {to_email}")
        return True
