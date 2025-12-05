from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.driver import Driver, DriverIncident
from app.models.load import Load
from app.schemas.matching import MatchingReason, MatchingResponse, MatchingSuggestion
from app.services.motive.matching.driver_matcher import MotiveDriverMatcher


class MatchingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def suggest(self, company_id: str, load_id: str, limit: int = 5) -> MatchingResponse:
        load = await self._load(company_id, load_id)
        drivers = await self._drivers(company_id)

        suggestions: List[MatchingSuggestion] = []

        for driver in drivers:
            reasons: List[MatchingReason] = []
            score = 50.0  # baseline

            # Compliance + performance heuristics
            if driver.compliance_score is not None:
                compliance_bonus = (driver.compliance_score - 0.5) * 20
                score += compliance_bonus
                reasons.append(
                    MatchingReason(
                        label="Compliance score",
                        detail=f"{driver.compliance_score:.2f}",
                        weight=round(compliance_bonus, 2),
                    )
                )

            if driver.average_rating is not None:
                rating_bonus = (driver.average_rating - 4) * 10
                score += rating_bonus
                reasons.append(
                    MatchingReason(label="Driver rating", detail=f"{driver.average_rating:.2f}", weight=round(rating_bonus, 2))
                )

            if driver.total_completed_loads:
                experience_bonus = min(driver.total_completed_loads, 500) / 25
                score += experience_bonus
                reasons.append(
                    MatchingReason(
                        label="Experience",
                        detail=f"{int(driver.total_completed_loads)} loads completed",
                        weight=round(experience_bonus, 2),
                    )
                )

            # Preferred driver boost
            preferred_drivers = getattr(load, "preferred_driver_ids", None) or []
            if driver.id in preferred_drivers:
                score += 15
                reasons.append(MatchingReason(label="Preferred driver", detail="Listed on load preferences", weight=15))

            # Required skills match vs penalty
            required_skills = set(getattr(load, "required_skills", []) or [])
            driver_skills = set(((driver.preference_profile or {}).get("skills") or []))
            if required_skills:
                matched = required_skills & driver_skills
                if matched:
                    bonus = min(len(matched) * 5, 15)
                    score += bonus
                    reasons.append(MatchingReason(label="Skill match", detail=", ".join(sorted(matched)), weight=bonus))
                else:
                    score -= 20
                    reasons.append(MatchingReason(label="Missing required skills", weight=-20))

            # Incident penalties
            incident_penalty = 0.0
            for incident in driver.incidents or []:
                months_ago = (datetime.utcnow() - incident.occurred_at).days / 30 if incident.occurred_at else 12
                severity_penalty = {"LOW": 2, "MEDIUM": 5, "HIGH": 10, "CRITICAL": 15}.get(incident.severity.upper(), 5)
                decay = max(0.2, 1 - months_ago / 24)
                incident_penalty += severity_penalty * decay
            if incident_penalty:
                score -= incident_penalty
                reasons.append(
                    MatchingReason(
                        label="Recent incidents",
                        detail=f"-{incident_penalty:.1f} risk",
                        weight=round(-incident_penalty, 1),
                    )
                )

            score = max(0.0, min(100.0, score))

            suggestions.append(
                MatchingSuggestion(
                    driver_id=driver.id,
                    driver_name=f"{driver.first_name} {driver.last_name}".strip(),
                    truck_id=self._select_truck(load),
                    score=round(score, 2),
                    reasons=reasons,
                    eta_available=self._eta(driver),
                    compliance_score=driver.compliance_score,
                    average_rating=driver.average_rating,
                    completed_loads=int(driver.total_completed_loads) if driver.total_completed_loads is not None else None,
                )
            )

        suggestions.sort(key=lambda suggestion: suggestion.score, reverse=True)
        trimmed = suggestions[:limit]

        # Enhance with Motive data if available
        try:
            motive_matcher = MotiveDriverMatcher(self.db)
            enhanced_suggestions = await motive_matcher.enhance_matching_with_motive(
                company_id, load, trimmed
            )
            trimmed = enhanced_suggestions
        except Exception as e:
            # Log but don't fail if Motive enhancement fails
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Motive matching enhancement failed: {e}")

        return MatchingResponse(
            load_id=load.id,
            generated_at=datetime.utcnow(),
            suggestions=trimmed,
        )

    async def _load(self, company_id: str, load_id: str) -> Load:
        result = await self.db.execute(
            select(Load)
            .where(Load.company_id == company_id, Load.id == load_id)
            .options(selectinload(Load.stops))
        )
        load = result.scalar_one_or_none()
        if not load:
            raise ValueError("Load not found")
        return load

    async def _drivers(self, company_id: str) -> List[Driver]:
        result = await self.db.execute(
            select(Driver)
            .where(Driver.company_id == company_id)
            .options(selectinload(Driver.incidents))
        )
        return list(result.scalars().all())

    def _select_truck(self, load: Load) -> str | None:
        """Get preferred truck ID from load metadata or return None."""
        preferred = (getattr(load, "preferred_truck_ids", None) or [])
        if preferred:
            return preferred[0]
        # Check metadata for assigned truck
        if load.metadata_json and "assigned_truck_id" in load.metadata_json:
            return load.metadata_json.get("assigned_truck_id")
        return None

    def _eta(self, driver: Driver) -> datetime:
        availability = (driver.preference_profile or {}).get("available_at")
        if availability:
            try:
                return datetime.fromisoformat(availability)
            except ValueError:
                pass
        return datetime.utcnow() + timedelta(hours=4)

