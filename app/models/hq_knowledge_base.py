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
    category = Column(Enum(KnowledgeCategory), nullable=False)
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
    category = Column(Enum(KnowledgeCategory), nullable=False)

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
