from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.collaboration import Channel, ChannelParticipant, Message
from app.models.user import User
from app.schemas.collaboration import (
    ChannelCreate,
    ChannelDetailResponse,
    ChannelResponse,
    GroupChatCreate,
    MessageCreate,
    MessageResponse,
    ParticipantResponse,
)


class CollaborationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_channels(self, company_id: str, driver_id: Optional[str] = None) -> List[ChannelResponse]:
        """
        List channels for a company with participants eagerly loaded.
        If driver_id is provided, filter to driver-specific channels.
        """
        query = (
            select(Channel)
            .where(Channel.company_id == company_id)
            .options(selectinload(Channel.participants))
        )

        if driver_id:
            query = query.where(Channel.name.like(f"driver:{driver_id}%"))

        query = query.order_by(Channel.created_at.desc())
        result = await self.db.execute(query)
        channels = list(result.scalars().all())

        return [self._channel_to_response(ch) for ch in channels]

    def _channel_to_response(self, channel: Channel) -> ChannelResponse:
        """Convert Channel model to ChannelResponse with participants."""
        participants = [
            ParticipantResponse(
                id=p.id,
                user_id=p.user_id,
                driver_id=p.driver_id,
                display_name=p.display_name,
                added_at=p.added_at,
            )
            for p in (channel.participants or [])
        ]
        return ChannelResponse(
            id=channel.id,
            name=channel.name,
            description=channel.description,
            channel_type=channel.channel_type or "dm",
            participants=participants,
            created_at=channel.created_at,
        )

    async def create_channel(self, company_id: str, payload: ChannelCreate) -> ChannelResponse:
        channel = Channel(
            id=str(uuid.uuid4()),
            company_id=company_id,
            name=payload.name,
            description=payload.description,
            channel_type="group",
        )
        self.db.add(channel)
        await self.db.commit()
        await self.db.refresh(channel)
        return self._channel_to_response(channel)

    async def get_channel(self, company_id: str, channel_id: str) -> Channel:
        result = await self.db.execute(
            select(Channel)
            .where(Channel.company_id == company_id, Channel.id == channel_id)
            .options(selectinload(Channel.participants))
        )
        channel = result.scalar_one_or_none()
        if not channel:
            raise ValueError("Channel not found")
        return channel

    async def delete_channel(self, company_id: str, channel_id: str) -> bool:
        """Delete a channel and all its messages/participants (cascading)."""
        channel = await self.get_channel(company_id, channel_id)
        await self.db.delete(channel)
        await self.db.commit()
        return True

    async def list_messages(self, channel_id: str) -> List[Message]:
        result = await self.db.execute(
            select(Message).where(Message.channel_id == channel_id).order_by(Message.created_at.desc())
        )
        return list(result.scalars().all())

    async def post_message(self, channel_id: str, author_id: str, payload: MessageCreate) -> Message:
        message = Message(
            id=str(uuid.uuid4()),
            channel_id=channel_id,
            author_id=author_id,
            body=payload.body,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def channel_detail(self, company_id: str, channel_id: str) -> ChannelDetailResponse:
        channel = await self.get_channel(company_id, channel_id)
        messages = await self.list_messages(channel_id)

        participants = [
            ParticipantResponse(
                id=p.id,
                user_id=p.user_id,
                driver_id=p.driver_id,
                display_name=p.display_name,
                added_at=p.added_at,
            )
            for p in (channel.participants or [])
        ]

        return ChannelDetailResponse(
            id=channel.id,
            name=channel.name,
            description=channel.description,
            channel_type=channel.channel_type or "dm",
            participants=participants,
            created_at=channel.created_at,
            messages=[MessageResponse.model_validate(message) for message in messages],
        )

    async def get_or_create_dm_channel(
        self, company_id: str, user1_id: str, user2_id: str,
        user1_name: str, user2_name: str
    ) -> ChannelResponse:
        """
        Get or create a direct message channel between two users.
        Uses a consistent naming convention: dm:{sorted_user_ids}
        Adds both users as participants with their display names.
        """
        sorted_ids = sorted([user1_id, user2_id])
        channel_name = f"dm:{sorted_ids[0]}:{sorted_ids[1]}"

        result = await self.db.execute(
            select(Channel)
            .where(Channel.company_id == company_id, Channel.name == channel_name)
            .options(selectinload(Channel.participants))
        )
        existing = result.scalar_one_or_none()
        if existing:
            # Backfill participants if missing (for channels created before migration)
            if not existing.participants or len(existing.participants) < 2:
                existing_user_ids = {p.user_id for p in (existing.participants or [])}
                if user1_id not in existing_user_ids:
                    p1 = ChannelParticipant(
                        id=str(uuid.uuid4()),
                        channel_id=existing.id,
                        user_id=user1_id,
                        display_name=user1_name,
                    )
                    self.db.add(p1)
                if user2_id not in existing_user_ids:
                    p2 = ChannelParticipant(
                        id=str(uuid.uuid4()),
                        channel_id=existing.id,
                        user_id=user2_id,
                        display_name=user2_name,
                    )
                    self.db.add(p2)
                # Update channel type if not set
                if not existing.channel_type:
                    existing.channel_type = "dm"
                await self.db.commit()
                # Reload with participants
                result = await self.db.execute(
                    select(Channel)
                    .where(Channel.id == existing.id)
                    .options(selectinload(Channel.participants))
                )
                existing = result.scalar_one()
            return self._channel_to_response(existing)

        # Create new DM channel
        channel_id = str(uuid.uuid4())
        channel = Channel(
            id=channel_id,
            company_id=company_id,
            name=channel_name,
            description=f"{user1_name}, {user2_name}",
            channel_type="dm",
        )
        self.db.add(channel)

        # Add both participants
        p1 = ChannelParticipant(
            id=str(uuid.uuid4()),
            channel_id=channel_id,
            user_id=user1_id,
            display_name=user1_name,
        )
        p2 = ChannelParticipant(
            id=str(uuid.uuid4()),
            channel_id=channel_id,
            user_id=user2_id,
            display_name=user2_name,
        )
        self.db.add(p1)
        self.db.add(p2)

        await self.db.commit()
        await self.db.refresh(channel)

        # Reload with participants
        result = await self.db.execute(
            select(Channel)
            .where(Channel.id == channel_id)
            .options(selectinload(Channel.participants))
        )
        channel = result.scalar_one()
        return self._channel_to_response(channel)

    async def create_group_chat(
        self, company_id: str, creator_id: str, payload: GroupChatCreate
    ) -> ChannelResponse:
        """
        Create a group chat with multiple participants.
        """
        channel_id = str(uuid.uuid4())
        channel = Channel(
            id=channel_id,
            company_id=company_id,
            name=payload.name,
            description=f"Group chat: {payload.name}",
            channel_type="group",
            created_by=creator_id,
        )
        self.db.add(channel)

        # Get creator's name
        creator_result = await self.db.execute(
            select(User).where(User.id == creator_id)
        )
        creator = creator_result.scalar_one_or_none()
        creator_name = f"{creator.first_name} {creator.last_name}" if creator else "Unknown"

        # Add creator as participant
        creator_participant = ChannelParticipant(
            id=str(uuid.uuid4()),
            channel_id=channel_id,
            user_id=creator_id,
            display_name=creator_name,
        )
        self.db.add(creator_participant)

        # Add other participants
        for user_id in payload.participant_ids:
            if user_id == creator_id:
                continue  # Skip if creator is also in the list

            user_result = await self.db.execute(
                select(User).where(User.id == user_id, User.company_id == company_id)
            )
            user = user_result.scalar_one_or_none()
            if user:
                participant = ChannelParticipant(
                    id=str(uuid.uuid4()),
                    channel_id=channel_id,
                    user_id=user_id,
                    display_name=f"{user.first_name} {user.last_name}",
                )
                self.db.add(participant)

        await self.db.commit()

        # Reload with participants
        result = await self.db.execute(
            select(Channel)
            .where(Channel.id == channel_id)
            .options(selectinload(Channel.participants))
        )
        channel = result.scalar_one()
        return self._channel_to_response(channel)

    async def get_or_create_driver_channel(
        self, company_id: str, driver_id: str, driver_name: str
    ) -> ChannelResponse:
        """
        Get or create a channel for driver communication.
        """
        channel_name = f"driver:{driver_id}"

        result = await self.db.execute(
            select(Channel)
            .where(Channel.company_id == company_id, Channel.name == channel_name)
            .options(selectinload(Channel.participants))
        )
        existing = result.scalar_one_or_none()
        if existing:
            return self._channel_to_response(existing)

        channel_id = str(uuid.uuid4())
        channel = Channel(
            id=channel_id,
            company_id=company_id,
            name=channel_name,
            description=driver_name,
            channel_type="driver",
        )
        self.db.add(channel)

        # Add driver as participant
        participant = ChannelParticipant(
            id=str(uuid.uuid4()),
            channel_id=channel_id,
            driver_id=driver_id,
            display_name=driver_name,
        )
        self.db.add(participant)

        await self.db.commit()

        result = await self.db.execute(
            select(Channel)
            .where(Channel.id == channel_id)
            .options(selectinload(Channel.participants))
        )
        channel = result.scalar_one()
        return self._channel_to_response(channel)
