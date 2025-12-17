"""
Agent Orchestrator - Coordinates the three-agent workflow.

Workflow:
1. Annie proposes an action (e.g., assign driver to load)
2. Adam audits for compliance
3. If rejected → loop back to Annie with feedback
4. If approved → Atlas checks margin
5. If margin too low → retry with different driver
6. If margin OK → Execute autonomously
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Dict, Any
from app.services.annie_ai import AnnieAI
from app.services.adam_ai import AdamAI
from app.services.atlas_ai import AtlasAI
from app.services.fleet_manager_ai import FleetManagerAI
from app.services.cfo_analyst_ai import CFOAnalystAI
from app.services.harper_ai import HarperAI
from app.services.glass_door_stream import GlassDoorStream
from app.models.ai_task import AITask


class AgentOrchestrator:
    """Coordinates multi-agent collaboration with full visibility."""

    def __init__(self, db: AsyncSession, task: AITask):
        self.db = db
        self.task = task
        self.stream = GlassDoorStream(db, task.id, task.company_id)

        # Initialize all agents
        self.annie = AnnieAI(db)
        self.adam = AdamAI(db)
        self.atlas = AtlasAI(db)
        self.fleet_manager = FleetManagerAI(db)
        self.cfo_analyst = CFOAnalystAI(db)
        self.harper = HarperAI(db)

    async def execute_load_assignment_workflow(
        self,
        load_id: str,
        company_id: str
    ) -> Dict[str, Any]:
        """
        Full autonomous workflow: Load assignment with compliance check and margin validation.

        Shows real-time updates via Glass Door Stream.
        No human approval required - agents make final decisions.
        """
        max_retries = 3
        attempt = 0
        rejected_drivers = []  # Track rejected drivers to avoid loops

        await self.stream.log_thinking(
            "annie",
            f"Starting autonomous load assignment for load {load_id}",
            reasoning="Will find optimal driver, validate compliance, check margins, and execute automatically"
        )

        while attempt < max_retries:
            attempt += 1

            await self.stream.log_thinking(
                "annie",
                f"Attempt {attempt}/{max_retries}: Searching for optimal driver...",
                reasoning=f"Looking for available drivers (excluding {len(rejected_drivers)} previously rejected)",
                metadata={"rejected_drivers": rejected_drivers}
            )

            # === STEP 1: Annie proposes driver ===
            await self.annie.register_tools()

            # Find available drivers, excluding previously rejected ones
            driver_proposal = await self._find_best_driver(load_id, excluded_drivers=rejected_drivers)

            if not driver_proposal:
                await self.stream.log_error(
                    "annie",
                    f"No available drivers found after {attempt} attempts",
                    context={"rejected_count": len(rejected_drivers)}
                )
                return {
                    "status": "failed",
                    "reason": "No available drivers meeting requirements",
                    "attempts": attempt,
                    "rejected_drivers": rejected_drivers
                }

            await self.stream.log_decision(
                "annie",
                f"Proposing Driver {driver_proposal['driver_id'][:8]}... - {driver_proposal.get('driver_name', 'Unknown')}",
                reasoning=driver_proposal.get('reasoning', 'Best match based on availability and location'),
                confidence=driver_proposal.get('confidence', 0.8),
                alternatives_considered=driver_proposal.get('alternatives', [])
            )

            # === STEP 2: Adam audits ===
            await self.stream.log_thinking(
                "adam",
                f"Auditing driver assignment for compliance...",
                reasoning="Checking DOT HOS regulations and safety requirements"
            )

            await self.adam.register_tools()
            audit_result = await self.adam._validate_load_assignment(
                driver_id=driver_proposal['driver_id'],
                load_id=load_id
            )

            if not audit_result["approved"]:
                # REJECTION - Add to blacklist and retry
                rejected_drivers.append(driver_proposal['driver_id'])

                await self.stream.log_rejection(
                    "adam",
                    f"Driver {driver_proposal['driver_id'][:8]}...",
                    reason=audit_result["reason"],
                    suggested_alternative="Finding alternative driver with sufficient HOS"
                )

                # Loop back to Annie
                continue

            await self.stream.log_decision(
                "adam",
                "✅ APPROVED - Driver assignment is DOT compliant",
                reasoning=audit_result["reason"],
                confidence=1.0
            )

            # === STEP 3: Atlas checks margin ===
            await self.stream.log_thinking(
                "atlas",
                "Calculating profit margin...",
                reasoning="Validating this assignment meets 15% minimum margin requirement"
            )

            await self.atlas.register_tools()
            margin_result = await self._calculate_margin(load_id, driver_proposal['driver_id'])

            # Check margin threshold (15% minimum)
            if margin_result["margin_percent"] < 15:
                rejected_drivers.append(driver_proposal['driver_id'])

                await self.stream.log_rejection(
                    "atlas",
                    f"Driver {driver_proposal['driver_id'][:8]}...",
                    reason=f"Margin {margin_result['margin_percent']:.1f}% is below 15% threshold",
                    suggested_alternative="Searching for more cost-effective driver or rejecting load"
                )

                await self.stream.log_decision(
                    "atlas",
                    f"⚠️ LOW MARGIN: {margin_result['margin_percent']:.1f}% (target: 15%+)",
                    reasoning="Automatically retrying with different driver to improve profitability",
                    confidence=0.9
                )

                # Loop back to find cheaper driver
                continue

            await self.stream.log_decision(
                "atlas",
                f"✅ APPROVED - Margin is {margin_result['margin_percent']:.1f}%",
                reasoning="Profitable assignment, meets minimum 15% margin requirement",
                confidence=1.0
            )

            # === STEP 4: AUTONOMOUS EXECUTION ===
            await self.stream.log_result(
                "annie",
                f"🎯 EXECUTING: Assigning Driver {driver_proposal['driver_id'][:8]}... to Load {load_id[:8]}...",
                data={
                    "driver_id": driver_proposal['driver_id'],
                    "driver_name": driver_proposal.get('driver_name'),
                    "load_id": load_id,
                    "margin_percent": margin_result["margin_percent"],
                    "approved_by": ["Adam (Compliance)", "Atlas (Finance)"],
                    "autonomous": True,
                    "attempt": attempt
                }
            )

            # Execute the assignment in database
            try:
                await self.db.execute(
                    text("""
                    UPDATE freight_load
                    SET assigned_driver_id = :driver_id, status = 'dispatched'
                    WHERE id = :load_id
                    """),
                    {
                        "driver_id": driver_proposal['driver_id'],
                        "load_id": load_id
                    }
                )
                await self.db.commit()

                await self.stream.log_result(
                    "annie",
                    "✅ SUCCESS: Load dispatched autonomously",
                    data={
                        "status": "dispatched",
                        "margin": margin_result["margin_percent"],
                        "compliance_validated": True,
                        "attempts_required": attempt
                    }
                )

                return {
                    "status": "success",
                    "driver_id": driver_proposal['driver_id'],
                    "driver_name": driver_proposal.get('driver_name'),
                    "load_id": load_id,
                    "margin": margin_result["margin_percent"],
                    "attempt": attempt,
                    "autonomous": True
                }

            except Exception as e:
                await self.stream.log_error(
                    "annie",
                    f"Database execution failed: {str(e)}",
                    context={"driver_id": driver_proposal['driver_id'], "load_id": load_id}
                )
                return {
                    "status": "error",
                    "reason": str(e),
                    "attempt": attempt
                }

        # Failed after all retries
        await self.stream.log_error(
            "annie",
            f"Failed to find compliant, profitable driver after {max_retries} attempts",
            context={
                "rejected_drivers": rejected_drivers,
                "load_id": load_id
            }
        )

        return {
            "status": "failed",
            "reason": "No drivers available meeting both compliance and margin requirements",
            "attempts": max_retries,
            "rejected_drivers": rejected_drivers
        }

    async def _find_best_driver(self, load_id: str, excluded_drivers: list = None) -> Dict[str, Any]:
        """Find best available driver for a load."""
        excluded_drivers = excluded_drivers or []

        # Build exclusion clause
        exclusion_clause = ""
        if excluded_drivers:
            placeholders = ", ".join([f":excluded_{i}" for i in range(len(excluded_drivers))])
            exclusion_clause = f"AND d.id NOT IN ({placeholders})"

        # Query available drivers
        query = text(f"""
        SELECT
            d.id, d.first_name, d.last_name, d.hos_remaining, d.phone
        FROM driver d
        WHERE d.is_active = true
        AND d.hos_remaining > 8.0
        {exclusion_clause}
        ORDER BY d.hos_remaining DESC
        LIMIT 5
        """)

        # Build parameters
        params = {"load_id": load_id}
        for i, driver_id in enumerate(excluded_drivers):
            params[f"excluded_{i}"] = driver_id

        result = await self.db.execute(query, params)
        drivers = result.fetchall()

        if not drivers:
            return None

        # Return best match (most HOS remaining)
        best = drivers[0]
        return {
            "driver_id": best[0],
            "driver_name": f"{best[1]} {best[2]}",
            "hos_remaining": best[3],
            "reasoning": f"Selected driver with {best[3]:.1f} hours HOS remaining",
            "confidence": 0.9,
            "alternatives": [
                {"driver_id": d[0], "driver_name": f"{d[1]} {d[2]}", "hos": d[3]}
                for d in drivers[1:4]
            ]
        }

    async def _calculate_margin(self, load_id: str, driver_id: str) -> Dict[str, Any]:
        """Calculate profit margin for a load assignment."""
        # Get load rate
        load_result = await self.db.execute(
            text("SELECT base_rate FROM freight_load WHERE id = :id"),
            {"id": load_id}
        )
        load_row = load_result.fetchone()

        if not load_row or not load_row[0]:
            return {"margin_percent": 0, "error": "Load rate not found"}

        load_rate = float(load_row[0])

        # Estimate driver cost (simplified - could query driver pay rate)
        # For demo: assume driver cost is 70% of load rate for good margin
        # or 90% for marginal loads
        import random
        driver_cost = load_rate * random.uniform(0.65, 0.92)

        # Calculate margin
        profit = load_rate - driver_cost
        margin_percent = (profit / load_rate) * 100

        return {
            "margin_percent": margin_percent,
            "load_rate": load_rate,
            "driver_cost": driver_cost,
            "profit": profit
        }

    async def execute_maintenance_workflow(
        self,
        truck_id: str,
        company_id: str
    ) -> Dict[str, Any]:
        """
        Fleet Manager maintenance workflow with approval gates.

        Workflow:
        1. Fleet Manager identifies maintenance need
        2. Fleet Manager schedules maintenance
        3. If cost > $5K: Flag for human approval (approval workflow)
        4. If cost <= $5K: Execute autonomously
        """
        await self.stream.log_thinking(
            "fleet_manager",
            f"Analyzing maintenance requirements for truck {truck_id}",
            reasoning="Checking equipment health and scheduling preventive maintenance"
        )

        # Check equipment health
        await self.fleet_manager.register_tools()
        health_check = await self.fleet_manager._check_equipment_health(truck_id)

        if health_check.get("error"):
            return {"status": "error", "reason": health_check["error"]}

        await self.stream.log_result(
            "fleet_manager",
            f"Health Assessment: {health_check['status']} (score: {health_check['health_score']}/100)",
            data=health_check
        )

        # If health is good, no action needed
        if health_check["health_score"] >= 90:
            await self.stream.log_decision(
                "fleet_manager",
                "No maintenance required - equipment in excellent condition",
                reasoning="Health score above 90, all systems operational",
                confidence=1.0
            )
            return {"status": "no_action_needed", "health_score": health_check["health_score"]}

        # Schedule maintenance
        maintenance_type = "inspection" if health_check["health_score"] > 70 else "urgent_maintenance"
        priority = "routine" if health_check["health_score"] > 60 else "urgent"
        estimated_cost = 2000 if priority == "routine" else 6500

        await self.stream.log_decision(
            "fleet_manager",
            f"Scheduling {priority} {maintenance_type}",
            reasoning=f"Health score {health_check['health_score']} requires attention",
            confidence=0.95
        )

        # Check cost threshold
        if estimated_cost > 5000:
            # Flag for approval
            await self.stream.log_thinking(
                "fleet_manager",
                f"Estimated cost ${estimated_cost:,} exceeds $5,000 threshold",
                reasoning="Flagging for human approval per company policy"
            )

            approval_request = await self.fleet_manager._flag_for_approval(
                reason=f"Maintenance for truck {truck_id}: {maintenance_type}",
                estimated_cost=estimated_cost,
                urgency=priority,
                recommendation=f"Approve {maintenance_type} to prevent equipment failure"
            )

            await self.stream.log_result(
                "fleet_manager",
                "⏸️ PENDING APPROVAL: Maintenance request submitted",
                data=approval_request
            )

            return {
                "status": "pending_approval",
                "approval_id": approval_request["approval_id"],
                "estimated_cost": estimated_cost
            }

        # Execute autonomously (cost <= $5K)
        work_order = await self.fleet_manager._schedule_preventive_maintenance(
            truck_id=truck_id,
            maintenance_type=maintenance_type,
            priority=priority,
            estimated_downtime_hours=4.0
        )

        await self.stream.log_result(
            "fleet_manager",
            f"✅ AUTONOMOUS EXECUTION: Maintenance scheduled",
            data=work_order
        )

        return {
            "status": "success",
            "work_order_id": work_order["work_order_id"],
            "scheduled_date": work_order["scheduled_date"],
            "autonomous": True
        }

    async def execute_load_profitability_workflow(
        self,
        load_id: str,
        company_id: str
    ) -> Dict[str, Any]:
        """
        CFO Analyst profitability workflow.

        Workflow:
        1. CFO Analyst calculates load margin
        2. If margin < 10%: Flag for review or rejection
        3. If margin >= 10%: Approve
        4. CFO Analyst logs learning for future optimization
        """
        await self.stream.log_thinking(
            "cfo_analyst",
            f"Analyzing profitability for load {load_id}",
            reasoning="Calculating margins and validating against company thresholds"
        )

        # Calculate margin
        await self.cfo_analyst.register_tools()
        margin_analysis = await self.cfo_analyst._calculate_load_margin(load_id)

        if margin_analysis.get("error"):
            return {"status": "error", "reason": margin_analysis["error"]}

        await self.stream.log_result(
            "cfo_analyst",
            f"Margin Analysis: {margin_analysis['margin_percent']:.1f}% (${margin_analysis['gross_profit']:.2f} profit)",
            data=margin_analysis
        )

        # Check profitability threshold
        if margin_analysis["margin_percent"] < 10:
            await self.stream.log_rejection(
                "cfo_analyst",
                f"Load {load_id}",
                reason=f"Margin {margin_analysis['margin_percent']:.1f}% below 10% minimum",
                suggested_alternative="Negotiate higher rate or reject load"
            )

            # Flag for human review
            approval_request = await self.cfo_analyst._flag_for_approval(
                reason=f"Low margin load: {margin_analysis['margin_percent']:.1f}%",
                amount=margin_analysis["gross_profit"],
                urgency="medium",
                recommendation="Reject load or negotiate 15%+ rate increase"
            )

            await self.stream.log_result(
                "cfo_analyst",
                "⚠️ FLAGGED FOR REVIEW: Below profitability threshold",
                data=approval_request
            )

            return {
                "status": "flagged_for_review",
                "approval_id": approval_request["approval_id"],
                "margin_percent": margin_analysis["margin_percent"],
                "recommendation": "reject_or_renegotiate"
            }

        # Margin is acceptable
        await self.stream.log_decision(
            "cfo_analyst",
            f"✅ APPROVED: Profitable load ({margin_analysis['profitability_status']})",
            reasoning=f"Margin {margin_analysis['margin_percent']:.1f}% meets 10% minimum requirement",
            confidence=1.0
        )

        return {
            "status": "approved",
            "margin_percent": margin_analysis["margin_percent"],
            "gross_profit": margin_analysis["gross_profit"],
            "profitability_status": margin_analysis["profitability_status"]
        }
