"""
NeonDB Branch Manager - Safe database sandboxing for AI agents.

Uses Neon's branching API to create isolated database copies where
agents can test SQL queries before applying them to production.
"""

import os
import httpx
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text


class NeonBranchManager:
    """
    Manages database branches for safe AI agent experimentation.

    Workflow:
    1. Agent proposes a query (UPDATE, DELETE, etc.)
    2. Create a branch of the main database
    3. Run query on the branch
    4. Adam (auditor) reviews the results
    5. If approved: merge branch → main
    6. If rejected: delete branch
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.neon_api_key = os.getenv("NEON_API_KEY")
        self.neon_project_id = os.getenv("NEON_PROJECT_ID")
        self.neon_api_url = "https://console.neon.tech/api/v2"

        if not self.neon_api_key or not self.neon_project_id:
            print("[Neon Branch Manager] Warning: NEON_API_KEY or NEON_PROJECT_ID not set. Database branching disabled.")

    async def create_sandbox_branch(
        self,
        task_id: str,
        company_id: str,
        agent_type: str,
        purpose: str = "sandbox_test"
    ) -> dict:
        """
        Create a new database branch for testing.

        Returns:
            {
                "branch_id": "br_123",
                "branch_name": "agent_sandbox_abc123",
                "connection_uri": "postgresql://..."
            }
        """
        if not self.neon_api_key:
            raise ValueError("NEON_API_KEY not set - cannot create database branch")

        branch_name = f"agent_{agent_type}_{task_id[:8]}"

        # Call Neon API to create branch
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
                        "parent_id": "main"  # Branch from main
                    }
                },
                timeout=30.0
            )
            response.raise_for_status()
            branch_data = response.json()

        # Get connection URI from response
        connection_uris = branch_data.get("connection_uris", [])
        connection_uri = connection_uris[0]["connection_uri"] if connection_uris else None

        # Store in database
        branch_id = str(uuid.uuid4())
        await self.db.execute(
            text("""
            INSERT INTO ai_database_branches
            (id, task_id, company_id, neon_branch_id, neon_branch_name, branch_connection_uri, purpose, agent_type, status, created_at)
            VALUES
            (:id, :task_id, :company_id, :neon_branch_id, :neon_branch_name, :branch_connection_uri, :purpose, :agent_type, :status, :created_at)
            """),
            {
                "id": branch_id,
                "task_id": task_id,
                "company_id": company_id,
                "neon_branch_id": branch_data["branch"]["id"],
                "neon_branch_name": branch_name,
                "branch_connection_uri": connection_uri,
                "purpose": purpose,
                "agent_type": agent_type,
                "status": "active",
                "created_at": datetime.utcnow()
            }
        )
        await self.db.commit()

        return {
            "branch_id": branch_id,
            "neon_branch_id": branch_data["branch"]["id"],
            "branch_name": branch_name,
            "connection_uri": connection_uri
        }

    async def execute_on_branch(
        self,
        branch_id: str,
        sql_query: str
    ) -> dict:
        """
        Execute SQL on a branch (not production).

        Returns:
            {
                "affected_rows": int,
                "results": [...],
                "error": str | None
            }
        """
        # Get branch connection string
        result = await self.db.execute(
            text("SELECT branch_connection_uri FROM ai_database_branches WHERE id = :id"),
            {"id": branch_id}
        )
        row = result.fetchone()

        if not row:
            raise ValueError(f"Branch {branch_id} not found")

        connection_uri = row[0]

        if not connection_uri:
            raise ValueError(f"Branch {branch_id} has no connection URI")

        # Create temporary engine for this branch
        branch_engine = create_async_engine(connection_uri)

        try:
            async with branch_engine.connect() as conn:
                result = await conn.execute(text(sql_query))
                affected_rows = result.rowcount

                # Try to fetch results if SELECT query
                try:
                    results = result.fetchall()
                    results_dict = [dict(row._mapping) for row in results]
                except:
                    results_dict = []

                await conn.commit()

                # Update database record
                await self.db.execute(
                    text("""
                    UPDATE ai_database_branches
                    SET sql_executed = :sql, affected_rows = :rows
                    WHERE id = :id
                    """),
                    {
                        "id": branch_id,
                        "sql": sql_query,
                        "rows": affected_rows
                    }
                )
                await self.db.commit()

                return {
                    "affected_rows": affected_rows,
                    "results": results_dict,
                    "error": None
                }
        except Exception as e:
            return {
                "affected_rows": 0,
                "results": [],
                "error": str(e)
            }
        finally:
            await branch_engine.dispose()

    async def merge_branch(self, branch_id: str, auditor_reasoning: str):
        """
        Merge branch changes into main (production).

        Only called after Adam approves the changes.
        """
        # Get branch info
        result = await self.db.execute(
            text("SELECT neon_branch_id FROM ai_database_branches WHERE id = :id"),
            {"id": branch_id}
        )
        row = result.fetchone()

        if not row:
            raise ValueError(f"Branch {branch_id} not found")

        neon_branch_id = row[0]

        # Call Neon API to merge
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.neon_api_url}/projects/{self.neon_project_id}/branches/{neon_branch_id}/merge",
                headers={"Authorization": f"Bearer {self.neon_api_key}"},
                timeout=30.0
            )

        # Update database
        await self.db.execute(
            text("""
            UPDATE ai_database_branches
            SET status = 'merged', merged_at = :merged_at, audit_reasoning = :reasoning
            WHERE id = :id
            """),
            {
                "id": branch_id,
                "merged_at": datetime.utcnow(),
                "reasoning": auditor_reasoning
            }
        )
        await self.db.commit()

    async def delete_branch(self, branch_id: str, rejection_reason: str):
        """
        Delete branch without merging (Adam rejected it).
        """
        result = await self.db.execute(
            text("SELECT neon_branch_id FROM ai_database_branches WHERE id = :id"),
            {"id": branch_id}
        )
        row = result.fetchone()

        if not row:
            raise ValueError(f"Branch {branch_id} not found")

        neon_branch_id = row[0]

        # Call Neon API to delete
        async with httpx.AsyncClient() as client:
            await client.delete(
                f"{self.neon_api_url}/projects/{self.neon_project_id}/branches/{neon_branch_id}",
                headers={"Authorization": f"Bearer {self.neon_api_key}"},
                timeout=30.0
            )

        # Update database
        await self.db.execute(
            text("""
            UPDATE ai_database_branches
            SET status = 'deleted', deleted_at = :deleted_at, audit_reasoning = :reasoning
            WHERE id = :id
            """),
            {
                "id": branch_id,
                "deleted_at": datetime.utcnow(),
                "reasoning": rejection_reason
            }
        )
        await self.db.commit()
