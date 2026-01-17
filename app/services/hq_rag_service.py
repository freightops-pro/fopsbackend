"""RAG (Retrieval Augmented Generation) Service for HQ AI Agents.

This service handles:
1. Document ingestion and chunking
2. Embedding generation (OpenAI or Gemini)
3. Vector similarity search for knowledge retrieval
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.hq_knowledge_base import (
    HQKnowledgeDocument,
    HQKnowledgeChunk,
    KnowledgeCategory,
)

logger = logging.getLogger(__name__)
settings = get_settings()


# =============================================================================
# Text Chunking
# =============================================================================

def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> List[str]:
    """
    Split text into overlapping chunks for embedding.

    Args:
        text: The text to chunk
        chunk_size: Target size of each chunk in characters
        chunk_overlap: Overlap between chunks

    Returns:
        List of text chunks
    """
    if not text or len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0

    while start < len(text):
        # Find end of chunk
        end = start + chunk_size

        # If not at the end, try to break at a sentence or paragraph
        if end < len(text):
            # Look for paragraph break
            para_break = text.rfind('\n\n', start, end)
            if para_break > start + chunk_size // 2:
                end = para_break + 2
            else:
                # Look for sentence break
                for sep in ['. ', '.\n', '? ', '?\n', '! ', '!\n']:
                    sent_break = text.rfind(sep, start, end)
                    if sent_break > start + chunk_size // 2:
                        end = sent_break + len(sep)
                        break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start with overlap
        start = end - chunk_overlap
        if start >= len(text):
            break

    return chunks


# =============================================================================
# Embedding Generation
# =============================================================================

async def generate_embedding_grok(text: str) -> Optional[List[float]]:
    """Generate embedding using Grok API (OpenAI-compatible format)."""
    api_key = settings.grok_api_key or settings.xai_api_key
    if not api_key:
        return None

    base_url = settings.grok_base_url

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "text-embedding-3-small",  # Grok embedding model
                    "input": text[:8000]  # Limit input size
                },
                timeout=30.0
            )

            if response.status_code == 200:
                data = response.json()
                embedding = data["data"][0]["embedding"]
                # Ensure 1536 dimensions
                if len(embedding) < 1536:
                    embedding.extend([0.0] * (1536 - len(embedding)))
                elif len(embedding) > 1536:
                    embedding = embedding[:1536]
                return embedding
            else:
                logger.error(f"Grok embedding error: {response.status_code} - {response.text}")
                return None

    except Exception as e:
        logger.error(f"Grok embedding error: {e}")
        return None


async def generate_embedding_gemini(text: str) -> Optional[List[float]]:
    """Generate embedding using Google's Gemini embedding model (fallback)."""
    api_key = settings.google_ai_api_key
    if not api_key:
        return None

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/embedding-001:embedContent?key={api_key}",
                headers={"Content-Type": "application/json"},
                json={
                    "model": "models/embedding-001",
                    "content": {"parts": [{"text": text[:8000]}]}
                },
                timeout=30.0
            )

            if response.status_code == 200:
                data = response.json()
                embedding = data.get("embedding", {}).get("values", [])
                # Pad to 1536 dimensions if needed (Gemini returns 768)
                if len(embedding) < 1536:
                    embedding.extend([0.0] * (1536 - len(embedding)))
                return embedding
            else:
                logger.error(f"Gemini embedding error: {response.status_code}")
                return None

    except Exception as e:
        logger.error(f"Gemini embedding error: {e}")
        return None


async def generate_embedding(text: str) -> Optional[List[float]]:
    """
    Generate embedding using available provider.

    Tries Grok first (Llama 4), falls back to Gemini.
    """
    # Try Grok first (uses same API key as chat)
    grok_key = settings.grok_api_key or settings.xai_api_key
    if grok_key:
        embedding = await generate_embedding_grok(text)
        if embedding:
            return embedding

    # Fall back to Gemini
    if settings.google_ai_api_key:
        embedding = await generate_embedding_gemini(text)
        if embedding:
            return embedding

    logger.warning("No embedding API available (set GROK_API_KEY or GOOGLE_AI_API_KEY)")
    return None


# =============================================================================
# Document Management
# =============================================================================

async def ingest_document(
    db: AsyncSession,
    title: str,
    content: str,
    category: KnowledgeCategory,
    source: Optional[str] = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> Optional[HQKnowledgeDocument]:
    """
    Ingest a document into the knowledge base.

    1. Creates the document record
    2. Chunks the content
    3. Generates embeddings for each chunk
    4. Stores chunks with embeddings

    Args:
        db: Database session
        title: Document title
        content: Full document content
        category: Knowledge category
        source: Source of the document
        chunk_size: Size of chunks
        chunk_overlap: Overlap between chunks

    Returns:
        The created document, or None if failed
    """
    try:
        # Create document
        doc = HQKnowledgeDocument(
            id=str(uuid.uuid4()),
            title=title,
            category=category,
            source=source,
            content=content,
            created_at=datetime.utcnow(),
        )
        db.add(doc)
        await db.flush()

        # Chunk the content
        chunks = chunk_text(content, chunk_size, chunk_overlap)
        logger.info(f"Document '{title}' split into {len(chunks)} chunks")

        # Create chunks with embeddings
        for i, chunk_text_content in enumerate(chunks):
            # Generate embedding
            embedding = await generate_embedding(chunk_text_content)

            chunk = HQKnowledgeChunk(
                id=str(uuid.uuid4()),
                document_id=doc.id,
                chunk_index=i,
                content=chunk_text_content,
                embedding=embedding,
                category=category,
                created_at=datetime.utcnow(),
            )
            db.add(chunk)

        await db.commit()
        logger.info(f"Document '{title}' ingested successfully with {len(chunks)} chunks")
        return doc

    except Exception as e:
        logger.error(f"Error ingesting document: {e}")
        await db.rollback()
        return None


async def delete_document(db: AsyncSession, document_id: str) -> bool:
    """Delete a document and all its chunks."""
    try:
        # Delete chunks first
        await db.execute(
            text("DELETE FROM hq_knowledge_chunks WHERE document_id = :doc_id"),
            {"doc_id": document_id}
        )

        # Delete document
        result = await db.execute(
            select(HQKnowledgeDocument).where(HQKnowledgeDocument.id == document_id)
        )
        doc = result.scalar_one_or_none()
        if doc:
            await db.delete(doc)
            await db.commit()
            return True
        return False

    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        await db.rollback()
        return False


# =============================================================================
# Vector Search / Retrieval
# =============================================================================

async def search_knowledge(
    db: AsyncSession,
    query: str,
    categories: Optional[List[KnowledgeCategory]] = None,
    limit: int = 5,
    min_similarity: float = 0.7
) -> List[Dict[str, Any]]:
    """
    Search the knowledge base using vector similarity.

    Args:
        db: Database session
        query: Search query text
        categories: Optional list of categories to filter
        limit: Maximum number of results
        min_similarity: Minimum cosine similarity threshold

    Returns:
        List of matching chunks with similarity scores
    """
    # Generate embedding for query
    query_embedding = await generate_embedding(query)
    if not query_embedding:
        logger.warning("Could not generate query embedding")
        return []

    try:
        # Build query with cosine similarity
        # Using pgvector's <=> operator for cosine distance
        # Similarity = 1 - distance

        if categories:
            category_filter = f"AND category IN ({','.join([repr(c.value) for c in categories])})"
        else:
            category_filter = ""

        # Query using raw SQL for pgvector operations
        result = await db.execute(
            text(f"""
                SELECT
                    id,
                    document_id,
                    chunk_index,
                    content,
                    category,
                    1 - (embedding <=> :query_embedding::vector) as similarity
                FROM hq_knowledge_chunks
                WHERE embedding IS NOT NULL
                {category_filter}
                ORDER BY embedding <=> :query_embedding::vector
                LIMIT :limit
            """),
            {
                "query_embedding": str(query_embedding),
                "limit": limit
            }
        )

        rows = result.fetchall()

        # Filter by minimum similarity and format results
        results = []
        for row in rows:
            similarity = row[5] if row[5] else 0
            if similarity >= min_similarity:
                results.append({
                    "chunk_id": row[0],
                    "document_id": row[1],
                    "chunk_index": row[2],
                    "content": row[3],
                    "category": row[4],
                    "similarity": similarity,
                })

        logger.info(f"Knowledge search found {len(results)} results for query: {query[:50]}...")
        return results

    except Exception as e:
        logger.error(f"Error searching knowledge base: {e}")
        return []


async def get_context_for_agent(
    db: AsyncSession,
    query: str,
    agent_type: str,
    limit: int = 5
) -> str:
    """
    Get relevant context from knowledge base for an agent.

    Args:
        db: Database session
        query: The user's query/task
        agent_type: The agent type (oracle, sentinel, nexus)
        limit: Maximum chunks to retrieve

    Returns:
        Formatted context string to include in agent prompt
    """
    # Map agent types to relevant categories
    agent_categories = {
        "oracle": [
            KnowledgeCategory.ACCOUNTING,
            KnowledgeCategory.TAXES,
            KnowledgeCategory.MARKETING,
            KnowledgeCategory.OPERATIONS,
        ],
        "sentinel": [
            KnowledgeCategory.COMPLIANCE,
            KnowledgeCategory.HR,
            KnowledgeCategory.TAXES,
        ],
        "nexus": [
            KnowledgeCategory.OPERATIONS,
            KnowledgeCategory.COMPLIANCE,
        ],
    }

    categories = agent_categories.get(agent_type, None)

    # Search knowledge base
    results = await search_knowledge(
        db, query, categories=categories, limit=limit, min_similarity=0.6
    )

    if not results:
        return ""

    # Format context
    context_parts = ["## Relevant Knowledge from Knowledge Base:\n"]

    for i, result in enumerate(results, 1):
        context_parts.append(f"### Source {i} (similarity: {result['similarity']:.2f})")
        context_parts.append(f"Category: {result['category']}")
        context_parts.append(f"{result['content']}\n")

    return "\n".join(context_parts)


# =============================================================================
# Utility Functions
# =============================================================================

async def get_knowledge_stats(db: AsyncSession) -> Dict[str, Any]:
    """Get statistics about the knowledge base."""
    try:
        # Count documents by category
        doc_result = await db.execute(
            text("""
                SELECT category, COUNT(*) as count
                FROM hq_knowledge_documents
                GROUP BY category
            """)
        )
        doc_counts = {row[0]: row[1] for row in doc_result.fetchall()}

        # Count chunks
        chunk_result = await db.execute(
            text("SELECT COUNT(*) FROM hq_knowledge_chunks")
        )
        total_chunks = chunk_result.scalar()

        # Count embedded chunks
        embedded_result = await db.execute(
            text("SELECT COUNT(*) FROM hq_knowledge_chunks WHERE embedding IS NOT NULL")
        )
        embedded_chunks = embedded_result.scalar()

        return {
            "total_documents": sum(doc_counts.values()),
            "documents_by_category": doc_counts,
            "total_chunks": total_chunks,
            "embedded_chunks": embedded_chunks,
        }

    except Exception as e:
        logger.error(f"Error getting knowledge stats: {e}")
        return {}
