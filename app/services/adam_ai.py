"""
Adam AI - Compliance and Risk Auditor Agent.

Adam checks other agents' decisions for safety, compliance, and correctness.
Uses Llama 4 Maverick for deep reasoning about DOT regulations and HOS rules.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.services.ai_agent import BaseAIAgent, AITool
from app.core.llm_router import LLMRouter


class AdamAI(BaseAIAgent):
    """
    Adam - Compliance Auditor AI Agent.

    Specializes in:
    - Auditing driver HOS compliance
    - Reviewing database changes for safety
    - Validating load assignments against DOT rules
    - Rejecting unsafe or non-compliant actions
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.llm_router = LLMRouter()

    @property
    def agent_name(self) -> str:
        return "Adam"

    @property
    def agent_role(self) -> str:
        return """Compliance and Risk AI specializing in DOT regulations, HOS auditing,
and safety validation. I audit other agents' decisions and reject unsafe actions."""

    async def register_tools(self):
        """Register Adam's auditing tools."""
        self.tools = [
            AITool(
                name="audit_driver_hos",
                description="Check if a driver has enough HOS remaining for a trip",
                parameters={
                    "driver_id": {"type": "string", "description": "Driver ID to check"},
                    "estimated_trip_hours": {"type": "number", "description": "Estimated trip duration in hours"},
                },
                function=self._audit_driver_hos
            ),

            AITool(
                name="audit_database_change",
                description="Review proposed database changes for safety",
                parameters={
                    "sql_query": {"type": "string", "description": "SQL query to audit"},
                    "affected_rows": {"type": "number", "description": "Number of rows that would be affected"},
                    "context": {"type": "string", "description": "What this query is trying to do"},
                },
                function=self._audit_database_change
            ),

            AITool(
                name="validate_load_assignment",
                description="Check if a load assignment is safe and compliant",
                parameters={
                    "driver_id": {"type": "string", "description": "Proposed driver"},
                    "load_id": {"type": "string", "description": "Load to assign"},
                },
                function=self._validate_load_assignment
            ),
        ]

    async def _audit_driver_hos(self, driver_id: str, estimated_trip_hours: float) -> dict:
        """Check if driver has enough hours."""
        # Query driver HOS from database
        result = await self.db.execute(
            text("SELECT hos_remaining, first_name, last_name FROM driver WHERE id = :id"),
            {"id": driver_id}
        )
        row = result.fetchone()

        if not row:
            return {"approved": False, "reason": "Driver not found"}

        hos_remaining = float(row[0]) if row[0] else 0
        driver_name = f"{row[1]} {row[2]}"

        # DOT Rule: Must have at least trip_hours + 2 hours buffer
        required_hours = estimated_trip_hours + 2

        if hos_remaining >= required_hours:
            return {
                "approved": True,
                "reason": f"Driver {driver_name} has {hos_remaining:.1f} hours remaining, needs {required_hours:.1f} hours",
                "hos_remaining": hos_remaining,
                "driver_name": driver_name
            }
        else:
            return {
                "approved": False,
                "reason": f"DOT VIOLATION: Driver {driver_name} only has {hos_remaining:.1f} hours remaining, but needs {required_hours:.1f} hours for this trip",
                "hos_remaining": hos_remaining,
                "required_hours": required_hours,
                "driver_name": driver_name
            }

    async def _audit_database_change(self, sql_query: str, affected_rows: int, context: str) -> dict:
        """Audit a proposed SQL query for safety."""
        sql_upper = sql_query.upper()

        # Red flag: Too many rows affected
        if affected_rows > 100:
            return {
                "approved": False,
                "reason": f"DANGEROUS: Query would affect {affected_rows} rows. This is too many for a single operation.",
                "recommendation": "Break into smaller batches or require manual verification",
                "severity": "high"
            }

        # Red flag: DELETE without WHERE
        if "DELETE" in sql_upper and "WHERE" not in sql_upper:
            return {
                "approved": False,
                "reason": "DANGEROUS: DELETE statement without WHERE clause would delete all rows",
                "recommendation": "Add WHERE clause to limit scope",
                "severity": "critical"
            }

        # Red flag: DROP TABLE
        if "DROP TABLE" in sql_upper or "DROP DATABASE" in sql_upper:
            return {
                "approved": False,
                "reason": "BLOCKED: Agents cannot drop tables or databases",
                "recommendation": "Contact human administrator for structural changes",
                "severity": "critical"
            }

        # Red flag: TRUNCATE
        if "TRUNCATE" in sql_upper:
            return {
                "approved": False,
                "reason": "BLOCKED: TRUNCATE operations are not allowed for AI agents",
                "recommendation": "Use DELETE with WHERE clause instead",
                "severity": "high"
            }

        # Red flag: ALTER TABLE
        if "ALTER TABLE" in sql_upper:
            return {
                "approved": False,
                "reason": "BLOCKED: Schema changes require human approval",
                "recommendation": "Submit schema change request to engineering team",
                "severity": "medium"
            }

        # Looks safe
        return {
            "approved": True,
            "reason": f"Query appears safe: affects {affected_rows} rows with proper filtering. Context: {context}",
            "context": context,
            "severity": "low"
        }

    async def _validate_load_assignment(self, driver_id: str, load_id: str) -> dict:
        """Validate a complete load assignment for compliance."""
        # Get load details
        load_result = await self.db.execute(
            text("""
            SELECT
                origin_city, origin_state, dest_city, dest_state,
                pickup_location_latitude, pickup_location_longitude,
                delivery_location_latitude, delivery_location_longitude
            FROM freight_load
            WHERE id = :id
            """),
            {"id": load_id}
        )
        load = load_result.fetchone()

        if not load:
            return {"approved": False, "reason": "Load not found"}

        # Estimate trip time based on distance
        # Simplified: Using straight-line distance and average 50 mph
        if load[4] and load[5] and load[6] and load[7]:
            import math
            lat1, lon1 = load[4], load[5]
            lat2, lon2 = load[6], load[7]

            # Haversine formula for distance
            R = 3959  # Earth radius in miles
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = (math.sin(dlat / 2) ** 2 +
                 math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
                 math.sin(dlon / 2) ** 2)
            c = 2 * math.asin(math.sqrt(a))
            distance = R * c

            # Estimate driving time at 50 mph average + 20% for stops/traffic
            estimated_hours = (distance / 50) * 1.2
        else:
            # Fallback: Estimate based on city/state (very rough)
            estimated_hours = 10.0

        # Check HOS compliance
        hos_check = await self._audit_driver_hos(driver_id, estimated_hours)

        if not hos_check["approved"]:
            return {
                "approved": False,
                "reason": hos_check["reason"],
                "details": hos_check,
                "estimated_trip_hours": estimated_hours
            }

        # All checks passed
        return {
            "approved": True,
            "reason": f"Load assignment is compliant. Driver has sufficient HOS for {estimated_hours:.1f} hour trip.",
            "details": hos_check,
            "estimated_trip_hours": estimated_hours
        }
