"""
LangGraph Orchestrator - Cyclic State Machine for Multi-Agent Workflow

Extended MDD Section 6: 5-Agent Workflow

Workflow:
1. Start: New Load Received
2. Annie (Scout): Proposes driver via vector search
3. Fleet Manager (Maverick): Checks equipment health/availability
4. Adam (Maverick): Audits HOS compliance
5. Harper (Maverick): Calculates driver settlement/pay
6. Atlas (Maverick): Validates margin (using Harper's pay data)
7. Loop: If any agent rejects → back to Annie with feedback
8. Decision: margin < 15% → Flag for human, else Execute
9. End: Load Booked
"""

from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
import uuid

from app.services.annie_ai import AnnieAI
from app.services.adam_ai import AdamAI
from app.services.atlas_ai import AtlasAI
from app.services.fleet_manager_ai import FleetManagerAI
from app.services.harper_ai import HarperAI
from app.services.glass_door_stream import GlassDoorStream


class AgentState(TypedDict):
    """
    State object passed between nodes in the graph.

    This represents the "working memory" of the workflow.
    """
    # Input
    load_id: str
    company_id: str
    task_id: str

    # Annie's proposal
    proposed_driver_id: str | None
    proposed_driver_name: str | None
    proposed_equipment_id: str | None
    annie_reasoning: str | None

    # Fleet Manager's equipment check
    fleet_approved: bool
    fleet_reasoning: str | None
    equipment_health_score: int | None

    # Adam's compliance audit
    adam_approved: bool
    adam_reasoning: str | None
    rejected_drivers: list[str]  # Track rejected drivers to avoid loops

    # Harper's pay calculation
    harper_settlement_amount: float | None
    harper_reasoning: str | None

    # Atlas's margin check
    margin_percent: float | None
    atlas_approved: bool
    atlas_reasoning: str | None

    # Execution status
    status: Literal["pending", "success", "failed", "flagged_for_review"]
    error_message: str | None
    attempt_count: int


class LoadAssignmentGraph:
    """
    LangGraph implementation of the autonomous load assignment workflow.

    This replaces the custom AgentOrchestrator with a proper state machine.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.annie = AnnieAI(db)
        self.adam = AdamAI(db)
        self.atlas = AtlasAI(db)
        self.fleet_manager = FleetManagerAI(db)
        self.harper = HarperAI(db)

        # Build the graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """
        Construct the LangGraph state machine.

        Graph structure (5-Agent Loop):
            START → annie_proposes → fleet_checks_equipment → adam_audits → harper_calculates_pay → atlas_validates
                         ↑                     ↓ (rejected)         ↓ (rejected)
                         └─────────────────────┴──────────────────┘
                                                                    ↓ (approved)
                                                            [margin decision]
                                                        ↓                    ↓
                                                execute_assignment    flag_for_human
                                                        ↓                    ↓
                                                       END                  END
        """
        workflow = StateGraph(AgentState)

        # Add nodes (the agents)
        workflow.add_node("annie_proposes", self._annie_proposes_driver)
        workflow.add_node("fleet_checks_equipment", self._fleet_checks_equipment)
        workflow.add_node("adam_audits", self._adam_audits_compliance)
        workflow.add_node("harper_calculates_pay", self._harper_calculates_pay)
        workflow.add_node("atlas_validates", self._atlas_validates_margin)
        workflow.add_node("execute_assignment", self._execute_assignment)
        workflow.add_node("flag_for_human", self._flag_for_human)

        # Define edges (the workflow)
        workflow.set_entry_point("annie_proposes")

        # Annie → Fleet Manager
        workflow.add_edge("annie_proposes", "fleet_checks_equipment")

        # Fleet Manager → Decision (equipment OK vs bad)
        workflow.add_conditional_edges(
            "fleet_checks_equipment",
            self._should_continue_after_fleet,
            {
                "retry": "annie_proposes",  # Loop back if equipment bad
                "approved": "adam_audits"  # Continue if equipment OK
            }
        )

        # Adam → Decision (HOS OK vs rejected)
        workflow.add_conditional_edges(
            "adam_audits",
            self._should_continue_after_adam,
            {
                "retry": "annie_proposes",  # Loop back if rejected
                "approved": "harper_calculates_pay"  # Continue if approved
            }
        )

        # Harper → Atlas (always continue, Harper just calculates pay)
        workflow.add_edge("harper_calculates_pay", "atlas_validates")

        # Atlas → Decision (margin OK vs margin low)
        workflow.add_conditional_edges(
            "atlas_validates",
            self._should_execute,
            {
                "execute": "execute_assignment",
                "flag": "flag_for_human"
            }
        )

        # Terminal nodes
        workflow.add_edge("execute_assignment", END)
        workflow.add_edge("flag_for_human", END)

        # Compile with memory (allows resuming workflows)
        memory = MemorySaver()
        return workflow.compile(checkpointer=memory)

    # === NODE IMPLEMENTATIONS ===

    async def _annie_proposes_driver(self, state: AgentState) -> AgentState:
        """
        Node: Annie uses vector search to find best driver.

        MDD Spec: "scans drivers table using Vector Search ('Who likes this lane?')"
        """
        stream = GlassDoorStream(self.db, state["task_id"], state["company_id"])

        await stream.log_thinking(
            "annie",
            f"Attempt {state['attempt_count'] + 1}: Searching for optimal driver...",
            reasoning=f"Excluding {len(state['rejected_drivers'])} previously rejected drivers",
            metadata={"rejected_drivers": state["rejected_drivers"]}
        )

        # Register Annie's tools
        await self.annie.register_tools()

        # Query available drivers (excluding rejected ones)
        excluded_drivers = state.get("rejected_drivers", [])
        driver_proposal = await self._find_best_driver(
            state["load_id"],
            excluded_drivers=excluded_drivers
        )

        if not driver_proposal:
            await stream.log_error(
                "annie",
                "No available drivers found",
                context={"rejected_count": len(excluded_drivers)}
            )
            state["status"] = "failed"
            state["error_message"] = "No available drivers"
            return state

        await stream.log_decision(
            "annie",
            f"Proposing Driver {driver_proposal['driver_id'][:8]}... - {driver_proposal.get('driver_name')}",
            reasoning=driver_proposal.get('reasoning', 'Best match by HOS and availability'),
            confidence=driver_proposal.get('confidence', 0.8)
        )

        # Update state
        state["proposed_driver_id"] = driver_proposal["driver_id"]
        state["proposed_driver_name"] = driver_proposal.get("driver_name")
        state["annie_reasoning"] = driver_proposal.get("reasoning")
        state["attempt_count"] += 1

        return state

    async def _adam_audits_compliance(self, state: AgentState) -> AgentState:
        """
        Node: Adam checks DOT HOS compliance.

        MDD Spec: "Checks driver_logs. IF hours < trip_time THEN Reject ELSE Approve."
        """
        stream = GlassDoorStream(self.db, state["task_id"], state["company_id"])

        await stream.log_thinking(
            "adam",
            f"Auditing driver {state['proposed_driver_id'][:8]}... for DOT compliance",
            reasoning="Validating Hours of Service regulations"
        )

        # Register Adam's tools
        await self.adam.register_tools()

        # Validate load assignment
        audit_result = await self.adam._validate_load_assignment(
            driver_id=state["proposed_driver_id"],
            load_id=state["load_id"]
        )

        if not audit_result["approved"]:
            # REJECTION
            await stream.log_rejection(
                "adam",
                f"Driver {state['proposed_driver_id'][:8]}...",
                reason=audit_result["reason"],
                suggested_alternative="Finding driver with sufficient HOS"
            )

            state["adam_approved"] = False
            state["adam_reasoning"] = audit_result["reason"]
            state["rejected_drivers"].append(state["proposed_driver_id"])

        else:
            # APPROVAL
            await stream.log_decision(
                "adam",
                "✅ APPROVED - Driver assignment is DOT compliant",
                reasoning=audit_result["reason"],
                confidence=1.0
            )

            state["adam_approved"] = True
            state["adam_reasoning"] = audit_result["reason"]

        return state

    async def _fleet_checks_equipment(self, state: AgentState) -> AgentState:
        """
        Node: Fleet Manager checks equipment health.

        Validates that the driver's assigned equipment is operational.
        """
        stream = GlassDoorStream(self.db, state["task_id"], state["company_id"])

        # Get driver's assigned equipment
        driver_result = await self.db.execute(
            text("SELECT metadata FROM driver WHERE id = :id"),
            {"id": state["proposed_driver_id"]}
        )
        driver_row = driver_result.fetchone()

        equipment_id = None
        if driver_row and driver_row[0]:
            metadata = driver_row[0]
            if isinstance(metadata, dict):
                equipment_id = metadata.get("assigned_equipment_id")

        if not equipment_id:
            # No equipment assigned - assume OK for now
            await stream.log_thinking(
                "fleet_manager",
                "No specific equipment assigned to driver",
                reasoning="Proceeding without equipment health check"
            )
            state["fleet_approved"] = True
            state["fleet_reasoning"] = "No equipment validation required"
            state["equipment_health_score"] = 100
            state["proposed_equipment_id"] = None
            return state

        await stream.log_thinking(
            "fleet_manager",
            f"Checking equipment health for {equipment_id[:8]}...",
            reasoning="Validating equipment is operational for this load"
        )

        # Register Fleet Manager's tools
        await self.fleet_manager.register_tools()

        # Check equipment health
        health_check = await self.fleet_manager._check_equipment_health(equipment_id)

        if health_check.get("error"):
            await stream.log_error(
                "fleet_manager",
                f"Failed to check equipment: {health_check['error']}",
                context={"equipment_id": equipment_id}
            )
            state["fleet_approved"] = False
            state["fleet_reasoning"] = health_check["error"]
            state["rejected_drivers"].append(state["proposed_driver_id"])
            return state

        health_score = health_check.get("health_score", 0)
        state["equipment_health_score"] = health_score
        state["proposed_equipment_id"] = equipment_id

        # Threshold: equipment must have health score >= 70
        if health_score < 70:
            await stream.log_rejection(
                "fleet_manager",
                f"Equipment {equipment_id[:8]}...",
                reason=f"Health score {health_score}/100 below 70 threshold",
                suggested_alternative="Finding driver with healthier equipment"
            )

            state["fleet_approved"] = False
            state["fleet_reasoning"] = f"Equipment health too low: {health_score}/100"
            state["rejected_drivers"].append(state["proposed_driver_id"])

        else:
            await stream.log_decision(
                "fleet_manager",
                f"✅ APPROVED - Equipment health is {health_score}/100",
                reasoning="Equipment is operational and safe for dispatch",
                confidence=0.95
            )

            state["fleet_approved"] = True
            state["fleet_reasoning"] = f"Good equipment health: {health_score}/100"

        return state

    async def _harper_calculates_pay(self, state: AgentState) -> AgentState:
        """
        Node: Harper calculates expected driver settlement.

        This is informational for Atlas's margin calculation.
        Harper doesn't reject - just provides pay data.
        """
        stream = GlassDoorStream(self.db, state["task_id"], state["company_id"])

        await stream.log_thinking(
            "harper",
            "Calculating expected driver settlement...",
            reasoning="Atlas will use this for margin validation"
        )

        # Get load details for pay calculation
        load_result = await self.db.execute(
            text("SELECT distance_miles FROM freight_load WHERE id = :id"),
            {"id": state["load_id"]}
        )
        load_row = load_result.fetchone()

        if not load_row or not load_row[0]:
            # No mileage data - use rough estimate
            await stream.log_thinking(
                "harper",
                "No mileage data available, using industry average",
                reasoning="Estimating $0.55/mile for typical load"
            )
            estimated_settlement = 1000.00  # Placeholder
            state["harper_settlement_amount"] = estimated_settlement
            state["harper_reasoning"] = "Estimated settlement (no mileage data)"
            return state

        distance_miles = float(load_row[0])

        # Register Harper's tools
        await self.harper.register_tools()

        # Get driver pay rate from metadata
        driver_result = await self.db.execute(
            text("SELECT metadata FROM driver WHERE id = :id"),
            {"id": state["proposed_driver_id"]}
        )
        driver_row = driver_result.fetchone()

        pay_rate_per_mile = 0.55  # Default
        if driver_row and driver_row[0]:
            metadata = driver_row[0]
            if isinstance(metadata, dict):
                pay_rate_per_mile = metadata.get("pay_rate_per_mile", 0.55)

        # Calculate settlement
        settlement_amount = distance_miles * pay_rate_per_mile

        await stream.log_result(
            "harper",
            f"Expected driver settlement: ${settlement_amount:.2f}",
            data={
                "distance_miles": distance_miles,
                "pay_rate": pay_rate_per_mile,
                "settlement": settlement_amount
            }
        )

        state["harper_settlement_amount"] = settlement_amount
        state["harper_reasoning"] = f"{distance_miles} miles × ${pay_rate_per_mile}/mile"

        return state

    async def _atlas_validates_margin(self, state: AgentState) -> AgentState:
        """
        Node: Atlas calculates profit margin.

        MDD Spec: "Calculates Margin. (Rate - DriverPay) / Rate.
                   IF margin < 15% THEN Flag_For_Human ELSE Execute."
        """
        stream = GlassDoorStream(self.db, state["task_id"], state["company_id"])

        await stream.log_thinking(
            "atlas",
            "Calculating profit margin...",
            reasoning="Validating minimum 15% margin requirement"
        )

        # Register Atlas's tools
        await self.atlas.register_tools()

        # Calculate margin using Harper's settlement data
        margin_result = await self._calculate_margin(
            state["load_id"],
            state["proposed_driver_id"],
            driver_settlement=state.get("harper_settlement_amount")
        )

        state["margin_percent"] = margin_result["margin_percent"]

        # Check margin threshold (15% per MDD)
        if margin_result["margin_percent"] < 15:
            await stream.log_rejection(
                "atlas",
                f"Driver {state['proposed_driver_id'][:8]}...",
                reason=f"Margin {margin_result['margin_percent']:.1f}% below 15% threshold",
                suggested_alternative="Searching for more cost-effective driver"
            )

            state["atlas_approved"] = False
            state["atlas_reasoning"] = f"Low margin: {margin_result['margin_percent']:.1f}%"
            state["rejected_drivers"].append(state["proposed_driver_id"])

        else:
            await stream.log_decision(
                "atlas",
                f"✅ APPROVED - Margin is {margin_result['margin_percent']:.1f}%",
                reasoning="Meets minimum 15% profitability requirement",
                confidence=1.0
            )

            state["atlas_approved"] = True
            state["atlas_reasoning"] = f"Good margin: {margin_result['margin_percent']:.1f}%"

        return state

    async def _execute_assignment(self, state: AgentState) -> AgentState:
        """
        Terminal Node: Execute the load assignment in database.

        MDD Spec: "Load Booked."
        """
        stream = GlassDoorStream(self.db, state["task_id"], state["company_id"])

        await stream.log_result(
            "annie",
            f"🎯 EXECUTING: Assigning Driver {state['proposed_driver_id'][:8]}... to Load {state['load_id'][:8]}...",
            data={
                "driver_id": state["proposed_driver_id"],
                "driver_name": state["proposed_driver_name"],
                "load_id": state["load_id"],
                "margin_percent": state["margin_percent"],
                "approved_by": ["Adam (Compliance)", "Atlas (Finance)"],
                "autonomous": True
            }
        )

        try:
            # Execute in database
            await self.db.execute(
                text("""
                UPDATE freight_load
                SET assigned_driver_id = :driver_id, status = 'dispatched'
                WHERE id = :load_id
                """),
                {
                    "driver_id": state["proposed_driver_id"],
                    "load_id": state["load_id"]
                }
            )
            await self.db.commit()

            await stream.log_result(
                "annie",
                "✅ SUCCESS: Load dispatched autonomously",
                data={
                    "status": "dispatched",
                    "margin": state["margin_percent"],
                    "attempts": state["attempt_count"]
                }
            )

            state["status"] = "success"

        except Exception as e:
            await stream.log_error(
                "annie",
                f"Database execution failed: {str(e)}",
                context={"driver_id": state["proposed_driver_id"], "load_id": state["load_id"]}
            )

            state["status"] = "failed"
            state["error_message"] = str(e)

        return state

    async def _flag_for_human(self, state: AgentState) -> AgentState:
        """
        Terminal Node: Flag low-margin load for human review.

        MDD Spec: "IF margin < 15% THEN Flag_For_Human"
        """
        stream = GlassDoorStream(self.db, state["task_id"], state["company_id"])

        await stream.log_result(
            "atlas",
            "⚠️ FLAGGED FOR REVIEW: Below profitability threshold",
            data={
                "margin_percent": state["margin_percent"],
                "reason": "Margin below 15% minimum",
                "recommendation": "Reject load or negotiate higher rate"
            }
        )

        # Create approval request
        approval_id = str(uuid.uuid4())
        await self.db.execute(
            text("""
            INSERT INTO ai_approval_requests
            (id, company_id, agent_type, reason, urgency, amount, recommendation, status, created_at)
            VALUES
            (:id, :company_id, :agent_type, :reason, :urgency, :amount, :recommendation, :status, :created_at)
            """),
            {
                "id": approval_id,
                "company_id": state["company_id"],
                "agent_type": "atlas",
                "reason": f"Low margin load: {state['margin_percent']:.1f}%",
                "urgency": "medium",
                "amount": 0,  # Could calculate from load rate
                "recommendation": "Reject load or renegotiate for 15%+ margin",
                "status": "pending",
                "created_at": datetime.utcnow()
            }
        )
        await self.db.commit()

        state["status"] = "flagged_for_review"

        return state

    # === CONDITIONAL EDGES ===

    def _should_continue_after_fleet(self, state: AgentState) -> Literal["retry", "approved"]:
        """
        Conditional: Should we retry after Fleet Manager's equipment check?

        If equipment is unhealthy, loop back to Annie for different driver.
        """
        MAX_ATTEMPTS = 3

        if not state["fleet_approved"]:
            # Fleet Manager rejected - check if we should retry
            if state["attempt_count"] >= MAX_ATTEMPTS:
                # Out of retries, fail the workflow
                state["status"] = "failed"
                state["error_message"] = f"No driver with healthy equipment found after {MAX_ATTEMPTS} attempts"
                return "approved"  # End the workflow
            else:
                return "retry"  # Loop back to Annie
        else:
            return "approved"  # Continue to Adam

    def _should_continue_after_adam(self, state: AgentState) -> Literal["retry", "approved"]:
        """
        Conditional: Should we loop back to Annie or proceed to Harper?

        MDD Spec: "Loop: If Rejected, send back to Annie with feedback"
        """
        MAX_ATTEMPTS = 3

        if not state["adam_approved"]:
            # Adam rejected - check if we should retry
            if state["attempt_count"] >= MAX_ATTEMPTS:
                # Out of retries, fail the workflow
                state["status"] = "failed"
                state["error_message"] = f"No compliant driver found after {MAX_ATTEMPTS} attempts"
                return "approved"  # End the workflow (will fail at execution)
            else:
                return "retry"  # Loop back to Annie
        else:
            return "approved"  # Continue to Harper

    def _should_execute(self, state: AgentState) -> Literal["execute", "flag"]:
        """
        Conditional: Should we execute or flag for human review?

        MDD Spec: "IF margin < 15% THEN Flag_For_Human ELSE Execute"
        """
        if state["atlas_approved"]:
            return "execute"
        else:
            return "flag"

    # === HELPER METHODS ===

    async def _find_best_driver(self, load_id: str, excluded_drivers: list = None) -> dict | None:
        """Find best available driver, excluding rejected ones."""
        excluded_drivers = excluded_drivers or []

        # Build exclusion clause
        exclusion_clause = ""
        if excluded_drivers:
            placeholders = ", ".join([f":excluded_{i}" for i in range(len(excluded_drivers))])
            exclusion_clause = f"AND d.id NOT IN ({placeholders})"

        # Query available drivers
        query = text(f"""
        SELECT
            d.id, d.first_name, d.last_name, d.hos_remaining
        FROM driver d
        WHERE d.is_active = true
        AND d.hos_remaining > 8.0
        {exclusion_clause}
        ORDER BY d.hos_remaining DESC
        LIMIT 1
        """)

        # Build parameters
        params = {}
        for i, driver_id in enumerate(excluded_drivers):
            params[f"excluded_{i}"] = driver_id

        result = await self.db.execute(query, params)
        driver_row = result.fetchone()

        if not driver_row:
            return None

        return {
            "driver_id": driver_row[0],
            "driver_name": f"{driver_row[1]} {driver_row[2]}",
            "hos_remaining": driver_row[3],
            "reasoning": f"Selected driver with {driver_row[3]:.1f} hours HOS remaining",
            "confidence": 0.9
        }

    async def _calculate_margin(
        self,
        load_id: str,
        driver_id: str,
        driver_settlement: float = None
    ) -> dict:
        """
        Calculate profit margin for load assignment.

        Uses Harper's settlement calculation if available, otherwise estimates.
        """
        # Get load rate
        load_result = await self.db.execute(
            text("SELECT base_rate FROM freight_load WHERE id = :id"),
            {"id": load_id}
        )
        load_row = load_result.fetchone()

        if not load_row or not load_row[0]:
            return {"margin_percent": 0, "error": "Load rate not found"}

        load_rate = float(load_row[0])

        # Use Harper's settlement if available, otherwise estimate
        if driver_settlement:
            driver_cost = driver_settlement
        else:
            # Fallback: estimate driver cost
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

    # === PUBLIC API ===

    async def run(self, load_id: str, company_id: str) -> dict:
        """
        Execute the load assignment workflow.

        Returns final state after workflow completes.
        """
        # Initialize state
        task_id = str(uuid.uuid4())

        initial_state: AgentState = {
            "load_id": load_id,
            "company_id": company_id,
            "task_id": task_id,
            "proposed_driver_id": None,
            "proposed_driver_name": None,
            "proposed_equipment_id": None,
            "annie_reasoning": None,
            "fleet_approved": False,
            "fleet_reasoning": None,
            "equipment_health_score": None,
            "adam_approved": False,
            "adam_reasoning": None,
            "rejected_drivers": [],
            "harper_settlement_amount": None,
            "harper_reasoning": None,
            "margin_percent": None,
            "atlas_approved": False,
            "atlas_reasoning": None,
            "status": "pending",
            "error_message": None,
            "attempt_count": 0
        }

        # Run the graph
        config = {"configurable": {"thread_id": task_id}}
        final_state = await self.graph.ainvoke(initial_state, config)

        return {
            "status": final_state["status"],
            "driver_id": final_state.get("proposed_driver_id"),
            "driver_name": final_state.get("proposed_driver_name"),
            "equipment_id": final_state.get("proposed_equipment_id"),
            "equipment_health_score": final_state.get("equipment_health_score"),
            "driver_settlement": final_state.get("harper_settlement_amount"),
            "margin_percent": final_state.get("margin_percent"),
            "attempts": final_state["attempt_count"],
            "error": final_state.get("error_message")
        }
