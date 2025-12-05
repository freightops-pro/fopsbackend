from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Dict, Protocol

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class NotificationResult:
    def __init__(self, success: bool, detail: str = "") -> None:
        self.success = success
        self.detail = detail


class NotificationSender(Protocol):
    async def send(self, recipient: str, subject: str, body: str) -> NotificationResult:
        ...


class EmailSender:
    async def send(self, recipient: str, subject: str, body: str) -> NotificationResult:
        if not settings.smtp_host or not settings.smtp_username or not settings.smtp_password:
            return NotificationResult(False, "SMTP not configured")

        message = EmailMessage()
        message["From"] = settings.smtp_username
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)

        def _send() -> NotificationResult:
            try:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                    server.starttls()
                    server.login(settings.smtp_username, settings.smtp_password)
                    server.send_message(message)
                return NotificationResult(True, "Email delivered via SMTP")
            except Exception as exc:
                logger.exception("Failed to send SMTP email", extra={"recipient": recipient})
                return NotificationResult(False, f"SMTP failure: {exc}")

        return await asyncio.to_thread(_send)


class SMSSender:
    async def send(self, recipient: str, subject: str, body: str) -> NotificationResult:
        if (
            not settings.sms_twilio_account_sid
            or not settings.sms_twilio_auth_token
            or not settings.sms_twilio_from_number
        ):
            return NotificationResult(False, "Twilio credentials not configured")

        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.sms_twilio_account_sid}/Messages.json"
        data = {
            "To": recipient,
            "From": settings.sms_twilio_from_number,
            "Body": f"{subject}\n{body}".strip(),
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                data=data,
                auth=(settings.sms_twilio_account_sid, settings.sms_twilio_auth_token),
                timeout=10,
            )
        if response.status_code in (200, 201):
            return NotificationResult(True, "SMS accepted by Twilio")
        logger.error("Twilio SMS failed", extra={"status": response.status_code, "body": response.text})
        return NotificationResult(False, f"Twilio failure: {response.text}")


class SlackSender:
    async def send(self, recipient: str, subject: str, body: str) -> NotificationResult:
        webhook = settings.slack_webhook_url or recipient
        if not webhook:
            return NotificationResult(False, "Slack webhook not configured")

        payload = {"text": f"*{subject}*\n{body}"}
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook, json=payload, timeout=10)
        if response.status_code in (200, 204):
            return NotificationResult(True, "Slack webhook accepted message")
        logger.error("Slack webhook failed", extra={"status": response.status_code, "body": response.text})
        return NotificationResult(False, f"Slack failure: {response.text}")


class InAppSender:
    async def send(self, recipient: str, subject: str, body: str) -> NotificationResult:
        # Placeholder for future in-app notifications
        logger.info("In-app notification recorded", extra={"recipient": recipient, "subject": subject})
        return NotificationResult(True, "Recorded in notification log")


def build_channel_registry() -> Dict[str, NotificationSender]:
    return {
        "email": EmailSender(),
        "sms": SMSSender(),
        "slack": SlackSender(),
        "in_app": InAppSender(),
    }