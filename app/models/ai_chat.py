"""AI Chat and Conversation Models."""
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.models.base import Base


class AIConversation(Base):
    """
    Stores AI conversation threads.

    Each conversation is a chat session between a user and one or more AI assistants.
    Conversations are company-scoped for privacy.
    """
    __tablename__ = "ai_conversations"

    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)

    # AI assistant involved (alex, annie, atlas, or "auto" for multi-assistant)
    assistant_type = Column(String, nullable=False, default="auto")  # alex | annie | atlas | auto

    # Conversation metadata
    title = Column(String, nullable=True)  # Auto-generated or user-set
    context_type = Column(String, nullable=True)  # load | driver | truck | customer | invoice | etc.
    context_id = Column(String, nullable=True)  # ID of the entity being discussed

    # Status
    status = Column(String, default="active")  # active | archived | resolved

    # Message count
    message_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_message_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    messages = relationship("AIMessage", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_ai_conversations_company_updated", "company_id", "updated_at"),
        Index("idx_ai_conversations_user_updated", "user_id", "updated_at"),
        Index("idx_ai_conversations_context", "context_type", "context_id"),
    )


class AIMessage(Base):
    """
    Individual messages within an AI conversation.

    Stores both user messages and AI responses with full context.
    """
    __tablename__ = "ai_messages"

    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("ai_conversations.id"), nullable=False, index=True)
    company_id = Column(String, nullable=False, index=True)

    # Message sender
    role = Column(String, nullable=False)  # user | assistant | system | tool
    assistant_type = Column(String, nullable=True)  # alex | annie | atlas (for assistant messages)
    user_id = Column(String, nullable=True)  # For user messages

    # Message content
    content = Column(Text, nullable=False)

    # AI-specific fields
    tokens_used = Column(Integer, nullable=True)  # Total tokens (input + output)
    model = Column(String, nullable=True)  # gemini-2.5-flash, claude-3.5-sonnet, etc.

    # Tool/function calling
    tool_calls = Column(JSON, nullable=True)  # Array of tool calls made by AI
    tool_results = Column(JSON, nullable=True)  # Results from tool executions

    # Context and metadata
    context_snapshot = Column(JSON, nullable=True)  # Snapshot of relevant context at message time
    metadata = Column(JSON, nullable=True)  # Additional metadata

    # Confidence and quality
    confidence_score = Column(Integer, nullable=True)  # 0-100

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    conversation = relationship("AIConversation", back_populates="messages")

    __table_args__ = (
        Index("idx_ai_messages_conversation_created", "conversation_id", "created_at"),
        Index("idx_ai_messages_company_created", "company_id", "created_at"),
    )


class AIContext(Base):
    """
    Per-company AI context and preferences.

    Stores company-specific settings, learned preferences, and context
    that helps AIs provide better responses.
    """
    __tablename__ = "ai_contexts"

    id = Column(String, primary_key=True)
    company_id = Column(String, unique=True, nullable=False, index=True)

    # AI preferences
    preferred_assistant = Column(String, nullable=True)  # alex | annie | atlas | auto
    auto_route_enabled = Column(String, default="true")  # Auto-route to best AI

    # Company-specific knowledge
    # These are learned over time or manually configured
    common_customers = Column(JSON, nullable=True)  # Frequently mentioned customers
    common_lanes = Column(JSON, nullable=True)  # Common origin → destination pairs
    common_equipment = Column(JSON, nullable=True)  # Typical equipment types
    business_rules = Column(JSON, nullable=True)  # Custom business rules

    # Operational preferences
    preferred_rate_structure = Column(String, nullable=True)  # per_mile | flat_rate | etc.
    timezone = Column(String, nullable=True)  # Company timezone
    units = Column(String, default="imperial")  # imperial | metric

    # AI behavior settings
    ai_formality = Column(String, default="professional")  # casual | professional | technical
    ai_verbosity = Column(String, default="balanced")  # concise | balanced | detailed

    # Learning data
    successful_suggestions = Column(JSON, nullable=True)  # Track what suggestions were accepted
    rejected_suggestions = Column(JSON, nullable=True)  # Track what was rejected

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
