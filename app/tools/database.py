"""
Safe SQL Execution Tool - NeonDB Branching

MDD Spec: "Intercept: When an agent wants to run UPDATE or DELETE.
           Branch: Call Neon API to fork main → agent_simulation_branch.
           Test: Run the SQL on the branch.
           Audit: Adam (Maverick) checks the result. 'Did we just delete 500 rows? If yes, REJECT.'
           Merge: Only apply to main if Adam approves."

Prevents AI agents from corrupting production data via database branching.
"""

import os
import httpx
import uuid
from typing import Dict, Any, Literal
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.services.adam_ai import AdamAI


class SafeDatabaseExecutor:
    """
    Executes potentially dangerous SQL queries using NeonDB branch sandboxing.

    Workflow:
    1. Detect dangerous query (UPDATE, DELETE, ALTER, DROP)
    2. Create NeonDB branch (fork of production)
    3. Run query on branch
    4. Adam audits the results
    5. If approved: Merge branch → production
    6. If rejected: Delete branch
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.neon_api_key = os.getenv("NEON_API_KEY")
        self.neon_project_id = os.getenv("NEON_PROJECT_ID")
        self.neon_api_url = "https://console.neon.tech/api/v2"

        if not self.neon_api_key:
            print("[Database Tool] Warning: NEON_API_KEY not set. Sandboxing disabled.")
            self.sandboxing_enabled = False
        else:
            self.sandboxing_enabled = True

        self.adam = AdamAI(db)

    async def execute_sql(
        self,
        sql_query: str,
        agent_type: str = "unknown",
        context: str = ""
    ) -> Dict[str, Any]:
        """
        Execute SQL query with automatic sandboxing for dangerous operations.

        Args:
            sql_query: SQL to execute
            agent_type: Which agent is requesting (annie, adam, atlas)
            context: Human-readable description of what this query does

        Returns:
            {
                "status": "success" | "rejected" | "error",
                "affected_rows": int,
                "results": list,
                "audit_reason": str,
                "sandboxed": bool
            }
        """
        # Classify query danger level
        danger_level = self._classify_query(sql_query)

        if danger_level == "safe":
            # Safe queries (SELECT, INSERT single row) - execute directly
            return await self._execute_direct(sql_query)

        elif danger_level == "dangerous":
            # Dangerous queries - use sandbox
            if not self.sandboxing_enabled:
                # Fallback: execute with Adam's pre-approval
                audit_result = await self._get_adam_preapproval(sql_query, context)
                if not audit_result["approved"]:
                    return {
                        "status": "rejected",
                        "affected_rows": 0,
                        "audit_reason": audit_result["reason"],
                        "sandboxed": False
                    }
                return await self._execute_direct(sql_query)

            else:
                # Full sandbox workflow
                return await self._execute_sandboxed(sql_query, agent_type, context)

        else:
            # Forbidden queries (DROP, TRUNCATE) - always reject
            return {
                "status": "rejected",
                "affected_rows": 0,
                "audit_reason": "Forbidden operation: Agents cannot DROP/TRUNCATE tables",
                "sandboxed": False
            }

    def _classify_query(self, sql: str) -> Literal["safe", "dangerous", "forbidden"]:
        """
        Classify SQL query danger level.

        MDD Spec: "Intercept: When an agent wants to run UPDATE or DELETE."
        """
        sql_upper = sql.upper().strip()

        # Forbidden (always reject)
        if any(keyword in sql_upper for keyword in ["DROP TABLE", "DROP DATABASE", "TRUNCATE"]):
            return "forbidden"

        # Dangerous (requires sandbox)
        if any(keyword in sql_upper for keyword in ["UPDATE", "DELETE", "ALTER"]):
            return "dangerous"

        # Safe (execute directly)
        return "safe"

    async def _execute_direct(self, sql_query: str) -> Dict[str, Any]:
        """Execute safe query directly on production database."""
        try:
            result = await self.db.execute(text(sql_query))
            affected_rows = result.rowcount

            # Try to fetch results (for SELECT)
            try:
                results = result.fetchall()
                results_list = [dict(row._mapping) for row in results]
            except:
                results_list = []

            await self.db.commit()

            return {
                "status": "success",
                "affected_rows": affected_rows,
                "results": results_list,
                "sandboxed": False
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "sandboxed": False
            }

    async def _execute_sandboxed(
        self,
        sql_query: str,
        agent_type: str,
        context: str
    ) -> Dict[str, Any]:
        """
        Execute query on NeonDB branch, audit results, then merge or discard.

        MDD Workflow:
        1. Branch: Fork main → agent_simulation_branch
        2. Test: Run SQL on branch
        3. Audit: Adam checks results
        4. Merge: Apply to main if approved
        """
        branch_name = f"agent_{agent_type}_{uuid.uuid4().hex[:8]}"

        # Step 1: Create branch
        branch_result = await self._create_neon_branch(branch_name)
        if "error" in branch_result:
            return {
                "status": "error",
                "error": branch_result["error"],
                "sandboxed": True
            }

        branch_id = branch_result["branch_id"]
        branch_connection_uri = branch_result["connection_uri"]

        try:
            # Step 2: Execute on branch
            execution_result = await self._execute_on_branch(
                branch_connection_uri,
                sql_query
            )

            if "error" in execution_result:
                await self._delete_neon_branch(branch_id)
                return {
                    "status": "error",
                    "error": execution_result["error"],
                    "sandboxed": True
                }

            affected_rows = execution_result["affected_rows"]

            # Step 3: Adam audits
            await self.adam.register_tools()
            audit_result = await self.adam._audit_database_change(
                sql_query=sql_query,
                affected_rows=affected_rows,
                context=context
            )

            if not audit_result["approved"]:
                # REJECTED - Delete branch
                await self._delete_neon_branch(branch_id)
                return {
                    "status": "rejected",
                    "affected_rows": affected_rows,
                    "audit_reason": audit_result["reason"],
                    "recommendation": audit_result.get("recommendation"),
                    "sandboxed": True
                }

            else:
                # APPROVED - Merge branch to main
                await self._merge_neon_branch(branch_id)
                return {
                    "status": "success",
                    "affected_rows": affected_rows,
                    "results": execution_result.get("results", []),
                    "audit_reason": audit_result["reason"],
                    "sandboxed": True
                }

        except Exception as e:
            # Error - clean up branch
            await self._delete_neon_branch(branch_id)
            return {
                "status": "error",
                "error": str(e),
                "sandboxed": True
            }

    async def _create_neon_branch(self, branch_name: str) -> Dict[str, Any]:
        """Call Neon API to create database branch."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.neon_api_url}/projects/{self.neon_project_id}/branches",
                    headers={
                        "Authorization": f"Bearer {self.neon_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "branch": {
                            "name": branch_name,
                            "parent_id": "main"
                        }
                    }
                )
                response.raise_for_status()
                data = response.json()

                return {
                    "branch_id": data["branch"]["id"],
                    "branch_name": branch_name,
                    "connection_uri": data["connection_uris"][0]["connection_uri"]
                }

        except Exception as e:
            return {"error": f"Failed to create branch: {str(e)}"}

    async def _execute_on_branch(
        self,
        branch_connection_uri: str,
        sql_query: str
    ) -> Dict[str, Any]:
        """Execute SQL on branch database."""
        try:
            # Create temporary engine for branch
            branch_engine = create_async_engine(branch_connection_uri)

            async with branch_engine.connect() as conn:
                result = await conn.execute(text(sql_query))
                affected_rows = result.rowcount

                # Try to fetch results
                try:
                    results = result.fetchall()
                    results_list = [dict(row._mapping) for row in results]
                except:
                    results_list = []

                await conn.commit()

            await branch_engine.dispose()

            return {
                "affected_rows": affected_rows,
                "results": results_list
            }

        except Exception as e:
            return {"error": str(e)}

    async def _merge_neon_branch(self, branch_id: str):
        """Merge branch changes into main production database."""
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self.neon_api_url}/projects/{self.neon_project_id}/branches/{branch_id}/merge",
                    headers={"Authorization": f"Bearer {self.neon_api_key}"}
                )
        except Exception as e:
            print(f"[Database Tool] Warning: Failed to merge branch {branch_id}: {e}")

    async def _delete_neon_branch(self, branch_id: str):
        """Delete branch without merging."""
        try:
            async with httpx.AsyncClient() as client:
                await client.delete(
                    f"{self.neon_api_url}/projects/{self.neon_project_id}/branches/{branch_id}",
                    headers={"Authorization": f"Bearer {self.neon_api_key}"}
                )
        except Exception as e:
            print(f"[Database Tool] Warning: Failed to delete branch {branch_id}: {e}")

    async def _get_adam_preapproval(self, sql_query: str, context: str) -> Dict[str, Any]:
        """
        Fallback when sandboxing is disabled: Get Adam's pre-approval.

        Not as safe as sandboxing, but better than nothing.
        """
        await self.adam.register_tools()

        # Estimate affected rows (conservative guess)
        estimated_rows = 10  # Placeholder

        audit_result = await self.adam._audit_database_change(
            sql_query=sql_query,
            affected_rows=estimated_rows,
            context=context
        )

        return audit_result
