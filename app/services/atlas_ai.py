"""Atlas AI - Autonomous Monitoring and Exception Management Agent.

Atlas monitors operations, detects exceptions, tracks performance,
and proactively alerts on issues before they become critical.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.load import Load, LoadStop
from app.models.driver import Driver
from app.services.ai_agent import BaseAIAgent, AITool


class AtlasAI(BaseAIAgent):
    """
    Atlas - Autonomous Monitoring and Exception Management AI Agent.

    Specializes in:
    - Delivery monitoring and ETA tracking
    - Exception detection and categorization
    - Performance metrics calculation
    - Proactive alerting on potential issues
    - Load tracking and status updates
    """

    @property
    def agent_name(self) -> str:
        return "Atlas"

    @property
    def agent_role(self) -> str:
        return """Monitoring and exception management AI specializing in tracking deliveries,
detecting issues before they escalate, calculating performance metrics, and proactively
alerting on potential problems. I monitor all operations 24/7 and surface critical issues."""

    async def register_tools(self):
        """Register all tools Atlas can use."""
        self.tools = [
            # Load Monitoring Tools
            AITool(
                name="get_loads_by_status",
                description="Query loads by status to find active, at-risk, or problem loads",
                parameters={
                    "status": {"type": "string", "description": "Load status: pending, assigned, in_transit, delivered, cancelled"},
                    "limit": {"type": "number", "description": "Maximum number of results (default 20)"},
                },
                function=self._get_loads_by_status
            ),

            AITool(
                name="detect_delivery_exceptions",
                description="Find loads with delivery exceptions, delays, or issues",
                parameters={
                    "hours_threshold": {"type": "number", "description": "Consider loads in transit for more than X hours as potential issues (default 48)"},
                },
                function=self._detect_delivery_exceptions
            ),

            AITool(
                name="check_load_eta",
                description="Check estimated time of arrival and delivery status for a specific load",
                parameters={
                    "load_id": {"type": "string", "description": "Load ID to check"},
                },
                function=self._check_load_eta
            ),

            # Performance Monitoring Tools
            AITool(
                name="calculate_otd_rate",
                description="Calculate on-time delivery rate for a time period",
                parameters={
                    "days_back": {"type": "number", "description": "Number of days to look back (default 7)"},
                },
                function=self._calculate_otd_rate
            ),

            AITool(
                name="get_performance_summary",
                description="Get comprehensive performance summary with key metrics",
                parameters={
                    "period": {"type": "string", "description": "Time period: today, week, month"},
                },
                function=self._get_performance_summary
            ),

            # Alert Tools
            AITool(
                name="create_alert",
                description="Create a high-priority alert for an issue that needs attention",
                parameters={
                    "alert_type": {"type": "string", "description": "Type: delivery_delay, driver_hos, equipment_failure, etc."},
                    "severity": {"type": "string", "description": "Severity: low, medium, high, critical"},
                    "message": {"type": "string", "description": "Alert message"},
                    "entity_id": {"type": "string", "description": "Related load/driver/equipment ID"},
                },
                function=self._create_alert
            ),

            AITool(
                name="check_driver_hos_violations",
                description="Check for drivers approaching or exceeding HOS limits",
                parameters={
                    "hours_threshold": {"type": "number", "description": "Alert if driver has less than X hours available (default 2)"},
                },
                function=self._check_driver_hos_violations
            ),

            # Analysis Tools
            AITool(
                name="identify_problem_lanes",
                description="Identify routes/lanes with consistent performance issues",
                parameters={
                    "min_occurrences": {"type": "number", "description": "Minimum number of issues on a lane to flag it (default 3)"},
                },
                function=self._identify_problem_lanes
            ),
        ]

    # === Tool Implementations ===

    async def _get_loads_by_status(
        self,
        status: str,
        limit: int = 20,
        **kwargs
    ) -> Dict[str, Any]:
        """Query loads by status."""
        try:
            company_id = kwargs.get("company_id", "default")

            query = select(Load).where(
                and_(
                    Load.company_id == company_id,
                    Load.status == status
                )
            ).limit(limit)

            result = await self.db.execute(query)
            loads = result.scalars().all()

            load_list = [
                {
                    "load_id": load.id,
                    "customer": load.customer_name,
                    "status": load.status,
                    "rate": float(load.base_rate),
                    "created_at": load.created_at.isoformat() if load.created_at else None,
                }
                for load in loads
            ]

            return {
                "status": "success",
                "count": len(load_list),
                "loads": load_list,
            }

        except Exception as e:
            return {"error": str(e)}

    async def _detect_delivery_exceptions(
        self,
        hours_threshold: int = 48,
        **kwargs
    ) -> Dict[str, Any]:
        """Find loads with potential delivery exceptions."""
        try:
            company_id = kwargs.get("company_id", "default")

            # Find loads in transit for longer than threshold
            threshold_time = datetime.utcnow() - timedelta(hours=hours_threshold)

            query = select(Load).where(
                and_(
                    Load.company_id == company_id,
                    Load.status == "in_transit",
                    Load.created_at < threshold_time
                )
            ).limit(50)

            result = await self.db.execute(query)
            problem_loads = result.scalars().all()

            exceptions = []
            for load in problem_loads:
                hours_in_transit = (datetime.utcnow() - load.created_at).total_seconds() / 3600 if load.created_at else 0

                exceptions.append({
                    "load_id": load.id,
                    "customer": load.customer_name,
                    "hours_in_transit": round(hours_in_transit, 1),
                    "status": load.status,
                    "issue_type": "potential_delay",
                    "severity": "high" if hours_in_transit > hours_threshold * 1.5 else "medium",
                })

            return {
                "status": "success",
                "exceptions_found": len(exceptions),
                "exceptions": exceptions,
                "threshold_hours": hours_threshold,
            }

        except Exception as e:
            return {"error": str(e)}

    async def _check_load_eta(
        self,
        load_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Check ETA and delivery status for a load."""
        try:
            result = await self.db.execute(select(Load).where(Load.id == load_id))
            load = result.scalar_one_or_none()

            if not load:
                return {"error": f"Load {load_id} not found"}

            # Calculate time in transit
            if load.created_at:
                hours_in_transit = (datetime.utcnow() - load.created_at).total_seconds() / 3600
            else:
                hours_in_transit = 0

            # Estimate ETA (simplified - in production would use GPS/ELD data)
            estimated_hours_remaining = max(0, 24 - hours_in_transit)  # Assume 24hr transit
            eta = datetime.utcnow() + timedelta(hours=estimated_hours_remaining)

            return {
                "load_id": load_id,
                "status": load.status,
                "customer": load.customer_name,
                "hours_in_transit": round(hours_in_transit, 1),
                "estimated_eta": eta.isoformat(),
                "on_time": hours_in_transit < 48,  # Simplified on-time check
            }

        except Exception as e:
            return {"error": str(e)}

    async def _calculate_otd_rate(
        self,
        days_back: int = 7,
        **kwargs
    ) -> Dict[str, Any]:
        """Calculate on-time delivery rate."""
        try:
            company_id = kwargs.get("company_id", "default")
            start_date = datetime.utcnow() - timedelta(days=days_back)

            # Count delivered loads
            delivered_query = select(Load).where(
                and_(
                    Load.company_id == company_id,
                    Load.status == "delivered",
                    Load.created_at >= start_date
                )
            )
            delivered_result = await self.db.execute(delivered_query)
            delivered_loads = delivered_result.scalars().all()

            total_delivered = len(delivered_loads)

            # In production, would check actual delivery times vs. scheduled
            # For now, assume loads delivered in < 48hrs are on-time
            on_time_count = 0
            for load in delivered_loads:
                if load.created_at:
                    hours_to_deliver = (datetime.utcnow() - load.created_at).total_seconds() / 3600
                    if hours_to_deliver < 48:
                        on_time_count += 1

            otd_rate = (on_time_count / total_delivered * 100) if total_delivered > 0 else 0

            return {
                "status": "success",
                "period_days": days_back,
                "total_delivered": total_delivered,
                "on_time_count": on_time_count,
                "otd_rate": round(otd_rate, 1),
                "meets_target": otd_rate >= 95.0,
            }

        except Exception as e:
            return {"error": str(e)}

    async def _get_performance_summary(
        self,
        period: str = "week",
        **kwargs
    ) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        try:
            company_id = kwargs.get("company_id", "default")

            # Determine date range
            if period == "today":
                start_date = datetime.utcnow().replace(hour=0, minute=0, second=0)
            elif period == "week":
                start_date = datetime.utcnow() - timedelta(days=7)
            else:  # month
                start_date = datetime.utcnow() - timedelta(days=30)

            # Count loads by status
            query = select(Load).where(
                and_(
                    Load.company_id == company_id,
                    Load.created_at >= start_date
                )
            )
            result = await self.db.execute(query)
            loads = result.scalars().all()

            status_counts = {}
            for load in loads:
                status_counts[load.status] = status_counts.get(load.status, 0) + 1

            # Calculate OTD rate for period
            days = (datetime.utcnow() - start_date).days or 1
            otd_result = await self._calculate_otd_rate(days_back=days, company_id=company_id)

            return {
                "status": "success",
                "period": period,
                "total_loads": len(loads),
                "by_status": status_counts,
                "otd_rate": otd_result.get("otd_rate", 0),
                "active_loads": status_counts.get("in_transit", 0) + status_counts.get("assigned", 0),
            }

        except Exception as e:
            return {"error": str(e)}

    async def _create_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        entity_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a system alert."""
        # In production, this would integrate with notification system
        return {
            "status": "created",
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "entity_id": entity_id,
            "created_at": datetime.utcnow().isoformat(),
        }

    async def _check_driver_hos_violations(
        self,
        hours_threshold: int = 2,
        **kwargs
    ) -> Dict[str, Any]:
        """Check for drivers approaching HOS limits."""
        try:
            company_id = kwargs.get("company_id", "default")

            # Get active drivers
            query = select(Driver).where(
                and_(
                    Driver.company_id == company_id,
                    Driver.status == "active"
                )
            )
            result = await self.db.execute(query)
            drivers = result.scalars().all()

            # In production, would query ELD system for actual HOS data
            # For now, simulate with random availability
            at_risk_drivers = []
            for driver in drivers:
                # Simulate: assume some drivers are low on hours
                # In production, check actual HOS from ELD integration
                simulated_hours_available = 8  # Placeholder

                if simulated_hours_available < hours_threshold:
                    at_risk_drivers.append({
                        "driver_id": driver.id,
                        "name": f"{driver.first_name} {driver.last_name}",
                        "hours_available": simulated_hours_available,
                        "status": "approaching_limit" if simulated_hours_available > 1 else "critical",
                    })

            return {
                "status": "success",
                "drivers_checked": len(drivers),
                "at_risk_count": len(at_risk_drivers),
                "at_risk_drivers": at_risk_drivers[:10],  # Limit to 10 for response size
                "threshold_hours": hours_threshold,
            }

        except Exception as e:
            return {"error": str(e)}

    async def _identify_problem_lanes(
        self,
        min_occurrences: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """Identify routes with recurring issues."""
        try:
            company_id = kwargs.get("company_id", "default")

            # Get all loads from last 30 days
            start_date = datetime.utcnow() - timedelta(days=30)
            query = select(Load).where(
                and_(
                    Load.company_id == company_id,
                    Load.created_at >= start_date
                )
            )
            result = await self.db.execute(query)
            loads = result.scalars().all()

            # Analyze lanes (simplified - in production would analyze actual routes)
            lane_issues = {}
            for load in loads:
                # Create a simple lane identifier
                lane = f"{load.customer_name}"  # Simplified

                # Check if load had issues (status cancelled or long transit)
                has_issue = load.status == "cancelled"
                if load.created_at:
                    hours = (datetime.utcnow() - load.created_at).total_seconds() / 3600
                    if hours > 48 and load.status == "in_transit":
                        has_issue = True

                if has_issue:
                    if lane not in lane_issues:
                        lane_issues[lane] = {"count": 0, "loads": []}
                    lane_issues[lane]["count"] += 1
                    lane_issues[lane]["loads"].append(load.id)

            # Filter lanes with min occurrences
            problem_lanes = {
                lane: data
                for lane, data in lane_issues.items()
                if data["count"] >= min_occurrences
            }

            return {
                "status": "success",
                "lanes_analyzed": len(set(load.customer_name for load in loads)),
                "problem_lanes_found": len(problem_lanes),
                "problem_lanes": problem_lanes,
                "min_occurrences": min_occurrences,
            }

        except Exception as e:
            return {"error": str(e)}
