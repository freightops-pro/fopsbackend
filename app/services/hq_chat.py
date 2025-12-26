"""HQ Chat Service - Unified Team + AI Chat.

Handles:
- Team channels (human-to-human messaging)
- AI channel (auto-routes to Oracle/Sentinel/Nexus)
- Message persistence and retrieval
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Dict, List, Literal, Optional, Tuple

from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hq_chat import HQChatChannel, HQChatMessage, HQChatParticipant
from app.schemas.hq import (
    HQAgentType,
    HQChannelType,
    HQChatChannelCreate,
    HQChatChannelResponse,
    HQChatMessageCreate,
    HQChatMessageResponse,
    HQChatParticipant as HQChatParticipantSchema,
    HQChatAIRoutingResult,
)
from app.services.hq_colab import get_hq_colab_service

import logging

logger = logging.getLogger(__name__)


# AI Agent Keywords for routing
AI_ROUTING_KEYWORDS: Dict[HQAgentType, List[str]] = {
    "oracle": [
        "revenue", "mrr", "arr", "churn", "forecast", "analytics", "metrics",
        "growth", "subscription", "tenant", "customer", "pricing", "tier",
        "conversion", "retention", "ltv", "arpu", "pipeline", "sales",
        "profit", "margin", "trend", "report", "dashboard", "kpi"
    ],
    "sentinel": [
        "fraud", "security", "compliance", "kyb", "kyc", "alert", "risk",
        "audit", "violation", "suspicious", "block", "freeze", "verify",
        "identity", "review", "policy", "regulation", "access", "permission"
    ],
    "nexus": [
        "system", "status", "integration", "webhook", "api", "sync", "health",
        "uptime", "maintenance", "deploy", "stripe", "synctera", "check",
        "payroll", "outage", "error", "connection", "service", "module"
    ]
}


class HQChatService:
    """Service for HQ unified chat operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._colab_service = get_hq_colab_service()

    # =========================================================================
    # AI Routing
    # =========================================================================

    def route_to_agent(self, message: str) -> HQChatAIRoutingResult:
        """Determine which AI agent should handle the message."""
        message_lower = message.lower()

        scores: Dict[HQAgentType, int] = {"oracle": 0, "sentinel": 0, "nexus": 0}

        for agent, keywords in AI_ROUTING_KEYWORDS.items():
            for keyword in keywords:
                if keyword in message_lower:
                    scores[agent] += 1

        # Find agent with highest score
        max_score = max(scores.values())

        if max_score == 0:
            # Default to Oracle for general questions
            return HQChatAIRoutingResult(
                agent="oracle",
                confidence=0.5,
                reasoning="No specific keywords detected, routing to Oracle for general analysis"
            )

        # Get agent with highest score
        best_agent: HQAgentType = max(scores, key=lambda k: scores[k])

        # Calculate confidence based on keyword matches
        total_matches = sum(scores.values())
        confidence = min(0.95, 0.6 + (scores[best_agent] / max(total_matches, 1)) * 0.35)

        agent_names = {
            "oracle": "Oracle (Strategic Insights)",
            "sentinel": "Sentinel (Security & Compliance)",
            "nexus": "Nexus (Operations)"
        }

        return HQChatAIRoutingResult(
            agent=best_agent,
            confidence=confidence,
            reasoning=f"Routed to {agent_names[best_agent]} based on {scores[best_agent]} keyword matches"
        )

    # =========================================================================
    # Channel Management
    # =========================================================================

    async def list_channels(self) -> List[HQChatChannelResponse]:
        """List all HQ chat channels with participants and last message."""
        result = await self.db.execute(
            select(HQChatChannel).order_by(
                HQChatChannel.is_pinned.desc(),
                HQChatChannel.updated_at.desc()
            )
        )
        channels = result.scalars().all()

        response = []
        for channel in channels:
            # Get participants
            participants = await self._get_channel_participants(channel.id)

            response.append(HQChatChannelResponse(
                id=channel.id,
                name=channel.name,
                channel_type=channel.channel_type,
                description=channel.description,
                last_message=channel.last_message,
                last_message_at=channel.last_message_at,
                unread_count=0,  # TODO: Implement per-user read tracking
                is_pinned=channel.is_pinned,
                participants=participants,
                created_at=channel.created_at,
                updated_at=channel.updated_at
            ))

        return response

    async def get_channel(self, channel_id: str) -> HQChatChannelResponse:
        """Get a specific channel by ID."""
        result = await self.db.execute(
            select(HQChatChannel).where(HQChatChannel.id == channel_id)
        )
        channel = result.scalar_one_or_none()

        if not channel:
            raise ValueError(f"Channel {channel_id} not found")

        participants = await self._get_channel_participants(channel_id)

        return HQChatChannelResponse(
            id=channel.id,
            name=channel.name,
            channel_type=channel.channel_type,
            description=channel.description,
            last_message=channel.last_message,
            last_message_at=channel.last_message_at,
            unread_count=0,
            is_pinned=channel.is_pinned,
            participants=participants,
            created_at=channel.created_at,
            updated_at=channel.updated_at
        )

    async def create_channel(self, payload: HQChatChannelCreate) -> HQChatChannelResponse:
        """Create a new chat channel."""
        channel = HQChatChannel(
            id=str(uuid.uuid4()),
            name=payload.name,
            channel_type=payload.channel_type,
            description=payload.description,
            is_pinned=payload.channel_type == "announcement",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        self.db.add(channel)
        await self.db.commit()
        await self.db.refresh(channel)

        return HQChatChannelResponse(
            id=channel.id,
            name=channel.name,
            channel_type=channel.channel_type,
            description=channel.description,
            last_message=None,
            last_message_at=None,
            unread_count=0,
            is_pinned=channel.is_pinned,
            participants=[],
            created_at=channel.created_at,
            updated_at=channel.updated_at
        )

    async def delete_channel(self, channel_id: str) -> None:
        """Delete a channel and all its messages."""
        # Delete messages first
        await self.db.execute(
            delete(HQChatMessage).where(HQChatMessage.channel_id == channel_id)
        )

        # Delete participants
        await self.db.execute(
            delete(HQChatParticipant).where(HQChatParticipant.channel_id == channel_id)
        )

        # Delete channel
        result = await self.db.execute(
            delete(HQChatChannel).where(HQChatChannel.id == channel_id)
        )

        if result.rowcount == 0:
            raise ValueError(f"Channel {channel_id} not found")

        await self.db.commit()

    async def ensure_default_channels(self) -> None:
        """Ensure default channels exist (General, AI Team, Announcements)."""
        default_channels = [
            {
                "id": "general",
                "name": "General",
                "channel_type": "team",
                "description": "General team discussion",
                "is_pinned": True
            },
            {
                "id": "ai-team",
                "name": "AI Team",
                "channel_type": "ai",
                "description": "Chat with AI assistants (Oracle, Sentinel, Nexus)",
                "is_pinned": True
            },
            {
                "id": "announcements",
                "name": "Announcements",
                "channel_type": "announcement",
                "description": "Company-wide announcements",
                "is_pinned": True
            }
        ]

        for ch_data in default_channels:
            result = await self.db.execute(
                select(HQChatChannel).where(HQChatChannel.id == ch_data["id"])
            )
            if not result.scalar_one_or_none():
                channel = HQChatChannel(
                    id=ch_data["id"],
                    name=ch_data["name"],
                    channel_type=ch_data["channel_type"],
                    description=ch_data["description"],
                    is_pinned=ch_data["is_pinned"],
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                self.db.add(channel)

        await self.db.commit()

    async def _get_channel_participants(self, channel_id: str) -> List[HQChatParticipantSchema]:
        """Get participants for a channel."""
        result = await self.db.execute(
            select(HQChatParticipant).where(HQChatParticipant.channel_id == channel_id)
        )
        participants = result.scalars().all()

        return [
            HQChatParticipantSchema(
                id=p.id,
                employee_id=p.employee_id,
                display_name=p.display_name,
                role=p.role,
                is_ai=p.is_ai,
                added_at=p.added_at
            )
            for p in participants
        ]

    # =========================================================================
    # Message Management
    # =========================================================================

    async def list_messages(self, channel_id: str, limit: int = 100) -> List[HQChatMessageResponse]:
        """Get messages for a channel."""
        result = await self.db.execute(
            select(HQChatMessage)
            .where(HQChatMessage.channel_id == channel_id)
            .order_by(HQChatMessage.created_at.asc())
            .limit(limit)
        )
        messages = result.scalars().all()

        return [
            HQChatMessageResponse(
                id=m.id,
                channel_id=m.channel_id,
                author_id=m.author_id,
                author_name=m.author_name,
                content=m.content,
                is_ai_response=m.is_ai_response,
                ai_agent=m.ai_agent,
                ai_reasoning=m.ai_reasoning,
                ai_confidence=m.ai_confidence,
                mentions=m.mentions,
                is_read=m.is_read,
                created_at=m.created_at
            )
            for m in messages
        ]

    async def post_message(
        self,
        channel_id: str,
        author_id: str,
        author_name: str,
        payload: HQChatMessageCreate
    ) -> Tuple[HQChatMessageResponse, Optional[HQChatMessageResponse]]:
        """
        Post a message to a channel.

        Returns tuple of (user_message, ai_response) where ai_response is None
        for non-AI channels.
        """
        # Verify channel exists
        result = await self.db.execute(
            select(HQChatChannel).where(HQChatChannel.id == channel_id)
        )
        channel = result.scalar_one_or_none()

        if not channel:
            raise ValueError(f"Channel {channel_id} not found")

        # Create user message
        user_message = HQChatMessage(
            id=str(uuid.uuid4()),
            channel_id=channel_id,
            author_id=author_id,
            author_name=author_name,
            content=payload.content,
            mentions=payload.mentions,
            is_ai_response=False,
            created_at=datetime.utcnow()
        )

        self.db.add(user_message)

        # Update channel's last message
        await self.db.execute(
            update(HQChatChannel)
            .where(HQChatChannel.id == channel_id)
            .values(
                last_message=payload.content[:100],
                last_message_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        )

        await self.db.commit()
        await self.db.refresh(user_message)

        user_response = HQChatMessageResponse(
            id=user_message.id,
            channel_id=user_message.channel_id,
            author_id=user_message.author_id,
            author_name=user_message.author_name,
            content=user_message.content,
            is_ai_response=False,
            ai_agent=None,
            ai_reasoning=None,
            ai_confidence=None,
            mentions=user_message.mentions,
            is_read=False,
            created_at=user_message.created_at
        )

        # If this is an AI channel, generate AI response
        ai_response = None
        if channel.channel_type == "ai":
            ai_response = await self._generate_ai_response(
                channel_id=channel_id,
                user_message=payload.content,
                user_id=author_id,
                user_name=author_name
            )

        return user_response, ai_response

    async def _generate_ai_response(
        self,
        channel_id: str,
        user_message: str,
        user_id: str,
        user_name: str
    ) -> HQChatMessageResponse:
        """Generate AI response for a message in an AI channel."""
        # Route to appropriate agent
        routing = self.route_to_agent(user_message)

        # Generate response using Colab service
        session_id = f"hq_chat_{channel_id}"

        try:
            colab_response = await self._colab_service.chat(
                session_id=session_id,
                agent=routing.agent,
                message=user_message,
                user_id=user_id,
                user_name=user_name
            )

            response_content = colab_response.response
            reasoning = colab_response.reasoning
            confidence = colab_response.confidence
        except Exception as e:
            logger.error(f"AI response generation failed: {e}")
            response_content = f"I apologize, but I'm having trouble processing your request right now. Please try again in a moment."
            reasoning = f"Error: {str(e)}"
            confidence = 0.0

        # Agent display names
        agent_names = {
            "oracle": "Oracle",
            "sentinel": "Sentinel",
            "nexus": "Nexus"
        }

        # Create AI message
        ai_message = HQChatMessage(
            id=str(uuid.uuid4()),
            channel_id=channel_id,
            author_id=f"ai_{routing.agent}",
            author_name=agent_names[routing.agent],
            content=response_content,
            is_ai_response=True,
            ai_agent=routing.agent,
            ai_reasoning=reasoning,
            ai_confidence=confidence,
            created_at=datetime.utcnow()
        )

        self.db.add(ai_message)

        # Update channel's last message
        await self.db.execute(
            update(HQChatChannel)
            .where(HQChatChannel.id == channel_id)
            .values(
                last_message=response_content[:100],
                last_message_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        )

        await self.db.commit()
        await self.db.refresh(ai_message)

        return HQChatMessageResponse(
            id=ai_message.id,
            channel_id=ai_message.channel_id,
            author_id=ai_message.author_id,
            author_name=ai_message.author_name,
            content=ai_message.content,
            is_ai_response=True,
            ai_agent=ai_message.ai_agent,
            ai_reasoning=ai_message.ai_reasoning,
            ai_confidence=ai_message.ai_confidence,
            mentions=None,
            is_read=False,
            created_at=ai_message.created_at
        )

    async def mark_messages_read(self, channel_id: str, user_id: str) -> None:
        """Mark all messages in a channel as read for a user."""
        # TODO: Implement per-user read tracking
        pass
