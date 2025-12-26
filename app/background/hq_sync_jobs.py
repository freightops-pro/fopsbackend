"""Background jobs for HQ lead management and FMCSA sync."""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionFactory
from app.core.llm_router import LLMRouter
from app.services.hq_leads import HQLeadService
from app.services.hq_ai_queue import HQAIQueueService
from app.models.hq_lead import HQLead, LeadStatus
from app.models.hq_ai_queue import AIActionType, AIActionRisk

logger = logging.getLogger(__name__)

# Default configuration for FMCSA sync
FMCSA_SYNC_CONFIG = {
    # States to sync (prioritized by trucking industry presence)
    "states": ["TX", "CA", "FL", "IL", "PA", "OH", "GA", "NC", "NJ", "MI"],
    # Fleet size range to target (small to mid-size carriers most likely to need TMS)
    "min_trucks": 5,
    "max_trucks": 100,
    # Max leads per state per sync cycle
    "limit_per_state": 10,
    # System user ID for auto-created leads
    "system_user_id": "system",
}

# AI Lead Nurturing Configuration
AI_NURTURING_CONFIG = {
    # Max leads to process per cycle
    "batch_size": 20,
    # Minimum hours between AI touches on same lead
    "min_hours_between_touches": 4,
}


async def sync_fmcsa_leads() -> None:
    """
    Sync leads from FMCSA Motor Carrier Census data.

    This job runs periodically to import new carriers as leads.
    Leads are distributed round-robin among active sales reps.
    After import, leads are automatically enriched with AI.
    """
    async with AsyncSessionFactory() as session:
        lead_service = HQLeadService(session)

        total_imported = 0
        total_enriched = 0
        total_errors = 0

        for state in FMCSA_SYNC_CONFIG["states"]:
            try:
                # Import leads from FMCSA for this state
                leads, errors = await lead_service.import_leads_from_fmcsa(
                    state=state,
                    min_trucks=FMCSA_SYNC_CONFIG["min_trucks"],
                    max_trucks=FMCSA_SYNC_CONFIG["max_trucks"],
                    limit=FMCSA_SYNC_CONFIG["limit_per_state"],
                    assign_to_sales_rep_id=None,  # Will use round-robin
                    created_by_id=FMCSA_SYNC_CONFIG["system_user_id"],
                    auto_assign_round_robin=True,
                )

                imported_count = len(leads)
                total_imported += imported_count
                total_errors += len([e for e in errors if "Already exists" not in e.get("error", "")])

                # NOTE: Auto-enrichment disabled - sales reps trigger enrichment manually per lead
                # if leads:
                #     lead_ids = [l.id for l in leads]
                #     enriched, enrich_errors = await lead_service.enrich_leads_batch(lead_ids)
                #     total_enriched += len(enriched)

                if imported_count > 0:
                    logger.info(
                        "fmcsa_sync_state_complete",
                        extra={
                            "state": state,
                            "imported": imported_count,
                            "duplicates": len([e for e in errors if "Already exists" in e.get("error", "")]),
                        }
                    )

            except Exception as exc:
                logger.exception(
                    "fmcsa_sync_state_failed",
                    extra={"state": state, "error": str(exc)}
                )
                total_errors += 1

        logger.info(
            "fmcsa_sync_complete",
            extra={
                "total_imported": total_imported,
                "total_enriched": total_enriched,
                "total_errors": total_errors,
            }
        )


async def sync_fmcsa_single_state(
    state: str,
    min_trucks: int = 5,
    max_trucks: int = 100,
    limit: int = 50,
) -> dict:
    """
    On-demand sync for a specific state.

    Returns:
        dict with import statistics
    """
    async with AsyncSessionFactory() as session:
        lead_service = HQLeadService(session)

        leads, errors = await lead_service.import_leads_from_fmcsa(
            state=state,
            min_trucks=min_trucks,
            max_trucks=max_trucks,
            limit=limit,
            assign_to_sales_rep_id=None,
            created_by_id=FMCSA_SYNC_CONFIG["system_user_id"],
            auto_assign_round_robin=True,
        )

        # NOTE: Auto-enrichment disabled - sales reps trigger enrichment manually per lead

        return {
            "state": state,
            "imported": len(leads),
            "enriched": 0,  # No auto-enrichment
            "duplicates": len([e for e in errors if "Already exists" in e.get("error", "")]),
            "errors": len([e for e in errors if "Already exists" not in e.get("error", "")]),
        }


async def ai_nurture_leads() -> None:
    """
    AI-powered autonomous lead nurturing with Level 2 autonomy.

    LEVEL 2 PROTOCOL:
    1. AI analyzes leads and prepares qualification + outreach
    2. Low risk actions (small fleets, new entrants) = auto-execute
    3. Medium/High risk (key accounts, mega carriers) = queue for approval
    4. Humans review, approve/edit/reject in the Approval Queue
    5. System learns from edits to improve over time
    """
    async with AsyncSessionFactory() as session:
        llm = LLMRouter()
        lead_service = HQLeadService(session)
        ai_queue = HQAIQueueService(session)

        # Seed default rules if not exist
        await ai_queue.seed_default_rules()

        # Find leads needing AI attention
        cutoff_time = datetime.utcnow() - timedelta(hours=AI_NURTURING_CONFIG["min_hours_between_touches"])

        # Get new leads without contact info, or leads needing qualification
        result = await session.execute(
            select(HQLead)
            .where(
                and_(
                    HQLead.status.in_([LeadStatus.NEW, LeadStatus.CONTACTED]),
                    HQLead.updated_at < cutoff_time,
                )
            )
            .order_by(HQLead.created_at.desc())
            .limit(AI_NURTURING_CONFIG["batch_size"])
        )
        leads = result.scalars().all()

        if not leads:
            logger.info("ai_nurture_no_leads", extra={"message": "No leads need nurturing"})
            return

        enriched_count = 0
        queued_count = 0
        auto_executed = 0

        outreach_drafted = 0

        for lead in leads:
            try:
                # Step 1: Enrich if missing contact info (always auto-execute)
                if not lead.contact_name or not lead.contact_email:
                    enriched = await lead_service.enrich_lead_with_ai(lead.id)
                    if enriched:
                        enriched_count += 1
                        await session.refresh(lead)

                # Step 2: Scout AI qualification analysis
                qualification_result = await _ai_qualify_lead(llm, lead)

                if qualification_result:
                    # Build entity data for risk assessment
                    fleet_size = int(lead.estimated_trucks or 0) if lead.estimated_trucks else 0
                    entity_data = {
                        "fleet_size": fleet_size,
                        "estimated_mrr": float(lead.estimated_mrr or 0),
                        "is_new_entrant": (datetime.utcnow() - lead.created_at).days < 30,
                        "days_since_registration": (datetime.utcnow() - lead.created_at).days,
                        "has_contact_info": bool(lead.contact_email or lead.contact_phone),
                        "priority": qualification_result.get("priority", "medium"),
                        "fleet_tier": qualification_result.get("fleet_tier", "unknown"),
                    }

                    # Prepare qualification draft content
                    ai_notes = []
                    fit_score = qualification_result.get("fit_score", 0)
                    if fit_score:
                        ai_notes.append(f"Fit Score: {fit_score}/100")
                    if qualification_result.get("fleet_tier"):
                        ai_notes.append(f"Fleet Tier: {qualification_result['fleet_tier']}")
                    if qualification_result.get("priority"):
                        ai_notes.append(f"Priority: {qualification_result['priority'].upper()}")
                    if qualification_result.get("reasoning"):
                        ai_notes.append(f"\nAnalysis: {qualification_result['reasoning']}")
                    if qualification_result.get("buying_signals"):
                        ai_notes.append(f"\nBuying Signals: {', '.join(qualification_result['buying_signals'])}")
                    if qualification_result.get("pain_points"):
                        ai_notes.append(f"\nPain Points: {', '.join(qualification_result['pain_points'])}")
                    if qualification_result.get("talking_points"):
                        ai_notes.append(f"\nTalking Points: {', '.join(qualification_result['talking_points'])}")
                    if qualification_result.get("suggested_approach"):
                        ai_notes.append(f"\nRecommended Approach: {qualification_result['suggested_approach']}")

                    draft_content = "\n".join(ai_notes)
                    new_status = "qualified" if qualification_result.get("qualified") else "unqualified" if qualification_result.get("unqualified") else None

                    # Create qualification action in approval queue
                    action = await ai_queue.create_action(
                        action_type=AIActionType.LEAD_QUALIFICATION,
                        agent_name="scout",
                        title=f"Qualify: {lead.company_name}",
                        description=f"Scout recommends marking as {new_status or 'needs review'}. Fleet: {fleet_size} trucks. Priority: {qualification_result.get('priority', 'medium')}.",
                        draft_content=draft_content,
                        ai_reasoning=qualification_result.get("reasoning", ""),
                        entity_type="lead",
                        entity_id=lead.id,
                        entity_name=lead.company_name,
                        entity_data=entity_data,
                        assigned_to_id=lead.assigned_sales_rep_id,
                    )

                    if action.status.value == "auto_executed":
                        # Low risk - update lead directly
                        if new_status == "qualified":
                            lead.status = LeadStatus.QUALIFIED
                        elif new_status == "unqualified":
                            lead.status = LeadStatus.UNQUALIFIED

                        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
                        if lead.notes:
                            lead.notes = f"{lead.notes}\n\n--- Scout Analysis ({timestamp}) ---\n{draft_content}"
                        else:
                            lead.notes = f"--- Scout Analysis ({timestamp}) ---\n{draft_content}"

                        auto_executed += 1
                    else:
                        queued_count += 1

                    # Step 3: For qualified leads with contact info, draft outreach email
                    if (qualification_result.get("qualified") and
                        lead.contact_email and
                        qualification_result.get("priority") in ["high", "medium"]):

                        outreach_draft = await _ai_draft_outreach(llm, lead, qualification_result)

                        if outreach_draft:
                            # Create outreach action in approval queue
                            outreach_content = f"Subject: {outreach_draft.get('subject', 'N/A')}\n\n{outreach_draft.get('body', '')}"

                            await ai_queue.create_action(
                                action_type=AIActionType.LEAD_OUTREACH,
                                agent_name="scout",
                                title=f"Outreach: {lead.company_name}",
                                description=f"Scout drafted a personalized outreach email. Priority: {qualification_result.get('priority', 'medium')}. Follow-up in {outreach_draft.get('follow_up_days', 3)} days.",
                                draft_content=outreach_content,
                                ai_reasoning=f"Based on qualification analysis: {qualification_result.get('reasoning', 'Lead meets ICP criteria')}",
                                entity_type="lead",
                                entity_id=lead.id,
                                entity_name=lead.company_name,
                                entity_data={
                                    **entity_data,
                                    "email_to": lead.contact_email,
                                    "subject": outreach_draft.get("subject", ""),
                                    "follow_up_days": outreach_draft.get("follow_up_days", 3),
                                    "follow_up_angle": outreach_draft.get("follow_up_angle", ""),
                                },
                                assigned_to_id=lead.assigned_sales_rep_id,
                            )
                            outreach_drafted += 1

                await session.commit()

            except Exception as exc:
                logger.exception(
                    "ai_nurture_lead_failed",
                    extra={"lead_id": lead.id, "error": str(exc)}
                )
                await session.rollback()

        logger.info(
            "ai_nurture_complete",
            extra={
                "processed": len(leads),
                "enriched": enriched_count,
                "auto_executed": auto_executed,
                "queued_for_approval": queued_count,
                "outreach_drafted": outreach_drafted,
            }
        )


async def _ai_qualify_lead(llm: LLMRouter, lead: HQLead) -> Optional[dict]:
    """
    Use Scout AI to qualify a lead and prepare outreach strategy.

    Returns qualification analysis including:
    - qualified: bool - is this a good fit?
    - fit_score: int 1-100 - how good is the fit?
    - reasoning: str - why qualified/not
    - suggested_approach: str - how to approach this lead
    - talking_points: list - key points for sales conversation
    - buying_signals: list - detected signals of purchase readiness
    - pain_points: list - likely pain points to address
    """
    from app.core.agent_prompts import get_agent_prompt

    system_prompt = get_agent_prompt("scout", "system")

    # Determine fleet tier for context
    fleet_size = int(lead.estimated_trucks or 0) if lead.estimated_trucks else 0
    if fleet_size < 5:
        fleet_tier = "micro"
    elif fleet_size <= 20:
        fleet_tier = "small"
    elif fleet_size <= 50:
        fleet_tier = "growth"
    elif fleet_size <= 100:
        fleet_tier = "mid"
    else:
        fleet_tier = "enterprise"

    # Calculate days since registration
    days_since_registration = (datetime.utcnow() - lead.created_at).days

    user_prompt = f"""Analyze this trucking company lead using your qualification criteria:

COMPANY PROFILE:
- Company Name: {lead.company_name}
- DOT Number: {lead.dot_number or 'Unknown'}
- MC Number: {lead.mc_number or 'Unknown'}
- Fleet Size: {lead.estimated_trucks or 'Unknown'} trucks (Tier: {fleet_tier})
- State: {lead.state or 'Unknown'}
- Days Since Added: {days_since_registration}

CONTACT INFO:
- Name: {lead.contact_name or 'Unknown'}
- Title: {lead.contact_title or 'Unknown'}
- Email: {lead.contact_email or 'Not available'}
- Phone: {lead.contact_phone or 'Not available'}

BUSINESS DETAILS:
- Estimated MRR Potential: ${lead.estimated_mrr or 0}
- Lead Source: {lead.source.value if lead.source else 'Unknown'}
- Carrier Type: {lead.carrier_type or 'Unknown'}
- Cargo Types: {lead.cargo_types or 'Unknown'}

EXISTING NOTES:
{lead.notes or 'None'}

Qualify this lead and determine:
1. Is this a good fit for FreightOps TMS?
2. What is their priority level?
3. What pain points should we address?
4. What is the recommended outreach approach?

Return your analysis as JSON."""

    try:
        response, _ = await llm.generate(
            agent_role="scout",
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.4,
            max_tokens=2048
        )

        # Parse JSON response
        response_text = response.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

        return json.loads(response_text)

    except Exception as exc:
        logger.warning(f"Scout qualification failed for lead {lead.id}: {str(exc)}")
        return None


async def _ai_draft_outreach(llm: LLMRouter, lead: HQLead, qualification: dict) -> Optional[dict]:
    """
    Use Scout AI to draft a personalized outreach email for a qualified lead.

    Returns:
    - subject: Email subject line
    - body: Email body content
    - follow_up_days: When to follow up if no response
    - follow_up_angle: Different angle for follow-up
    """
    from app.core.agent_prompts import get_agent_prompt

    outreach_prompt = get_agent_prompt("scout", "outreach")

    fleet_size = lead.estimated_trucks or "unknown"
    pain_points = qualification.get("pain_points", [])
    buying_signals = qualification.get("buying_signals", [])
    recommended_pitch = qualification.get("recommended_pitch", "general TMS benefits")

    user_prompt = f"""Draft a personalized cold outreach email for this lead:

LEAD DETAILS:
- Company: {lead.company_name}
- Contact Name: {lead.contact_name or 'there'}
- Fleet Size: {fleet_size} trucks
- State: {lead.state or 'Unknown'}
- Cargo Types: {lead.cargo_types or 'General freight'}

QUALIFICATION INSIGHTS:
- Pain Points Identified: {', '.join(pain_points) if pain_points else 'General operational challenges'}
- Buying Signals: {', '.join(buying_signals) if buying_signals else 'Fleet size suggests growth stage'}
- Recommended Pitch Angle: {recommended_pitch}
- Priority: {qualification.get('priority', 'medium')}

Write a short, personalized email that:
1. References something specific about their operation
2. Addresses their likely pain point
3. Offers a low-commitment call to discuss
4. Is under 150 words

Return as JSON with subject, body, follow_up_days, and follow_up_angle."""

    try:
        response, _ = await llm.generate(
            agent_role="scout",
            prompt=user_prompt,
            system_prompt=outreach_prompt,
            temperature=0.5,  # Slightly more creative for email writing
            max_tokens=1024
        )

        # Parse JSON response
        response_text = response.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

        return json.loads(response_text)

    except Exception as exc:
        logger.warning(f"Scout outreach draft failed for lead {lead.id}: {str(exc)}")
        return None


async def ai_claim_lead(lead_id: str, sales_rep_id: str) -> Optional[dict]:
    """
    Sales rep claims a lead - removes from shared pool and assigns to rep.

    Returns the claimed lead data.
    """
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(HQLead).where(HQLead.id == lead_id)
        )
        lead = result.scalar_one_or_none()

        if not lead:
            return None

        # Assign to sales rep
        lead.assigned_sales_rep_id = sales_rep_id
        lead.status = LeadStatus.CONTACTED  # Mark as being worked

        await session.commit()

        return {
            "id": lead.id,
            "company_name": lead.company_name,
            "assigned_to": sales_rep_id,
            "status": lead.status.value,
        }
