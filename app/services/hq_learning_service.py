"""
HQ Learning Service - Continuous learning for AI agents.

This service handles:
1. Recording agent interactions for learning
2. Collecting and processing user feedback
3. Detecting knowledge gaps
4. Updating chunk confidence scores
5. Generating learning metrics
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, update, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hq_knowledge_base import (
    HQKnowledgeDocument,
    HQKnowledgeChunk,
    HQAgentInteraction,
    HQKnowledgeFeedback,
    HQKnowledgeGap,
    HQChunkConfidence,
    HQLearningMetrics,
    KnowledgeCategory,
    FeedbackType,
    GapType,
)
from app.services.hq_rag_service import generate_embedding

logger = logging.getLogger(__name__)


# =============================================================================
# Interaction Recording
# =============================================================================

async def record_interaction(
    db: AsyncSession,
    agent_type: str,
    user_query: str,
    retrieved_chunks: List[Dict[str, Any]],
    final_response: str,
    task_id: Optional[str] = None,
    response_time_ms: Optional[int] = None,
    user_context: Optional[Dict] = None,
) -> HQAgentInteraction:
    """
    Record an agent interaction for learning analysis.

    Args:
        db: Database session
        agent_type: Type of agent (oracle, sentinel, nexus)
        user_query: The user's query/task
        retrieved_chunks: List of chunks that were retrieved (with scores)
        final_response: The agent's response
        task_id: Optional link to HQAITask
        response_time_ms: Response latency in milliseconds
        user_context: Additional context
    """
    # Extract chunk IDs and scores
    chunk_ids = [c.get("chunk_id") for c in retrieved_chunks]
    retrieval_scores = [c.get("similarity", 0) for c in retrieved_chunks]

    # Calculate retrieval quality (average of top scores)
    retrieval_quality = sum(retrieval_scores) / len(retrieval_scores) if retrieval_scores else 0

    # Generate query embedding for similarity analysis
    query_embedding = await generate_embedding(user_query)

    interaction = HQAgentInteraction(
        id=str(uuid.uuid4()),
        agent_type=agent_type,
        task_id=task_id,
        user_query=user_query,
        query_embedding=query_embedding,
        retrieved_chunk_ids=json.dumps(chunk_ids),
        retrieval_scores=json.dumps(retrieval_scores),
        final_response=final_response,
        response_length=len(final_response) if final_response else 0,
        retrieval_quality_score=retrieval_quality,
        user_context=json.dumps(user_context) if user_context else None,
        response_time_ms=response_time_ms,
        created_at=datetime.utcnow(),
    )

    db.add(interaction)
    await db.commit()
    await db.refresh(interaction)

    # Update chunk usage stats
    await _update_chunk_usage(db, chunk_ids, retrieval_scores)

    # Check for potential knowledge gaps
    if retrieval_quality < 0.5:
        await _detect_gap_from_interaction(db, interaction, retrieved_chunks)

    logger.info(f"Recorded interaction {interaction.id} for {agent_type}")
    return interaction


async def _update_chunk_usage(
    db: AsyncSession,
    chunk_ids: List[str],
    retrieval_scores: List[float]
):
    """Update chunk usage statistics."""
    for i, chunk_id in enumerate(chunk_ids):
        if not chunk_id:
            continue

        # Get or create confidence record
        result = await db.execute(
            select(HQChunkConfidence).where(HQChunkConfidence.chunk_id == chunk_id)
        )
        confidence = result.scalar_one_or_none()

        if confidence:
            # Update existing
            confidence.usage_count += 1
            confidence.last_used_at = datetime.utcnow()

            # Update average retrieval rank
            new_rank = i + 1  # 1-indexed
            if confidence.avg_retrieval_rank:
                # Running average
                confidence.avg_retrieval_rank = (
                    confidence.avg_retrieval_rank * (confidence.usage_count - 1) + new_rank
                ) / confidence.usage_count
            else:
                confidence.avg_retrieval_rank = new_rank
        else:
            # Create new
            confidence = HQChunkConfidence(
                id=str(uuid.uuid4()),
                chunk_id=chunk_id,
                usage_count=1,
                avg_retrieval_rank=i + 1,
                last_used_at=datetime.utcnow(),
            )
            db.add(confidence)

    await db.commit()


# =============================================================================
# Feedback Collection
# =============================================================================

async def collect_feedback(
    db: AsyncSession,
    interaction_id: str,
    feedback_type: FeedbackType,
    user_rating: Optional[int] = None,
    user_comment: Optional[str] = None,
    suggested_correction: Optional[str] = None,
    feedback_source: str = "user",
) -> HQKnowledgeFeedback:
    """
    Collect user feedback on an agent response.

    Args:
        db: Database session
        interaction_id: ID of the interaction being rated
        feedback_type: Type of feedback (helpful, unhelpful, etc.)
        user_rating: Optional 1-5 rating
        user_comment: Optional comment
        suggested_correction: Optional correction text
        feedback_source: Source of feedback (user, auto, admin)
    """
    # Get interaction to find affected chunks
    result = await db.execute(
        select(HQAgentInteraction).where(HQAgentInteraction.id == interaction_id)
    )
    interaction = result.scalar_one_or_none()

    if not interaction:
        raise ValueError(f"Interaction {interaction_id} not found")

    feedback = HQKnowledgeFeedback(
        id=str(uuid.uuid4()),
        interaction_id=interaction_id,
        feedback_type=feedback_type,
        user_rating=user_rating,
        user_comment=user_comment,
        suggested_correction=suggested_correction,
        affected_chunk_ids=interaction.retrieved_chunk_ids,
        feedback_source=feedback_source,
        created_at=datetime.utcnow(),
    )

    db.add(feedback)
    await db.commit()

    # Process feedback immediately
    await process_feedback(db, feedback)

    logger.info(f"Collected {feedback_type.value} feedback for interaction {interaction_id}")
    return feedback


async def process_feedback(db: AsyncSession, feedback: HQKnowledgeFeedback):
    """Process feedback to update chunk confidence and detect gaps."""
    chunk_ids = json.loads(feedback.affected_chunk_ids or "[]")

    is_positive = feedback.feedback_type == FeedbackType.HELPFUL
    is_negative = feedback.feedback_type in [
        FeedbackType.UNHELPFUL,
        FeedbackType.INACCURATE,
        FeedbackType.INCOMPLETE,
        FeedbackType.OUTDATED,
    ]

    # Update chunk confidence scores
    for chunk_id in chunk_ids:
        await _update_chunk_confidence(db, chunk_id, is_positive, is_negative)

    # If negative feedback, check for knowledge gaps
    if is_negative:
        interaction = await db.get(HQAgentInteraction, feedback.interaction_id)
        if interaction:
            await _detect_gap_from_feedback(db, interaction, feedback)

    # Mark feedback as processed
    feedback.processed = 1
    feedback.processed_at = datetime.utcnow()
    await db.commit()


async def _update_chunk_confidence(
    db: AsyncSession,
    chunk_id: str,
    is_positive: bool,
    is_negative: bool
):
    """Update chunk confidence based on feedback."""
    result = await db.execute(
        select(HQChunkConfidence).where(HQChunkConfidence.chunk_id == chunk_id)
    )
    confidence = result.scalar_one_or_none()

    if not confidence:
        confidence = HQChunkConfidence(
            id=str(uuid.uuid4()),
            chunk_id=chunk_id,
        )
        db.add(confidence)

    if is_positive:
        confidence.helpful_count += 1
    if is_negative:
        confidence.unhelpful_count += 1

    # Recalculate helpfulness ratio
    total = confidence.helpful_count + confidence.unhelpful_count
    if total > 0:
        confidence.helpfulness_ratio = confidence.helpful_count / total

    # Update confidence score (weighted by feedback)
    # Start at 1.0, decay with negative feedback, boost with positive
    base_score = 1.0
    negative_penalty = 0.1 * confidence.unhelpful_count
    positive_boost = 0.05 * confidence.helpful_count
    confidence.confidence_score = max(0.1, min(1.0, base_score - negative_penalty + positive_boost))

    await db.commit()


# =============================================================================
# Gap Detection
# =============================================================================

async def _detect_gap_from_interaction(
    db: AsyncSession,
    interaction: HQAgentInteraction,
    retrieved_chunks: List[Dict[str, Any]]
):
    """Detect knowledge gap from low-quality retrieval."""
    # Determine gap type
    if not retrieved_chunks:
        gap_type = GapType.MISSING_TOPIC
        detection_method = "zero_results"
        confidence = 0.9
    else:
        avg_score = sum(c.get("similarity", 0) for c in retrieved_chunks) / len(retrieved_chunks)
        if avg_score < 0.3:
            gap_type = GapType.MISSING_TOPIC
            detection_method = "very_low_relevance"
            confidence = 0.8
        else:
            gap_type = GapType.LOW_RELEVANCE
            detection_method = "low_relevance"
            confidence = 0.6

    await _create_or_update_gap(
        db,
        gap_type=gap_type,
        topic=interaction.user_query,
        detection_method=detection_method,
        confidence=confidence,
        interaction_id=interaction.id,
    )


async def _detect_gap_from_feedback(
    db: AsyncSession,
    interaction: HQAgentInteraction,
    feedback: HQKnowledgeFeedback
):
    """Detect knowledge gap from negative feedback."""
    gap_type_map = {
        FeedbackType.UNHELPFUL: GapType.LOW_RELEVANCE,
        FeedbackType.INACCURATE: GapType.CONTRADICTION,
        FeedbackType.INCOMPLETE: GapType.INSUFFICIENT_DEPTH,
        FeedbackType.OUTDATED: GapType.OUTDATED,
    }

    gap_type = gap_type_map.get(feedback.feedback_type, GapType.LOW_RELEVANCE)

    await _create_or_update_gap(
        db,
        gap_type=gap_type,
        topic=interaction.user_query,
        detection_method=f"user_feedback_{feedback.feedback_type.value}",
        confidence=0.85 if feedback.user_rating and feedback.user_rating <= 2 else 0.7,
        interaction_id=interaction.id,
    )


async def _create_or_update_gap(
    db: AsyncSession,
    gap_type: GapType,
    topic: str,
    detection_method: str,
    confidence: float,
    interaction_id: str,
):
    """Create a new gap or update existing similar gap."""
    # Generate embedding for topic
    topic_embedding = await generate_embedding(topic)

    # Check for similar existing gaps (by embedding similarity)
    # For now, use simple text matching
    existing = await db.execute(
        select(HQKnowledgeGap).where(
            and_(
                HQKnowledgeGap.status == "open",
                HQKnowledgeGap.topic.ilike(f"%{topic[:50]}%")
            )
        )
    )
    similar_gap = existing.scalar_one_or_none()

    if similar_gap:
        # Update existing gap
        similar_gap.occurrence_count += 1
        similar_gap.last_occurred_at = datetime.utcnow()
        similar_gap.confidence_score = max(similar_gap.confidence_score, confidence)

        # Increase priority based on frequency
        similar_gap.priority_score = min(1.0, similar_gap.priority_score + 0.1)

        # Add interaction ID to related list
        related = json.loads(similar_gap.related_interaction_ids or "[]")
        related.append(interaction_id)
        similar_gap.related_interaction_ids = json.dumps(related[-10:])  # Keep last 10
    else:
        # Create new gap
        gap = HQKnowledgeGap(
            id=str(uuid.uuid4()),
            gap_type=gap_type,
            topic=topic,
            topic_embedding=topic_embedding,
            detection_method=detection_method,
            confidence_score=confidence,
            related_interaction_ids=json.dumps([interaction_id]),
            priority_score=0.5,
            detected_at=datetime.utcnow(),
        )
        db.add(gap)
        logger.info(f"Detected new knowledge gap: {gap_type.value} - {topic[:50]}")

    await db.commit()


async def get_open_gaps(
    db: AsyncSession,
    limit: int = 20,
    min_priority: float = 0.0,
) -> List[HQKnowledgeGap]:
    """Get open knowledge gaps sorted by priority."""
    result = await db.execute(
        select(HQKnowledgeGap)
        .where(
            and_(
                HQKnowledgeGap.status == "open",
                HQKnowledgeGap.priority_score >= min_priority
            )
        )
        .order_by(HQKnowledgeGap.priority_score.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def resolve_gap(
    db: AsyncSession,
    gap_id: str,
    resolution_notes: str,
    resolved_by_document_id: Optional[str] = None,
):
    """Mark a knowledge gap as resolved."""
    gap = await db.get(HQKnowledgeGap, gap_id)
    if gap:
        gap.status = "resolved"
        gap.resolution_notes = resolution_notes
        gap.resolved_by_document_id = resolved_by_document_id
        gap.resolved_at = datetime.utcnow()
        await db.commit()


# =============================================================================
# Learning Metrics
# =============================================================================

async def calculate_daily_metrics(
    db: AsyncSession,
    date: Optional[datetime] = None,
) -> HQLearningMetrics:
    """Calculate learning metrics for a given day."""
    date = date or datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    next_date = date + timedelta(days=1)

    # Count documents and chunks
    doc_count = await db.scalar(
        select(func.count()).select_from(HQKnowledgeDocument)
    )
    chunk_count = await db.scalar(
        select(func.count()).select_from(HQKnowledgeChunk)
    )

    # Average chunk confidence
    avg_confidence = await db.scalar(
        select(func.avg(HQChunkConfidence.confidence_score))
    ) or 1.0

    # Today's interactions
    interactions_today = await db.scalar(
        select(func.count()).select_from(HQAgentInteraction).where(
            and_(
                HQAgentInteraction.created_at >= date,
                HQAgentInteraction.created_at < next_date
            )
        )
    ) or 0

    # Average retrieval quality today
    avg_quality = await db.scalar(
        select(func.avg(HQAgentInteraction.retrieval_quality_score)).where(
            and_(
                HQAgentInteraction.created_at >= date,
                HQAgentInteraction.created_at < next_date
            )
        )
    ) or 0.0

    # Today's feedback
    feedback_result = await db.execute(
        select(
            func.count().label("total"),
            func.sum(
                func.case(
                    (HQKnowledgeFeedback.feedback_type == FeedbackType.HELPFUL, 1),
                    else_=0
                )
            ).label("positive")
        ).where(
            and_(
                HQKnowledgeFeedback.created_at >= date,
                HQKnowledgeFeedback.created_at < next_date
            )
        )
    )
    feedback_row = feedback_result.first()
    feedback_total = feedback_row.total or 0
    feedback_positive = feedback_row.positive or 0
    positive_pct = (feedback_positive / feedback_total * 100) if feedback_total > 0 else 0

    # Average rating
    avg_rating = await db.scalar(
        select(func.avg(HQKnowledgeFeedback.user_rating)).where(
            and_(
                HQKnowledgeFeedback.created_at >= date,
                HQKnowledgeFeedback.created_at < next_date,
                HQKnowledgeFeedback.user_rating.isnot(None)
            )
        )
    )

    # Open gaps
    open_gaps = await db.scalar(
        select(func.count()).select_from(HQKnowledgeGap).where(
            HQKnowledgeGap.status == "open"
        )
    ) or 0

    # Gaps detected today
    gaps_today = await db.scalar(
        select(func.count()).select_from(HQKnowledgeGap).where(
            and_(
                HQKnowledgeGap.detected_at >= date,
                HQKnowledgeGap.detected_at < next_date
            )
        )
    ) or 0

    # Gaps resolved today
    gaps_resolved = await db.scalar(
        select(func.count()).select_from(HQKnowledgeGap).where(
            and_(
                HQKnowledgeGap.resolved_at >= date,
                HQKnowledgeGap.resolved_at < next_date
            )
        )
    ) or 0

    # Knowledge coverage (interactions with quality > 0.7)
    high_quality = await db.scalar(
        select(func.count()).select_from(HQAgentInteraction).where(
            and_(
                HQAgentInteraction.created_at >= date,
                HQAgentInteraction.created_at < next_date,
                HQAgentInteraction.retrieval_quality_score >= 0.7
            )
        )
    ) or 0
    coverage = (high_quality / interactions_today * 100) if interactions_today > 0 else 0

    metrics = HQLearningMetrics(
        id=str(uuid.uuid4()),
        date=date,
        total_documents=doc_count,
        total_chunks=chunk_count,
        avg_chunk_confidence=avg_confidence,
        total_interactions=interactions_today,
        avg_retrieval_quality=avg_quality,
        feedback_received=feedback_total,
        positive_feedback_pct=positive_pct,
        avg_user_rating=avg_rating,
        open_gaps_count=open_gaps,
        gaps_detected=gaps_today,
        gaps_resolved=gaps_resolved,
        knowledge_coverage_pct=coverage,
        created_at=datetime.utcnow(),
    )

    db.add(metrics)
    await db.commit()

    return metrics


async def get_learning_dashboard(db: AsyncSession) -> Dict[str, Any]:
    """Get summary data for learning dashboard."""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)

    # Get recent metrics
    result = await db.execute(
        select(HQLearningMetrics)
        .where(HQLearningMetrics.date >= week_ago)
        .order_by(HQLearningMetrics.date.desc())
    )
    recent_metrics = list(result.scalars().all())

    # Get top gaps
    top_gaps = await get_open_gaps(db, limit=5, min_priority=0.5)

    # Get low confidence chunks
    low_confidence = await db.execute(
        select(HQChunkConfidence)
        .where(HQChunkConfidence.confidence_score < 0.5)
        .order_by(HQChunkConfidence.confidence_score.asc())
        .limit(10)
    )

    # Calculate trends
    if len(recent_metrics) >= 2:
        latest = recent_metrics[0]
        previous = recent_metrics[-1]
        coverage_trend = latest.knowledge_coverage_pct - previous.knowledge_coverage_pct
        quality_trend = latest.avg_retrieval_quality - previous.avg_retrieval_quality
    else:
        coverage_trend = 0
        quality_trend = 0

    return {
        "current_metrics": recent_metrics[0] if recent_metrics else None,
        "metrics_history": [
            {
                "date": m.date.isoformat(),
                "coverage": m.knowledge_coverage_pct,
                "quality": m.avg_retrieval_quality,
                "interactions": m.total_interactions,
                "feedback_positive_pct": m.positive_feedback_pct,
            }
            for m in recent_metrics
        ],
        "trends": {
            "coverage_change": coverage_trend,
            "quality_change": quality_trend,
        },
        "top_gaps": [
            {
                "id": g.id,
                "topic": g.topic[:100],
                "gap_type": g.gap_type.value,
                "priority": g.priority_score,
                "occurrence_count": g.occurrence_count,
            }
            for g in top_gaps
        ],
        "low_confidence_chunks": [
            {
                "chunk_id": c.chunk_id,
                "confidence": c.confidence_score,
                "usage_count": c.usage_count,
                "helpfulness_ratio": c.helpfulness_ratio,
            }
            for c in low_confidence.scalars()
        ],
    }


# =============================================================================
# Staleness Detection
# =============================================================================

async def detect_stale_chunks(
    db: AsyncSession,
    stale_threshold_days: int = 90
) -> List[str]:
    """Detect chunks that haven't been used recently."""
    threshold = datetime.utcnow() - timedelta(days=stale_threshold_days)

    result = await db.execute(
        select(HQChunkConfidence.chunk_id)
        .where(
            or_(
                HQChunkConfidence.last_used_at < threshold,
                HQChunkConfidence.last_used_at.is_(None)
            )
        )
    )
    stale_ids = [row[0] for row in result.all()]

    # Mark as stale
    if stale_ids:
        await db.execute(
            update(HQChunkConfidence)
            .where(HQChunkConfidence.chunk_id.in_(stale_ids))
            .values(is_stale=1)
        )
        await db.commit()

    logger.info(f"Detected {len(stale_ids)} stale chunks")
    return stale_ids
