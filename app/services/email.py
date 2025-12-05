"""
Email service for sending driver invitations and notifications.

To integrate with an email provider (SendGrid, AWS SES, Resend, etc.):
1. Install the provider's SDK: `poetry add sendgrid` or `poetry add resend`
2. Add API keys to your .env file
3. Replace the print statements below with actual email sending logic
"""

from typing import Optional


class EmailService:
    """Service for sending emails."""

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
        # TODO: Replace with actual email sending logic
        print("\n" + "="*80)
        print("📧 DRIVER INVITATION EMAIL")
        print("="*80)
        print(f"To: {email}")
        print(f"Subject: Welcome to {company_name or 'FreightOps'} - Your Account is Ready")
        print("\n" + "-"*80)
        print(f"""
Hi {first_name} {last_name},

Welcome to {company_name or 'FreightOps'}! Your driver account has been created.

LOGIN CREDENTIALS:
-------------------
Email: {email}
Temporary Password: {temporary_password}

IMPORTANT: You will be required to change your password upon first login.

Login URL: [Your App URL Here]

If you have any questions, please contact your dispatcher.

Best regards,
{company_name or 'FreightOps'} Team
        """)
        print("-"*80 + "\n")

        # Example: SendGrid integration
        # from sendgrid import SendGridAPIClient
        # from sendgrid.helpers.mail import Mail
        #
        # message = Mail(
        #     from_email='noreply@yourcompany.com',
        #     to_emails=email,
        #     subject=f'Welcome to {company_name or "FreightOps"} - Your Account is Ready',
        #     html_content=f"""
        #         <h2>Hi {first_name} {last_name},</h2>
        #         <p>Welcome to {company_name or 'FreightOps'}!</p>
        #         ... (full HTML email here)
        #     """
        # )
        #
        # try:
        #     sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        #     response = sg.send(message)
        #     return response.status_code == 202
        # except Exception as e:
        #     print(f"Error sending email: {e}")
        #     return False

        # For now, just return True (email "sent" via console)
        return True

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
        # TODO: Implement password reset email
        print(f"\n📧 Password Reset Email to: {email}")
        print(f"Reset Link: {reset_link}\n")
        return True
