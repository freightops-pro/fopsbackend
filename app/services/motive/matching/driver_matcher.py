"""Enhanced driver matching service with Motive integration."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.driver import Driver
from app.models.integration import CompanyIntegration, Integration
from app.models.load import Load
from app.schemas.matching import MatchingReason, MatchingSuggestion
from app.services.motive.motive_client import MotiveAPIClient

logger = logging.getLogger(__name__)


class MotiveDriverMatcher:
    """Enhanced driver matcher that uses Motive API data for better matching."""

    def __init__(self, db: AsyncSession):
        """Initialize Motive driver matcher."""
        self.db = db

    async def get_motive_client_for_company(self, company_id: str) -> Optional[MotiveAPIClient]:
        """Get Motive API client for a company if integration exists."""
        try:
            # Find Motive integration for company
            result = await self.db.execute(
                select(CompanyIntegration)
                .join(Integration)
                .where(
                    CompanyIntegration.company_id == company_id,
                    Integration.integration_key == "motive",
                    CompanyIntegration.status == "active",
                )
            )
            integration = result.scalar_one_or_none()
            if not integration or not integration.credentials:
                return None

            credentials = integration.credentials
            client_id = credentials.get("client_id")
            client_secret = credentials.get("client_secret")

            if not client_id or not client_secret:
                return None

            return MotiveAPIClient(client_id, client_secret)
        except Exception as e:
            logger.error(f"Error getting Motive client: {e}")
            return None

    async def enhance_matching_with_motive(
        self,
        company_id: str,
        load: Load,
        driver_suggestions: List[MatchingSuggestion],
    ) -> List[MatchingSuggestion]:
        """
        Enhance driver matching suggestions with Motive data.

        Args:
            company_id: Company ID
            load: Load to match
            driver_suggestions: Initial matching suggestions

        Returns:
            Enhanced matching suggestions with Motive data
        """
        client = await self.get_motive_client_for_company(company_id)
        if not client:
            # No Motive integration, return suggestions as-is
            return driver_suggestions

        try:
            # Get Motive data for all drivers
            motive_data = await self._fetch_motive_data(client, company_id, load)

            # Enhance each suggestion with Motive data
            enhanced_suggestions = []
            for suggestion in driver_suggestions:
                enhanced = await self._enhance_single_suggestion(
                    suggestion, driver_suggestions, motive_data, load
                )
                enhanced_suggestions.append(enhanced)

            # Re-sort by enhanced score
            enhanced_suggestions.sort(key=lambda s: s.score, reverse=True)
            return enhanced_suggestions
        except Exception as e:
            logger.error(f"Error enhancing matching with Motive: {e}", exc_info=True)
            # Return original suggestions if Motive enhancement fails
            return driver_suggestions

    async def _fetch_motive_data(
        self, client: MotiveAPIClient, company_id: str, load: Load
    ) -> Dict[str, Dict]:
        """Fetch relevant Motive data for matching."""
        data: Dict[str, Dict] = {}

        try:
            # Get drivers with available time
            available_time_response = await client.get_drivers_with_available_time()
            available_times = available_time_response.get("data", []) or available_time_response.get("drivers", [])

            # Get company drivers HOS
            hos_response = await client.get_company_drivers_hos()
            hos_data = hos_response.get("data", []) or hos_response.get("drivers", [])

            # Get driver performance events (v2)
            performance_response = await client.get_driver_performance_events_v2()
            performance_data = performance_response.get("data", []) or performance_response.get("events", [])

            # Get nearby vehicles if load has pickup location
            nearby_vehicles = []
            if load.stops and len(load.stops) > 0:
                first_stop = load.stops[0]
                if first_stop.latitude and first_stop.longitude:
                    try:
                        nearby_response = await client.get_nearby_vehicles_v2(
                            latitude=first_stop.latitude,
                            longitude=first_stop.longitude,
                            radius=50,  # 50 miles radius
                        )
                        nearby_vehicles = nearby_response.get("data", []) or nearby_response.get("vehicles", [])
                    except Exception as e:
                        logger.warning(f"Error fetching nearby vehicles: {e}")

            # Organize data by driver ID (Motive user ID)
            for driver_data in available_times:
                user_id = driver_data.get("id") or driver_data.get("user_id")
                if user_id:
                    if user_id not in data:
                        data[user_id] = {}
                    data[user_id]["available_time"] = driver_data

            for driver_data in hos_data:
                user_id = driver_data.get("id") or driver_data.get("user_id")
                if user_id:
                    if user_id not in data:
                        data[user_id] = {}
                    data[user_id]["hos"] = driver_data

            for event in performance_data:
                user_id = event.get("driver_id") or event.get("user_id")
                if user_id:
                    if user_id not in data:
                        data[user_id] = {}
                    if "performance" not in data[user_id]:
                        data[user_id]["performance"] = []
                    data[user_id]["performance"].append(event)

            # Map nearby vehicles by driver
            for vehicle in nearby_vehicles:
                driver_id = vehicle.get("driver_id") or vehicle.get("current_driver", {}).get("id")
                if driver_id:
                    if driver_id not in data:
                        data[driver_id] = {}
                    if "nearby_vehicle" not in data[driver_id]:
                        data[driver_id]["nearby_vehicle"] = []
                    data[driver_id]["nearby_vehicle"].append(vehicle)

        except Exception as e:
            logger.error(f"Error fetching Motive data: {e}", exc_info=True)

        return data

    async def _enhance_single_suggestion(
        self,
        suggestion: MatchingSuggestion,
        all_suggestions: List[MatchingSuggestion],
        motive_data: Dict[str, Dict],
        load: Load,
    ) -> MatchingSuggestion:
        """Enhance a single driver suggestion with Motive data."""
        # Find driver to get Motive user ID
        result = await self.db.execute(
            select(Driver).where(Driver.id == suggestion.driver_id)
        )
        driver = result.scalar_one_or_none()
        if not driver:
            return suggestion

        # Get Motive user ID from profile_metadata
        motive_user_id = None
        if driver.profile_metadata:
            motive_user_id = driver.profile_metadata.get("motive_user_id")

        if not motive_user_id:
            return suggestion

        # Get Motive data for this driver
        driver_motive_data = motive_data.get(str(motive_user_id), {})
        if not driver_motive_data:
            return suggestion

        # Enhance score and reasons
        new_score = suggestion.score
        new_reasons = list(suggestion.reasons) if suggestion.reasons else []

        # HOS Availability Bonus
        available_time = driver_motive_data.get("available_time")
        if available_time:
            available_seconds = available_time.get("available_time_seconds", 0)
            if available_seconds > 0:
                # Convert to hours
                available_hours = available_seconds / 3600
                # Bonus for having available time (up to 15 points)
                hos_bonus = min(available_hours / 2, 15)
                new_score += hos_bonus
                new_reasons.append(
                    MatchingReason(
                        label="HOS Availability",
                        detail=f"{available_hours:.1f} hours available",
                        weight=round(hos_bonus, 2),
                    )
                )
            else:
                # Penalty for no available time
                new_score -= 20
                new_reasons.append(
                    MatchingReason(
                        label="No HOS Availability",
                        detail="Driver has no available hours",
                        weight=-20,
                    )
                )

        # HOS Violations Penalty
        hos_data = driver_motive_data.get("hos")
        if hos_data:
            violations = hos_data.get("hos_violations", [])
            if violations:
                violation_count = len(violations)
                violation_penalty = min(violation_count * 5, 25)
                new_score -= violation_penalty
                new_reasons.append(
                    MatchingReason(
                        label="HOS Violations",
                        detail=f"{violation_count} active violation(s)",
                        weight=round(-violation_penalty, 2),
                    )
                )

        # Performance Score Bonus
        performance_events = driver_motive_data.get("performance", [])
        if performance_events:
            # Calculate average performance score
            scores = [
                event.get("score") for event in performance_events if event.get("score") is not None
            ]
            if scores:
                avg_performance = sum(scores) / len(scores)
                # Bonus for good performance (up to 10 points)
                performance_bonus = (avg_performance - 50) / 5  # Scale from 0-100
                performance_bonus = max(0, min(performance_bonus, 10))
                new_score += performance_bonus
                new_reasons.append(
                    MatchingReason(
                        label="Performance Score",
                        detail=f"Avg: {avg_performance:.1f}",
                        weight=round(performance_bonus, 2),
                    )
                )

        # Proximity Bonus
        nearby_vehicles = driver_motive_data.get("nearby_vehicle", [])
        if nearby_vehicles and load.stops and len(load.stops) > 0:
            first_stop = load.stops[0]
            if first_stop.latitude and first_stop.longitude:
                # Find closest vehicle
                closest_distance = None
                for vehicle in nearby_vehicles:
                    vehicle_lat = vehicle.get("latitude")
                    vehicle_lon = vehicle.get("longitude")
                    if vehicle_lat and vehicle_lon:
                        # Simple distance calculation (could use haversine)
                        distance = abs(vehicle_lat - first_stop.latitude) + abs(
                            vehicle_lon - first_stop.longitude
                        )
                        if closest_distance is None or distance < closest_distance:
                            closest_distance = distance

                if closest_distance is not None and closest_distance < 0.5:  # Within ~30 miles
                    proximity_bonus = max(0, 10 - (closest_distance * 20))
                    new_score += proximity_bonus
                    new_reasons.append(
                        MatchingReason(
                            label="Proximity",
                            detail=f"Near pickup location",
                            weight=round(proximity_bonus, 2),
                        )
                    )

        # Ensure score is within bounds
        new_score = max(0.0, min(100.0, new_score))

        # Create enhanced suggestion
        return MatchingSuggestion(
            driver_id=suggestion.driver_id,
            driver_name=suggestion.driver_name,
            truck_id=suggestion.truck_id,
            score=round(new_score, 2),
            reasons=new_reasons,
            eta_available=suggestion.eta_available,
            compliance_score=suggestion.compliance_score,
            average_rating=suggestion.average_rating,
            completed_loads=suggestion.completed_loads,
        )

