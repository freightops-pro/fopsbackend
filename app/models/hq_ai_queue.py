"""HQ AI Approval Queue models for Level 2 autonomy."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Column, String, Text, DateTime, Enum, ForeignKey, Boolean, Integer, JSON
)
from sqlalchemy.orm import relationship

from app.models.base import Base


class AIActionType(str, PyEnum):
    """Types of AI-generated actions."""
    LEAD_OUTREACH = "lead_outreach"  # Email/call to prospect
    LEAD_QUALIFICATION = "lead_qualification"  # Status change based on analysis
    RATE_NEGOTIATION = "rate_negotiation"  # Counter-offer to broker
    LOAD_ACCEPTANCE = "load_acceptance"  # Accept a load offer
    DRIVER_ASSIGNMENT = "driver_assignment"  # Assign driver to load
    COMPLIANCE_ALERT = "compliance_alert"  # Flag compliance issue
    INVOICE_APPROVAL = "invoice_approval"  # Approve payment


class AIActionRisk(str, PyEnum):
    """Risk levels for AI actions."""
    LOW = "low"  # Auto-execute (reading, internal updates)
    MEDIUM = "medium"  # Draft & notify (standard actions)
    HIGH = "high"  # Flagged draft (requires approval)
    CRITICAL = "critical"  # Requires manager approval


class AIActionStatus(str, PyEnum):
    """Status of AI-generated action."""
    PENDING = "pending"  # Awaiting human review
    APPROVED = "approved"  # Human approved, executed
    APPROVED_WITH_EDITS = "approved_with_edits"  # Human edited then approved
    REJECTED = "rejected"  # Human rejected
    AUTO_EXECUTED = "auto_executed"  # Low risk, executed automatically
    EXPIRED = "expired"  # Timed out without action


class HQAIAction(Base):
    """
    AI-generated action pending approval.

    Level 2 Autonomy: AI drafts actions, humans approve/edit/reject.
    System learns from human edits to improve over time.
    """
    __tablename__ = "hq_ai_actions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Action details
    action_type = Column(Enum(AIActionType), nullable=False)
    risk_level = Column(Enum(AIActionRisk), nullable=False, default=AIActionRisk.MEDIUM)
    status = Column(Enum(AIActionStatus), nullable=False, default=AIActionStatus.PENDING)

    # What agent created this
    agent_name = Column(String(50), nullable=False)  # "alex", "annie", "adam", etc.

    # Title/summary for the approval queue
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # The actual draft content (email body, counter-offer, etc.)
    draft_content = Column(Text, nullable=True)

    # AI's reasoning for this action
    ai_reasoning = Column(Text, nullable=True)

    # Related entity (lead_id, load_id, etc.)
    entity_type = Column(String(50), nullable=True)  # "lead", "load", "carrier"
    entity_id = Column(String(36), nullable=True)
    entity_name = Column(String(255), nullable=True)  # For display

    # Risk assessment data
    risk_factors = Column(JSON, nullable=True)  # {"fleet_size": 50, "new_entrant": false}

    # Who should review this
    assigned_to_id = Column(String(36), ForeignKey("hq_employee.id"), nullable=True)

    # Human action
    reviewed_by_id = Column(String(36), ForeignKey("hq_employee.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    human_edits = Column(Text, nullable=True)  # What the human changed
    rejection_reason = Column(Text, nullable=True)

    # Learning metrics
    was_edited = Column(Boolean, default=False)  # Did human edit before approve?
    edit_similarity_score = Column(Integer, nullable=True)  # 0-100, how similar to original

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # Auto-expire if not reviewed
    executed_at = Column(DateTime, nullable=True)

    # Relationships
    assigned_to = relationship(
        "HQEmployee",
        foreign_keys=[assigned_to_id],
        backref="assigned_ai_actions"
    )
    reviewed_by = relationship(
        "HQEmployee",
        foreign_keys=[reviewed_by_id],
        backref="reviewed_ai_actions"
    )

    def __repr__(self):
        return f"<HQAIAction {self.id} - {self.action_type.value} - {self.status.value}>"


class HQAIAutonomyRule(Base):
    """
    Rules that define when AI can act autonomously vs. require approval.

    These are the "Logic Gates" that govern Level 2/3 autonomy.
    """
    __tablename__ = "hq_ai_autonomy_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # What action this rule applies to
    action_type = Column(Enum(AIActionType), nullable=False)
    agent_name = Column(String(50), nullable=False)

    # Rule name and description
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # The condition (evaluated against entity data)
    # e.g., "fleet_size > 20" or "is_new_entrant == true"
    condition_field = Column(String(100), nullable=False)
    condition_operator = Column(String(20), nullable=False)  # >, <, ==, !=, in, contains
    condition_value = Column(String(255), nullable=False)

    # What risk level to assign if condition matches
    resulting_risk = Column(Enum(AIActionRisk), nullable=False)

    # Is this rule active?
    is_active = Column(Boolean, default=True)

    # Priority (higher = evaluated first)
    priority = Column(Integer, default=0)

    # Learning: success rate tracking for Level 3 promotion
    total_actions = Column(Integer, default=0)
    approved_without_edits = Column(Integer, default=0)
    approved_with_edits = Column(Integer, default=0)
    rejected = Column(Integer, default=0)

    # If success rate hits threshold, can auto-promote to Level 3
    auto_promote_threshold = Column(Integer, default=95)  # 95% approval rate
    is_level_3_enabled = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def success_rate(self) -> float:
        """Calculate approval rate without edits."""
        if self.total_actions == 0:
            return 0.0
        return (self.approved_without_edits / self.total_actions) * 100

    def should_promote_to_level_3(self) -> bool:
        """Check if this rule should be promoted to autonomous execution."""
        if self.total_actions < 100:  # Need minimum sample size
            return False
        return self.success_rate() >= self.auto_promote_threshold

    def __repr__(self):
        return f"<HQAIAutonomyRule {self.name} - {self.action_type.value}>"
