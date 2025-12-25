"""HQ Email service for CRM email functionality."""

import logging
import smtplib
import uuid
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Tuple

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hq_lead import HQLead
from app.models.hq_lead_activity import (
    HQLeadActivity, HQEmailTemplate, HQEmailConfig,
    ActivityType, FollowUpStatus
)

logger = logging.getLogger(__name__)


class HQEmailService:
    """
    Service for sending emails from the CRM and tracking email activities.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Email Sending
    # =========================================================================

    async def send_email(
        self,
        lead_id: str,
        to_email: str,
        subject: str,
        body: str,
        sent_by_id: str,
        cc: Optional[str] = None,
        template_id: Optional[str] = None,
    ) -> Tuple[Optional[HQLeadActivity], Optional[str]]:
        """
        Send an email to a lead and log the activity.

        Args:
            lead_id: Lead to associate the email with
            to_email: Recipient email address
            subject: Email subject
            body: Email body (HTML supported)
            sent_by_id: ID of the employee sending the email
            cc: Optional CC recipients (comma-separated)
            template_id: Optional template used

        Returns:
            Tuple of (activity record, error message if failed)
        """
        # Get the default email config
        config = await self._get_default_email_config()
        if not config:
            return None, "No email configuration found. Please configure email settings."

        # Generate unique message ID for threading
        message_id = f"<{uuid.uuid4()}@freightops.com>"
        thread_id = f"lead-{lead_id}-{uuid.uuid4().hex[:8]}"

        # Get lead info for the activity record
        result = await self.db.execute(
            select(HQLead).where(HQLead.id == lead_id)
        )
        lead = result.scalar_one_or_none()
        if not lead:
            return None, "Lead not found"

        # Try to send the email
        try:
            await self._send_via_provider(
                config=config,
                to_email=to_email,
                subject=subject,
                body=body,
                cc=cc,
                message_id=message_id,
            )
            email_status = "sent"
        except Exception as e:
            logger.exception(f"Failed to send email: {e}")
            email_status = "failed"
            # Still log the attempt

        # Create activity record
        activity = HQLeadActivity(
            id=str(uuid.uuid4()),
            lead_id=lead_id,
            activity_type=ActivityType.EMAIL_SENT,
            subject=subject,
            content=body,
            email_from=config.from_email,
            email_to=to_email,
            email_cc=cc,
            email_message_id=message_id,
            email_thread_id=thread_id,
            email_status=email_status,
            created_by_id=sent_by_id,
            metadata={
                "template_id": template_id,
                "from_name": config.from_name,
            }
        )

        self.db.add(activity)

        # Update lead's last contacted timestamp
        lead.last_contacted_at = datetime.utcnow()

        # Increment template usage if used
        if template_id:
            await self._increment_template_usage(template_id)

        await self.db.commit()
        await self.db.refresh(activity)

        if email_status == "failed":
            return activity, "Email failed to send but was logged"

        return activity, None

    async def _send_via_provider(
        self,
        config: HQEmailConfig,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        message_id: Optional[str] = None,
    ):
        """Send email using the configured provider."""
        provider = config.provider.lower()

        if provider == "smtp":
            await self._send_smtp(config, to_email, subject, body, cc, message_id)
        elif provider == "sendgrid":
            await self._send_sendgrid(config, to_email, subject, body, cc, message_id)
        else:
            raise ValueError(f"Unsupported email provider: {provider}")

    async def _send_smtp(
        self,
        config: HQEmailConfig,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        message_id: Optional[str] = None,
    ):
        """Send email via SMTP."""
        smtp_config = config.config

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{config.from_name} <{config.from_email}>" if config.from_name else config.from_email
        msg["To"] = to_email
        if cc:
            msg["Cc"] = cc
        if config.reply_to:
            msg["Reply-To"] = config.reply_to
        if message_id:
            msg["Message-ID"] = message_id

        # Add HTML body
        msg.attach(MIMEText(body, "html"))

        # Send
        with smtplib.SMTP(smtp_config["host"], smtp_config.get("port", 587)) as server:
            if smtp_config.get("use_tls", True):
                server.starttls()
            if smtp_config.get("username") and smtp_config.get("password"):
                server.login(smtp_config["username"], smtp_config["password"])

            recipients = [to_email]
            if cc:
                recipients.extend([e.strip() for e in cc.split(",")])

            server.sendmail(config.from_email, recipients, msg.as_string())

    async def _send_sendgrid(
        self,
        config: HQEmailConfig,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        message_id: Optional[str] = None,
    ):
        """Send email via SendGrid API."""
        import httpx

        api_key = config.config.get("api_key")
        if not api_key:
            raise ValueError("SendGrid API key not configured")

        payload = {
            "personalizations": [{
                "to": [{"email": to_email}],
            }],
            "from": {
                "email": config.from_email,
                "name": config.from_name or "FreightOps",
            },
            "subject": subject,
            "content": [{"type": "text/html", "value": body}],
        }

        if cc:
            payload["personalizations"][0]["cc"] = [
                {"email": e.strip()} for e in cc.split(",")
            ]

        if config.reply_to:
            payload["reply_to"] = {"email": config.reply_to}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()

    async def _get_default_email_config(self) -> Optional[HQEmailConfig]:
        """Get the default email configuration."""
        result = await self.db.execute(
            select(HQEmailConfig).where(
                and_(
                    HQEmailConfig.is_default == True,
                    HQEmailConfig.is_active == True,
                )
            )
        )
        return result.scalar_one_or_none()

    # =========================================================================
    # Email Templates
    # =========================================================================

    async def get_templates(
        self,
        category: Optional[str] = None,
        include_personal: bool = True,
        user_id: Optional[str] = None,
    ) -> List[HQEmailTemplate]:
        """Get available email templates."""
        query = select(HQEmailTemplate).where(HQEmailTemplate.is_active == True)

        if category:
            query = query.where(HQEmailTemplate.category == category)

        if include_personal and user_id:
            query = query.where(
                (HQEmailTemplate.is_global == True) |
                (HQEmailTemplate.created_by_id == user_id)
            )
        else:
            query = query.where(HQEmailTemplate.is_global == True)

        query = query.order_by(HQEmailTemplate.name)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create_template(
        self,
        name: str,
        subject: str,
        body: str,
        created_by_id: str,
        category: Optional[str] = None,
        is_global: bool = False,
        variables: Optional[List[str]] = None,
    ) -> HQEmailTemplate:
        """Create a new email template."""
        template = HQEmailTemplate(
            id=str(uuid.uuid4()),
            name=name,
            subject=subject,
            body=body,
            category=category,
            is_global=is_global,
            created_by_id=created_by_id,
            variables=variables or [],
        )

        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)

        return template

    async def render_template(
        self,
        template_id: str,
        lead_id: str,
        custom_vars: Optional[dict] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Render an email template with lead data.

        Returns:
            Tuple of (subject, body, error)
        """
        # Get template
        result = await self.db.execute(
            select(HQEmailTemplate).where(HQEmailTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        if not template:
            return None, None, "Template not found"

        # Get lead
        result = await self.db.execute(
            select(HQLead).where(HQLead.id == lead_id)
        )
        lead = result.scalar_one_or_none()
        if not lead:
            return None, None, "Lead not found"

        # Build variable context
        context = {
            "company_name": lead.company_name or "",
            "contact_name": lead.contact_name or "",
            "contact_first_name": (lead.contact_name or "").split()[0] if lead.contact_name else "",
            "contact_email": lead.contact_email or "",
            "fleet_size": lead.estimated_trucks or "",
            "estimated_mrr": f"${lead.estimated_mrr:.2f}" if lead.estimated_mrr else "",
        }

        # Add custom variables
        if custom_vars:
            context.update(custom_vars)

        # Render template
        try:
            subject = template.subject
            body = template.body

            for key, value in context.items():
                subject = subject.replace(f"{{{{{key}}}}}", str(value))
                body = body.replace(f"{{{{{key}}}}}", str(value))

            return subject, body, None

        except Exception as e:
            return None, None, f"Template rendering error: {str(e)}"

    async def _increment_template_usage(self, template_id: str):
        """Increment the usage count of a template."""
        result = await self.db.execute(
            select(HQEmailTemplate).where(HQEmailTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        if template:
            current = int(template.times_used or "0")
            template.times_used = str(current + 1)

    # =========================================================================
    # Email Configuration
    # =========================================================================

    async def create_email_config(
        self,
        name: str,
        provider: str,
        config: dict,
        from_email: str,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        is_default: bool = False,
    ) -> HQEmailConfig:
        """Create a new email configuration."""
        # If this is default, unset other defaults
        if is_default:
            result = await self.db.execute(
                select(HQEmailConfig).where(HQEmailConfig.is_default == True)
            )
            for existing in result.scalars().all():
                existing.is_default = False

        email_config = HQEmailConfig(
            id=str(uuid.uuid4()),
            name=name,
            provider=provider,
            config=config,
            from_email=from_email,
            from_name=from_name,
            reply_to=reply_to,
            is_default=is_default,
        )

        self.db.add(email_config)
        await self.db.commit()
        await self.db.refresh(email_config)

        return email_config

    async def get_email_configs(self) -> List[HQEmailConfig]:
        """Get all email configurations."""
        result = await self.db.execute(
            select(HQEmailConfig).order_by(HQEmailConfig.name)
        )
        return list(result.scalars().all())
