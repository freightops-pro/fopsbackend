"""HQ AI Approval Queue service for Level 2 autonomy."""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from difflib import SequenceMatcher

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hq_ai_queue import (
    HQAIAction, HQAIAutonomyRule,
    AIActionType, AIActionRisk, AIActionStatus
)

logger = logging.getLogger(__name__)


class HQAIQueueService:
    """
    Service for managing AI-generated actions in the approval queue.

    Level 2 Autonomy Protocol:
    1. AI drafts actions with risk assessment
    2. Low risk = auto-execute, Medium/High = queue for approval
    3. Humans approve/edit/reject
    4. System learns from edits to improve over time
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Risk Assessment - The "Logic Gate"
    # =========================================================================

    async def assess_risk(
        self,
        action_type: AIActionType,
        agent_name: str,
        entity_data: dict,
    ) -> Tuple[AIActionRisk, List[dict]]:
        """
        Assess risk level for an action based on autonomy rules.

        Args:
            action_type: Type of action being taken
            agent_name: Which AI agent is acting
            entity_data: Data about the entity (lead, load, etc.)

        Returns:
            Tuple of (risk_level, list of matched rules)
        """
        # Get active rules for this action type
        result = await self.db.execute(
            select(HQAIAutonomyRule)
            .where(
                and_(
                    HQAIAutonomyRule.action_type == action_type,
                    HQAIAutonomyRule.agent_name == agent_name,
                    HQAIAutonomyRule.is_active == True,
                )
            )
            .order_by(HQAIAutonomyRule.priority.desc())
        )
        rules = result.scalars().all()

        matched_rules = []
        highest_risk = AIActionRisk.LOW  # Default to low risk

        for rule in rules:
            if self._evaluate_rule(rule, entity_data):
                matched_rules.append({
                    "rule_id": rule.id,
                    "name": rule.name,
                    "condition": f"{rule.condition_field} {rule.condition_operator} {rule.condition_value}",
                    "risk": rule.resulting_risk.value,
                })

                # Track highest risk level
                risk_order = [AIActionRisk.LOW, AIActionRisk.MEDIUM, AIActionRisk.HIGH, AIActionRisk.CRITICAL]
                if risk_order.index(rule.resulting_risk) > risk_order.index(highest_risk):
                    highest_risk = rule.resulting_risk

        return highest_risk, matched_rules

    def _evaluate_rule(self, rule: HQAIAutonomyRule, entity_data: dict) -> bool:
        """Evaluate if a rule condition matches the entity data."""
        field_value = entity_data.get(rule.condition_field)
        if field_value is None:
            return False

        try:
            op = rule.condition_operator
            target = rule.condition_value

            # Type conversion for comparison
            if isinstance(field_value, (int, float)):
                target = float(target)

            if op == ">":
                return field_value > target
            elif op == "<":
                return field_value < target
            elif op == ">=":
                return field_value >= target
            elif op == "<=":
                return field_value <= target
            elif op == "==":
                return str(field_value).lower() == str(target).lower()
            elif op == "!=":
                return str(field_value).lower() != str(target).lower()
            elif op == "in":
                targets = [t.strip() for t in target.split(",")]
                return str(field_value).lower() in [t.lower() for t in targets]
            elif op == "contains":
                return str(target).lower() in str(field_value).lower()

        except Exception as e:
            logger.warning(f"Rule evaluation error: {e}")

        return False

    # =========================================================================
    # Action Creation
    # =========================================================================

    async def create_action(
        self,
        action_type: AIActionType,
        agent_name: str,
        title: str,
        description: str,
        draft_content: str,
        ai_reasoning: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        entity_name: Optional[str] = None,
        entity_data: Optional[dict] = None,
        assigned_to_id: Optional[str] = None,
        expires_hours: int = 24,
    ) -> HQAIAction:
        """
        Create an AI action in the approval queue.

        Automatically assesses risk and either queues or auto-executes.
        """
        # Assess risk
        entity_data = entity_data or {}
        risk_level, risk_factors = await self.assess_risk(action_type, agent_name, entity_data)

        # Create the action
        action = HQAIAction(
            action_type=action_type,
            agent_name=agent_name,
            risk_level=risk_level,
            title=title,
            description=description,
            draft_content=draft_content,
            ai_reasoning=ai_reasoning,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            risk_factors=risk_factors,
            entity_data=entity_data,  # Store entity data for email details, etc.
            assigned_to_id=assigned_to_id,
            expires_at=datetime.utcnow() + timedelta(hours=expires_hours),
        )

        # Low risk = auto-execute
        if risk_level == AIActionRisk.LOW:
            action.status = AIActionStatus.AUTO_EXECUTED
            action.executed_at = datetime.utcnow()
            logger.info(f"AI Action auto-executed: {action_type.value} - {title}")
        else:
            action.status = AIActionStatus.PENDING
            logger.info(f"AI Action queued for approval: {action_type.value} - {title} (Risk: {risk_level.value})")

        self.db.add(action)
        await self.db.commit()
        await self.db.refresh(action)

        return action

    # =========================================================================
    # Queue Management
    # =========================================================================

    async def get_pending_actions(
        self,
        assigned_to_id: Optional[str] = None,
        action_type: Optional[AIActionType] = None,
        limit: int = 50,
    ) -> List[HQAIAction]:
        """Get pending actions for the approval queue."""
        query = select(HQAIAction).where(
            HQAIAction.status == AIActionStatus.PENDING
        )

        if assigned_to_id:
            query = query.where(HQAIAction.assigned_to_id == assigned_to_id)

        if action_type:
            query = query.where(HQAIAction.action_type == action_type)

        query = query.order_by(
            HQAIAction.risk_level.desc(),  # Critical first
            HQAIAction.created_at.asc(),   # Oldest first
        ).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_action(self, action_id: str) -> Optional[HQAIAction]:
        """Get a specific action by ID."""
        result = await self.db.execute(
            select(HQAIAction).where(HQAIAction.id == action_id)
        )
        return result.scalar_one_or_none()

    # =========================================================================
    # Human Actions (Approve/Edit/Reject)
    # =========================================================================

    async def approve_action(
        self,
        action_id: str,
        reviewed_by_id: str,
        edits: Optional[str] = None,
    ) -> Optional[HQAIAction]:
        """
        Approve an AI action.

        If edits are provided, marks as approved_with_edits and logs
        the similarity score for learning.
        """
        action = await self.get_action(action_id)
        if not action or action.status != AIActionStatus.PENDING:
            return None

        action.reviewed_by_id = reviewed_by_id
        action.reviewed_at = datetime.utcnow()
        action.executed_at = datetime.utcnow()

        if edits:
            action.status = AIActionStatus.APPROVED_WITH_EDITS
            action.human_edits = edits
            action.was_edited = True
            # Calculate similarity score for learning
            action.edit_similarity_score = self._calculate_similarity(
                action.draft_content or "", edits
            )
        else:
            action.status = AIActionStatus.APPROVED
            action.was_edited = False

        # Update autonomy rule statistics
        await self._update_rule_stats(action)

        await self.db.commit()

        logger.info(
            f"AI Action {'approved with edits' if edits else 'approved'}: {action.id}",
            extra={"action_id": action.id, "edited": bool(edits)}
        )

        return action

    async def reject_action(
        self,
        action_id: str,
        reviewed_by_id: str,
        reason: str,
    ) -> Optional[HQAIAction]:
        """Reject an AI action with reason."""
        action = await self.get_action(action_id)
        if not action or action.status != AIActionStatus.PENDING:
            return None

        action.status = AIActionStatus.REJECTED
        action.reviewed_by_id = reviewed_by_id
        action.reviewed_at = datetime.utcnow()
        action.rejection_reason = reason

        # Update autonomy rule statistics
        await self._update_rule_stats(action)

        await self.db.commit()

        logger.info(f"AI Action rejected: {action.id}", extra={"reason": reason})

        return action

    def _calculate_similarity(self, original: str, edited: str) -> int:
        """Calculate text similarity score (0-100)."""
        ratio = SequenceMatcher(None, original, edited).ratio()
        return int(ratio * 100)

    async def _update_rule_stats(self, action: HQAIAction):
        """Update autonomy rule statistics based on action outcome."""
        if not action.risk_factors:
            return

        for factor in action.risk_factors:
            rule_id = factor.get("rule_id")
            if not rule_id:
                continue

            result = await self.db.execute(
                select(HQAIAutonomyRule).where(HQAIAutonomyRule.id == rule_id)
            )
            rule = result.scalar_one_or_none()
            if not rule:
                continue

            rule.total_actions += 1

            if action.status == AIActionStatus.APPROVED:
                rule.approved_without_edits += 1
            elif action.status == AIActionStatus.APPROVED_WITH_EDITS:
                rule.approved_with_edits += 1
            elif action.status == AIActionStatus.REJECTED:
                rule.rejected += 1

            # Check for Level 3 promotion
            if rule.should_promote_to_level_3() and not rule.is_level_3_enabled:
                rule.is_level_3_enabled = True
                logger.info(
                    f"Autonomy rule promoted to Level 3: {rule.name}",
                    extra={"rule_id": rule.id, "success_rate": rule.success_rate()}
                )

    # =========================================================================
    # Queue Statistics
    # =========================================================================

    async def get_queue_stats(self) -> dict:
        """Get statistics about the approval queue."""
        # Pending counts by risk
        result = await self.db.execute(
            select(
                HQAIAction.risk_level,
                func.count(HQAIAction.id)
            )
            .where(HQAIAction.status == AIActionStatus.PENDING)
            .group_by(HQAIAction.risk_level)
        )
        pending_by_risk = {row[0].value: row[1] for row in result.all()}

        # Pending counts by type
        result = await self.db.execute(
            select(
                HQAIAction.action_type,
                func.count(HQAIAction.id)
            )
            .where(HQAIAction.status == AIActionStatus.PENDING)
            .group_by(HQAIAction.action_type)
        )
        pending_by_type = {row[0].value: row[1] for row in result.all()}

        # Today's stats
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        result = await self.db.execute(
            select(
                HQAIAction.status,
                func.count(HQAIAction.id)
            )
            .where(HQAIAction.created_at >= today_start)
            .group_by(HQAIAction.status)
        )
        today_by_status = {row[0].value: row[1] for row in result.all()}

        return {
            "pending_total": sum(pending_by_risk.values()),
            "pending_by_risk": pending_by_risk,
            "pending_by_type": pending_by_type,
            "today_created": sum(today_by_status.values()),
            "today_approved": today_by_status.get("approved", 0) + today_by_status.get("approved_with_edits", 0),
            "today_rejected": today_by_status.get("rejected", 0),
            "today_auto_executed": today_by_status.get("auto_executed", 0),
        }

    # =========================================================================
    # Seed Default Rules
    # =========================================================================

    async def seed_default_rules(self):
        """Create default autonomy rules for lead management."""
        rules = [
            # Lead Outreach Rules
            {
                "action_type": AIActionType.LEAD_OUTREACH,
                "agent_name": "scout",
                "name": "New Entrant - Low Stakes",
                "description": "New carriers (< 30 days) are low risk for outreach",
                "condition_field": "days_since_registration",
                "condition_operator": "<",
                "condition_value": "30",
                "resulting_risk": AIActionRisk.LOW,
                "priority": 10,
            },
            {
                "action_type": AIActionType.LEAD_OUTREACH,
                "agent_name": "scout",
                "name": "Small Fleet - Auto Send",
                "description": "Small fleets (< 20 trucks) are low risk for outreach",
                "condition_field": "fleet_size",
                "condition_operator": "<",
                "condition_value": "20",
                "resulting_risk": AIActionRisk.LOW,
                "priority": 5,
            },
            {
                "action_type": AIActionType.LEAD_OUTREACH,
                "agent_name": "scout",
                "name": "Key Account - Require Approval",
                "description": "Large fleets (20+ trucks) require human approval",
                "condition_field": "fleet_size",
                "condition_operator": ">=",
                "condition_value": "20",
                "resulting_risk": AIActionRisk.HIGH,
                "priority": 20,
            },
            {
                "action_type": AIActionType.LEAD_OUTREACH,
                "agent_name": "scout",
                "name": "Mega Carrier - Critical",
                "description": "Very large fleets (100+ trucks) require manager approval",
                "condition_field": "fleet_size",
                "condition_operator": ">=",
                "condition_value": "100",
                "resulting_risk": AIActionRisk.CRITICAL,
                "priority": 30,
            },
            # Lead Qualification Rules
            {
                "action_type": AIActionType.LEAD_QUALIFICATION,
                "agent_name": "scout",
                "name": "Small Fleet - Auto Qualify",
                "description": "Small fleets can be auto-qualified",
                "condition_field": "fleet_size",
                "condition_operator": "<",
                "condition_value": "10",
                "resulting_risk": AIActionRisk.LOW,
                "priority": 10,
            },
            {
                "action_type": AIActionType.LEAD_QUALIFICATION,
                "agent_name": "scout",
                "name": "High Value Lead",
                "description": "High MRR leads require approval",
                "condition_field": "estimated_mrr",
                "condition_operator": ">=",
                "condition_value": "500",
                "resulting_risk": AIActionRisk.MEDIUM,
                "priority": 15,
            },
        ]

        for rule_data in rules:
            # Check if rule already exists
            result = await self.db.execute(
                select(HQAIAutonomyRule).where(
                    and_(
                        HQAIAutonomyRule.name == rule_data["name"],
                        HQAIAutonomyRule.agent_name == rule_data["agent_name"],
                    )
                )
            )
            if result.scalar_one_or_none():
                continue

            rule = HQAIAutonomyRule(**rule_data)
            self.db.add(rule)

        await self.db.commit()
        logger.info("Default autonomy rules seeded")
