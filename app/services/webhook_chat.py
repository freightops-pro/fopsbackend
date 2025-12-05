"""
Service for integrating webhook events with the chat/collaboration system.
Handles automatic message creation from webhook events for driver communication.
"""

from __future__ import annotations

import logging
import uuid
from typing import Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collaboration import Channel, Message
from app.models.driver import Driver
from app.models.user import User
from app.websocket.hub import channel_hub

logger = logging.getLogger(__name__)


class WebhookChatService:
    """Service to create chat messages from webhook events."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create_driver_channel(
        self, company_id: str, driver_id: str, driver_name: Optional[str] = None
    ) -> Channel:
        """
        Get or create a channel for driver communication.
        Channel name format: "Driver: {First Name} {Last Name}"
        """
        # Try to find existing driver channel
        # Driver channels are prefixed with "driver:" in the name
        result = await self.db.execute(
            select(Channel).where(
                Channel.company_id == company_id,
                Channel.name.like(f"driver:{driver_id}%")
            )
        )
        channel = result.scalar_one_or_none()

        if not channel:
            # Get driver info if not provided
            if not driver_name:
                driver_result = await self.db.execute(
                    select(Driver).where(Driver.id == driver_id, Driver.company_id == company_id)
                )
                driver = driver_result.scalar_one_or_none()
                if driver:
                    driver_name = f"{driver.first_name} {driver.last_name}"
                else:
                    driver_name = f"Driver {driver_id[:8]}"

            # Create new driver channel
            channel = Channel(
                id=str(uuid.uuid4()),
                company_id=company_id,
                name=f"driver:{driver_id}",
                description=f"Direct communication channel for {driver_name}",
            )
            self.db.add(channel)
            await self.db.commit()
            await self.db.refresh(channel)
            logger.info(f"Created driver channel: {channel.id} for driver {driver_id}")

        return channel

    async def create_system_message(
        self,
        channel_id: str,
        message_body: str,
        system_user_id: Optional[str] = None,
    ) -> Message:
        """
        Create a system message in a channel.
        If system_user_id is not provided, creates a message with a special system author.
        """
        # Get or create system user for the company
        if not system_user_id:
            # Find a system/admin user in the company
            channel_result = await self.db.execute(
                select(Channel).where(Channel.id == channel_id)
            )
            channel = channel_result.scalar_one_or_none()
            if channel:
                # Get first admin user from the company
                user_result = await self.db.execute(
                    select(User).where(
                        User.company_id == channel.company_id,
                        User.role.in_(["TENANT_ADMIN", "ADMIN"])
                    ).limit(1)
                )
                system_user = user_result.scalar_one_or_none()
                if system_user:
                    system_user_id = system_user.id
                else:
                    # Fallback: get any user from the company
                    fallback_result = await self.db.execute(
                        select(User).where(User.company_id == channel.company_id).limit(1)
                    )
                    fallback_user = fallback_result.scalar_one_or_none()
                    if fallback_user:
                        system_user_id = fallback_user.id

        if not system_user_id:
            raise ValueError("No system user available to create message")

        message = Message(
            id=str(uuid.uuid4()),
            channel_id=channel_id,
            author_id=system_user_id,
            body=message_body,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)

        # Broadcast message via WebSocket
        await channel_hub.broadcast(
            channel_id,
            {
                "type": "message",
                "data": {
                    "id": message.id,
                    "channel_id": message.channel_id,
                    "author_id": message.author_id,
                    "body": message.body,
                    "created_at": message.created_at.isoformat(),
                },
            },
        )

        logger.info(f"Created system message in channel {channel_id}: {message.id}")
        return message

    async def notify_driver_webhook_event(
        self,
        company_id: str,
        driver_id: str,
        event_type: str,
        event_data: Dict[str, Any],
        driver_name: Optional[str] = None,
    ) -> Message:
        """
        Create a notification message in a driver's channel from a webhook event.
        
        Args:
            company_id: Company ID
            driver_id: Driver ID
            event_type: Type of webhook event (e.g., "hos_violation", "geofence_entry")
            event_data: Event data dictionary
            driver_name: Optional driver name for channel creation
        """
        channel = await self.get_or_create_driver_channel(company_id, driver_id, driver_name)

        # Format message based on event type
        message_body = self._format_webhook_message(event_type, event_data)

        return await self.create_system_message(channel.id, message_body)

    def _format_webhook_message(self, event_type: str, event_data: Dict[str, Any]) -> str:
        """Format a webhook event into a human-readable chat message."""
        if event_type in ["hos_violation", "hos.violation", "violation.created"]:
            violation_type = event_data.get("violation_type", "HOS violation")
            severity = event_data.get("severity", "warning")
            return f"⚠️ **HOS Violation Alert**: {violation_type} detected. Severity: {severity}"

        elif event_type in ["hos_status", "hos.status", "hos.updated"]:
            status = event_data.get("status", "unknown")
            hours_remaining = event_data.get("hours_remaining")
            if hours_remaining is not None:
                return f"📊 **HOS Status Update**: Current status: {status}. Hours remaining: {hours_remaining}"
            return f"📊 **HOS Status Update**: Current status: {status}"

        elif event_type in ["geofence_entry", "geofence.entry", "vehicle_geofence_event"]:
            geofence_name = event_data.get("geofence_name", "geofence")
            location = event_data.get("location", "")
            if location:
                return f"📍 **Geofence Entry**: Entered {geofence_name} at {location}"
            return f"📍 **Geofence Entry**: Entered {geofence_name}"

        elif event_type in ["geofence_exit", "geofence.exit"]:
            geofence_name = event_data.get("geofence_name", "geofence")
            return f"🚪 **Geofence Exit**: Left {geofence_name}"

        elif event_type in ["fault_code", "fault_code.created", "fault_code_opened"]:
            fault_code = event_data.get("fault_code", "unknown")
            description = event_data.get("description", "")
            if description:
                return f"🔧 **Fault Code Alert**: {fault_code} - {description}"
            return f"🔧 **Fault Code Alert**: {fault_code}"

        elif event_type in ["vehicle_location", "vehicle.location", "vehicle_location_updated"]:
            location = event_data.get("location", {})
            lat = location.get("latitude") if isinstance(location, dict) else None
            lng = location.get("longitude") if isinstance(location, dict) else None
            if lat and lng:
                return f"🗺️ **Location Update**: Vehicle at {lat}, {lng}"
            return "🗺️ **Location Update**: Vehicle location updated"

        elif event_type in ["speeding_event", "speeding_event_created"]:
            speed = event_data.get("speed")
            limit = event_data.get("speed_limit")
            if speed and limit:
                return f"🚨 **Speeding Alert**: Traveling at {speed} mph (limit: {limit} mph)"
            return "🚨 **Speeding Alert**: Speeding detected"

        elif event_type in ["driver_performance", "driver_performance_event_created"]:
            performance_type = event_data.get("type", "performance event")
            return f"📈 **Performance Event**: {performance_type}"

        elif event_type in ["engine_toggle", "engine_toggle_event"]:
            trigger = event_data.get("trigger", "unknown")
            return f"🔌 **Engine Event**: {trigger}"

        else:
            # Generic webhook message
            return f"📢 **System Notification**: {event_type} event received"

    async def notify_load_assignment(
        self,
        company_id: str,
        driver_id: str,
        load_id: str,
        load_details: Dict[str, Any],
        driver_name: Optional[str] = None,
    ) -> Message:
        """Create a notification message for load assignment."""
        channel = await self.get_or_create_driver_channel(company_id, driver_id, driver_name)

        pickup = load_details.get("pickup_location", {})
        delivery = load_details.get("delivery_location", {})
        pickup_addr = pickup.get("address", "TBD") if isinstance(pickup, dict) else "TBD"
        delivery_addr = delivery.get("address", "TBD") if isinstance(delivery, dict) else "TBD"

        message_body = (
            f"📦 **New Load Assigned**\n\n"
            f"Load ID: {load_id}\n"
            f"Pickup: {pickup_addr}\n"
            f"Delivery: {delivery_addr}\n"
            f"Please confirm acceptance."
        )

        return await self.create_system_message(channel.id, message_body)

    async def notify_pickup_reminder(
        self,
        company_id: str,
        driver_id: str,
        load_id: str,
        pickup_time: str,
        location: str,
        driver_name: Optional[str] = None,
    ) -> Message:
        """Create a pickup reminder message."""
        channel = await self.get_or_create_driver_channel(company_id, driver_id, driver_name)

        message_body = (
            f"⏰ **Pickup Reminder**\n\n"
            f"Load ID: {load_id}\n"
            f"Scheduled pickup: {pickup_time}\n"
            f"Location: {location}\n"
            f"Please arrive on time."
        )

        return await self.create_system_message(channel.id, message_body)









