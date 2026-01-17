"""HQ Knowledge Base models for RAG (Retrieval Augmented Generation).

This module provides vector storage for AI agent knowledge retrieval.
Uses pgvector for efficient similarity search.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import (
    Column, String, Text, DateTime, Enum, Integer, Index, Float
)
from sqlalchemy.dialects.postgresql import ARRAY
from pgvector.sqlalchemy import Vector

from app.models.base import Base


class KnowledgeCategory(str, PyEnum):
    """Knowledge document categories."""
    ACCOUNTING = "accounting"  # GAAP, bookkeeping, financial statements
    TAXES = "taxes"  # Payroll taxes, IFTA, 2290, quarterly filings
    HR = "hr"  # Hiring, termination, labor laws, benefits
    PAYROLL = "payroll"  # Driver pay, deductions, garnishments
    MARKETING = "marketing"  # Sales, customer acquisition, retention
    COMPLIANCE = "compliance"  # Banking, BSA/AML, KYB/KYC
    OPERATIONS = "operations"  # System health, integrations, SaaS metrics
    GENERAL = "general"  # General business knowledge


class HQKnowledgeDocument(Base):
    """
    Knowledge base document for RAG retrieval.

    Documents are chunked and embedded for semantic search.
    """
    __tablename__ = "hq_knowledge_documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Document metadata
    title = Column(String(500), nullable=False)
    category = Column(
        Enum(
            KnowledgeCategory,
            name='knowledgecategory',
            create_type=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False
    )
    source = Column(String(500), nullable=True)  # Where this knowledge came from

    # Full document content (for reference)
    content = Column(Text, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<HQKnowledgeDocument {self.id} - {self.title[:50]}>"


class HQKnowledgeChunk(Base):
    """
    Chunked and embedded knowledge for vector search.

    Each document is split into smaller chunks for better retrieval.
    """
    __tablename__ = "hq_knowledge_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Link to parent document
    document_id = Column(String(36), nullable=False, index=True)

    # Chunk metadata
    chunk_index = Column(Integer, nullable=False)  # Position in document

    # Chunk content
    content = Column(Text, nullable=False)

    # Vector embedding (1536 dimensions for OpenAI ada-002, 768 for others)
    embedding = Column(Vector(1536), nullable=True)

    # Category for filtering
    category = Column(
        Enum(
            KnowledgeCategory,
            name='knowledgecategory',
            create_type=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Index for vector similarity search
    __table_args__ = (
        Index(
            'ix_hq_knowledge_chunks_embedding',
            embedding,
            postgresql_using='ivfflat',
            postgresql_with={'lists': 100},
            postgresql_ops={'embedding': 'vector_cosine_ops'}
        ),
    )

    def __repr__(self):
        return f"<HQKnowledgeChunk {self.id} - doc:{self.document_id} chunk:{self.chunk_index}>"


# =============================================================================
# Learning & Feedback Models
# =============================================================================

class FeedbackType(str, PyEnum):
    """Types of user feedback."""
    HELPFUL = "helpful"
    UNHELPFUL = "unhelpful"
    INACCURATE = "inaccurate"
    INCOMPLETE = "incomplete"
    OUTDATED = "outdated"


class GapType(str, PyEnum):
    """Types of knowledge gaps detected."""
    MISSING_TOPIC = "missing_topic"  # No relevant knowledge found
    LOW_RELEVANCE = "low_relevance"  # Found chunks but poor match
    CONTRADICTION = "contradiction"  # Conflicting information
    OUTDATED = "outdated"  # Knowledge is stale
    INSUFFICIENT_DEPTH = "insufficient_depth"  # Too shallow


class HQAgentInteraction(Base):
    """
    Records all agent interactions for learning analysis.

    Every query/response is logged to enable continuous improvement.
    """
    __tablename__ = "hq_agent_interactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Agent context
    agent_type = Column(String(50), nullable=False, index=True)  # oracle, sentinel, nexus
    task_id = Column(String(36), nullable=True, index=True)  # Link to HQAITask if applicable

    # Query details
    user_query = Column(Text, nullable=False)
    query_embedding = Column(Vector(1536), nullable=True)  # For similarity analysis

    # Retrieved knowledge
    retrieved_chunk_ids = Column(Text, nullable=True)  # JSON array of chunk IDs
    retrieval_scores = Column(Text, nullable=True)  # JSON array of similarity scores

    # Response
    final_response = Column(Text, nullable=True)
    response_length = Column(Integer, nullable=True)

    # Quality metrics (calculated)
    retrieval_quality_score = Column(Float, nullable=True)  # 0-1
    response_confidence = Column(Float, nullable=True)  # 0-1

    # User context
    user_context = Column(Text, nullable=True)  # JSON with additional context

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    response_time_ms = Column(Integer, nullable=True)  # Response latency

    __table_args__ = (
        Index('ix_hq_agent_interactions_agent_type', 'agent_type'),
        Index('ix_hq_agent_interactions_created_at', 'created_at'),
    )

    def __repr__(self):
        return f"<HQAgentInteraction {self.id} - {self.agent_type}>"


class HQKnowledgeFeedback(Base):
    """
    User feedback on agent responses for learning.

    Both explicit (thumbs up/down) and implicit (follow-up patterns) feedback.
    """
    __tablename__ = "hq_knowledge_feedback"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Link to interaction
    interaction_id = Column(String(36), nullable=False, index=True)

    # Feedback details
    feedback_type = Column(
        Enum(
            FeedbackType,
            name='feedbacktype',
            create_type=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False
    )
    user_rating = Column(Integer, nullable=True)  # 1-5 scale
    user_comment = Column(Text, nullable=True)
    suggested_correction = Column(Text, nullable=True)

    # Which chunks were used (to update their confidence)
    affected_chunk_ids = Column(Text, nullable=True)  # JSON array

    # Metadata
    feedback_source = Column(String(50), default="user")  # user, auto, admin
    processed = Column(Integer, default=0)  # 0=pending, 1=processed

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('ix_hq_knowledge_feedback_processed', 'processed'),
    )

    def __repr__(self):
        return f"<HQKnowledgeFeedback {self.id} - {self.feedback_type.value}>"


class HQKnowledgeGap(Base):
    """
    Detected knowledge gaps for improvement.

    Tracks areas where the knowledge base is insufficient.
    """
    __tablename__ = "hq_knowledge_gaps"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Gap details
    gap_type = Column(
        Enum(
            GapType,
            name='gaptype',
            create_type=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False
    )
    topic = Column(Text, nullable=False)  # The query/topic with missing knowledge
    topic_embedding = Column(Vector(1536), nullable=True)  # For clustering similar gaps

    # Detection details
    detection_method = Column(String(100), nullable=False)  # zero_results, low_relevance, user_feedback
    confidence_score = Column(Float, default=0.5)  # How confident we are this is a real gap

    # Related data
    related_interaction_ids = Column(Text, nullable=True)  # JSON array
    suggested_category = Column(
        Enum(
            KnowledgeCategory,
            name='knowledgecategory',
            create_type=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        nullable=True
    )

    # Resolution
    status = Column(String(20), default="open")  # open, in_progress, resolved, dismissed
    resolution_notes = Column(Text, nullable=True)
    resolved_by_document_id = Column(String(36), nullable=True)

    # Priority (based on frequency and impact)
    occurrence_count = Column(Integer, default=1)
    priority_score = Column(Float, default=0.5)  # 0-1

    # Timestamps
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_occurred_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('ix_hq_knowledge_gaps_status', 'status'),
        Index('ix_hq_knowledge_gaps_priority', 'priority_score'),
    )

    def __repr__(self):
        return f"<HQKnowledgeGap {self.id} - {self.gap_type.value}: {self.topic[:50]}>"


class HQChunkConfidence(Base):
    """
    Tracks confidence/quality scores for each knowledge chunk.

    Updated based on feedback and usage patterns.
    """
    __tablename__ = "hq_chunk_confidence"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    chunk_id = Column(String(36), nullable=False, unique=True, index=True)

    # Confidence metrics
    confidence_score = Column(Float, default=1.0)  # 0-1, starts at 1.0
    usage_count = Column(Integer, default=0)  # How often retrieved
    helpful_count = Column(Integer, default=0)  # Positive feedback
    unhelpful_count = Column(Integer, default=0)  # Negative feedback

    # Calculated metrics
    helpfulness_ratio = Column(Float, default=1.0)  # helpful / (helpful + unhelpful)
    avg_retrieval_rank = Column(Float, nullable=True)  # Average position in results

    # Staleness tracking
    last_used_at = Column(DateTime, nullable=True)
    is_stale = Column(Integer, default=0)  # 0=fresh, 1=potentially stale

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<HQChunkConfidence {self.chunk_id} - score:{self.confidence_score:.2f}>"


class HQLearningMetrics(Base):
    """
    Daily learning metrics for monitoring knowledge base health.
    """
    __tablename__ = "hq_learning_metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Time period
    date = Column(DateTime, nullable=False, index=True)
    agent_type = Column(String(50), nullable=True)  # None for aggregate

    # Knowledge metrics
    total_documents = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    avg_chunk_confidence = Column(Float, default=1.0)

    # Learning activity
    new_chunks_added = Column(Integer, default=0)
    chunks_updated = Column(Integer, default=0)
    chunks_deprecated = Column(Integer, default=0)

    # Gap metrics
    gaps_detected = Column(Integer, default=0)
    gaps_resolved = Column(Integer, default=0)
    open_gaps_count = Column(Integer, default=0)

    # Interaction metrics
    total_interactions = Column(Integer, default=0)
    avg_retrieval_quality = Column(Float, default=0.0)

    # Feedback metrics
    feedback_received = Column(Integer, default=0)
    positive_feedback_pct = Column(Float, default=0.0)
    avg_user_rating = Column(Float, nullable=True)

    # Coverage estimate
    knowledge_coverage_pct = Column(Float, default=0.0)  # % of queries fully answered

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('ix_hq_learning_metrics_date_agent', 'date', 'agent_type'),
    )
