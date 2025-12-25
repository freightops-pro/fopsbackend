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
from app.models.hq_lead import HQLead, LeadStatus

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

                # Auto-enrich the new leads
                if leads:
                    lead_ids = [l.id for l in leads]
                    enriched, enrich_errors = await lead_service.enrich_leads_batch(lead_ids)
                    total_enriched += len(enriched)

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

        # Auto-enrich
        enriched_count = 0
        if leads:
            lead_ids = [l.id for l in leads]
            enriched, _ = await lead_service.enrich_leads_batch(lead_ids)
            enriched_count = len(enriched)

        return {
            "state": state,
            "imported": len(leads),
            "enriched": enriched_count,
            "duplicates": len([e for e in errors if "Already exists" in e.get("error", "")]),
            "errors": len([e for e in errors if "Already exists" not in e.get("error", "")]),
        }


async def ai_nurture_leads() -> None:
    """
    AI-powered autonomous lead nurturing.

    This job:
    1. Finds leads needing attention (new, stale, or needing qualification)
    2. Uses AI to analyze each lead and determine next action
    3. Auto-qualifies leads based on fit criteria
    4. Prepares personalized outreach for sales reps
    5. Updates lead status and notes with AI insights
    """
    async with AsyncSessionFactory() as session:
        llm = LLMRouter()
        lead_service = HQLeadService(session)

        # Find leads needing AI attention
        cutoff_time = datetime.utcnow() - timedelta(hours=AI_NURTURING_CONFIG["min_hours_between_touches"])

        # Get new leads without contact info, or leads needing qualification
        result = await session.execute(
            select(HQLead)
            .where(
                and_(
                    HQLead.status.in_([LeadStatus.NEW, LeadStatus.CONTACTED]),
                    # Avoid leads we just touched
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

        qualified_count = 0
        enriched_count = 0
        outreach_prepared = 0

        for lead in leads:
            try:
                # Step 1: Enrich if missing contact info
                if not lead.contact_name or not lead.contact_email:
                    enriched = await lead_service.enrich_lead_with_ai(lead.id)
                    if enriched:
                        enriched_count += 1
                        # Refresh lead data
                        await session.refresh(lead)

                # Step 2: AI qualification analysis
                qualification_result = await _ai_qualify_lead(llm, lead)

                if qualification_result:
                    # Update lead based on AI analysis
                    if qualification_result.get("qualified"):
                        lead.status = LeadStatus.QUALIFIED
                        qualified_count += 1
                    elif qualification_result.get("unqualified"):
                        lead.status = LeadStatus.UNQUALIFIED

                    # Add AI analysis to notes
                    ai_notes = []
                    if qualification_result.get("fit_score"):
                        ai_notes.append(f"AI Fit Score: {qualification_result['fit_score']}/10")
                    if qualification_result.get("reasoning"):
                        ai_notes.append(f"AI Analysis: {qualification_result['reasoning']}")
                    if qualification_result.get("suggested_approach"):
                        ai_notes.append(f"Suggested Approach: {qualification_result['suggested_approach']}")
                    if qualification_result.get("talking_points"):
                        ai_notes.append(f"Talking Points: {', '.join(qualification_result['talking_points'])}")

                    if ai_notes:
                        new_notes = "\n".join(ai_notes)
                        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
                        if lead.notes:
                            lead.notes = f"{lead.notes}\n\n--- AI Analysis ({timestamp}) ---\n{new_notes}"
                        else:
                            lead.notes = f"--- AI Analysis ({timestamp}) ---\n{new_notes}"
                        outreach_prepared += 1

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
                "qualified": qualified_count,
                "enriched": enriched_count,
                "outreach_prepared": outreach_prepared,
            }
        )


async def _ai_qualify_lead(llm: LLMRouter, lead: HQLead) -> Optional[dict]:
    """
    Use AI to qualify a lead and prepare outreach strategy.

    Returns qualification analysis including:
    - qualified: bool - is this a good fit?
    - fit_score: int 1-10 - how good is the fit?
    - reasoning: str - why qualified/not
    - suggested_approach: str - how to approach this lead
    - talking_points: list - key points for sales conversation
    """
    system_prompt = """You are an expert sales qualification AI for FreightOps, a TMS (Transportation Management System) software company.

Your job is to analyze trucking company leads and determine:
1. Are they a good fit for our TMS product?
2. How should sales approach them?
3. What are the key talking points?

IDEAL CUSTOMER PROFILE:
- Fleet size: 5-200 trucks (sweet spot: 15-75 trucks)
- Currently using outdated systems or spreadsheets
- Growing companies needing better operations management
- Companies focused on compliance (ELD, IFTA, DOT)
- Regional or OTR carriers

DISQUALIFICATION SIGNALS:
- Very large enterprise fleets (1000+ trucks) - need enterprise sales
- Brokers/3PLs (not carriers) - different product
- Companies already using modern TMS
- Inactive or suspended operating authority

Return ONLY valid JSON:
{
  "qualified": true/false,
  "unqualified": true/false,
  "fit_score": 1-10,
  "reasoning": "explanation",
  "suggested_approach": "how to reach out",
  "talking_points": ["point1", "point2", "point3"],
  "priority": "high/medium/low"
}"""

    user_prompt = f"""Analyze this trucking company lead:

Company: {lead.company_name}
Contact: {lead.contact_name or 'Unknown'} ({lead.contact_title or 'Unknown title'})
Email: {lead.contact_email or 'Unknown'}
Phone: {lead.contact_phone or 'Unknown'}
Fleet Size: {lead.estimated_trucks or 'Unknown'} trucks
Estimated MRR: ${lead.estimated_mrr or 0}
Source: {lead.source.value if lead.source else 'Unknown'}
Notes: {lead.notes or 'None'}

Qualify this lead and provide outreach strategy."""

    try:
        response, _ = await llm.generate(
            agent_role="alex",
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1024
        )

        # Parse JSON response
        response_text = response.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

        return json.loads(response_text)

    except Exception as exc:
        logger.warning(f"AI qualification failed for lead {lead.id}: {str(exc)}")
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
