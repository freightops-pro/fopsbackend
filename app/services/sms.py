"""
Email-to-SMS Service
Sends SMS messages via email gateways - completely free!

This service uses carrier email-to-SMS gateways to send text messages
without Twilio or other paid SMS services.
"""

import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.services.notifications import EmailSender, NotificationResult

logger = logging.getLogger(__name__)


# Carrier email gateways for email-to-SMS conversion
CARRIER_GATEWAYS = {
    "verizon": "@vtext.com",
    "att": "@txt.att.net",
    "tmobile": "@tmomail.net",
    "sprint": "@messaging.sprintpcs.com",
    "us_cellular": "@email.uscc.net",
    "boost": "@sms.myboostmobile.com",
    "cricket": "@sms.cricketwireless.net",
    "metro_pcs": "@mymetropcs.com",
}


def clean_phone_number(phone: str) -> str:
    """
    Remove all formatting from phone number.

    Examples:
        (555) 123-4567 → 5551234567
        555-123-4567 → 5551234567
        +1 555 123 4567 → 15551234567

    Args:
        phone: Phone number with any formatting

    Returns:
        str: Digits-only phone number
    """
    return ''.join(filter(str.isdigit, phone))


async def send_sms_via_email(
    phone: str,
    carrier: str,
    message: str,
    subject: str = "",
) -> NotificationResult:
    """
    Send SMS via email-to-SMS gateway.

    Args:
        phone: Phone number (any format)
        carrier: Carrier name (verizon, att, tmobile, etc.)
        message: SMS message (will be truncated to 160 chars)
        subject: Email subject (usually left empty for SMS)

    Returns:
        NotificationResult: Success status and details

    Raises:
        ValueError: If carrier is invalid or phone number is malformed
    """
    # Validate carrier
    gateway = CARRIER_GATEWAYS.get(carrier.lower())
    if not gateway:
        raise ValueError(
            f"Unknown carrier: {carrier}. "
            f"Valid carriers: {list(CARRIER_GATEWAYS.keys())}"
        )

    # Clean phone number
    clean_phone = clean_phone_number(phone)

    if len(clean_phone) < 10:
        raise ValueError(f"Invalid phone number: {phone}")

    # Truncate message to 160 characters (SMS limit)
    sms_message = message[:160]

    # Construct SMS email address
    sms_email = f"{clean_phone}{gateway}"

    logger.info(
        f"Sending SMS to {phone} ({carrier}) via email gateway {sms_email}",
        extra={"phone": phone, "carrier": carrier, "gateway": sms_email}
    )

    try:
        # Send email (which becomes SMS)
        email_sender = EmailSender()
        result = await email_sender.send(
            recipient=sms_email,
            subject=subject,  # Usually empty - subject gets prepended to SMS
            body=sms_message
        )

        if result.success:
            logger.info(
                f"SMS sent successfully to {phone}",
                extra={"phone": phone, "carrier": carrier}
            )
        else:
            logger.error(
                f"Failed to send SMS to {phone}: {result.detail}",
                extra={"phone": phone, "carrier": carrier, "error": result.detail}
            )

        return result

    except Exception as e:
        logger.exception(
            f"Unexpected error sending SMS to {phone}",
            extra={"phone": phone, "carrier": carrier}
        )
        return NotificationResult(False, f"Failed to send SMS: {str(e)}")


async def send_driver_notification(
    driver_id: str,
    message: str,
    db: Session,
    email_subject: str = "FreightOps Notification"
) -> dict:
    """
    Send notification to driver via BOTH email and SMS.

    Args:
        driver_id: Driver ID
        message: Full notification message
        db: Database session
        email_subject: Subject line for email notification

    Returns:
        dict: Status of email and SMS delivery with driver info
    """
    from app.models.driver import Driver
    from app.services.notifications import EmailSender

    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise ValueError(f"Driver not found: {driver_id}")

    result = {
        "email_sent": False,
        "sms_sent": False,
        "driver_name": f"{driver.first_name} {driver.last_name}",
        "driver_id": driver_id
    }

    # Send full email notification
    if driver.email:
        try:
            email_sender = EmailSender()
            email_result = await email_sender.send(
                recipient=driver.email,
                subject=email_subject,
                body=message
            )
            result["email_sent"] = email_result.success
            if email_result.success:
                logger.info(
                    f"Email sent to driver {driver_id}",
                    extra={"driver_id": driver_id, "email": driver.email}
                )
            else:
                logger.error(
                    f"Failed to send email to driver {driver_id}: {email_result.detail}",
                    extra={"driver_id": driver_id, "email": driver.email}
                )
        except Exception as e:
            logger.exception(
                f"Error sending email to driver {driver_id}",
                extra={"driver_id": driver_id}
            )

    # Send SMS if carrier is known
    if driver.phone and driver.phone_carrier:
        try:
            # Truncate message for SMS (160 char limit)
            sms_message = message[:160]
            sms_result = await send_sms_via_email(
                phone=driver.phone,
                carrier=driver.phone_carrier,
                message=sms_message
            )
            result["sms_sent"] = sms_result.success
            if sms_result.success:
                logger.info(
                    f"SMS sent to driver {driver_id}",
                    extra={"driver_id": driver_id, "phone": driver.phone}
                )
            else:
                logger.error(
                    f"Failed to send SMS to driver {driver_id}: {sms_result.detail}",
                    extra={"driver_id": driver_id, "phone": driver.phone}
                )
        except Exception as e:
            logger.exception(
                f"Error sending SMS to driver {driver_id}",
                extra={"driver_id": driver_id}
            )
    else:
        if not driver.phone:
            logger.info(
                f"No phone number for driver {driver_id}, skipping SMS",
                extra={"driver_id": driver_id}
            )
        if not driver.phone_carrier:
            logger.info(
                f"No phone carrier for driver {driver_id}, skipping SMS",
                extra={"driver_id": driver_id}
            )

    return result
