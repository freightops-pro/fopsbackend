"""Check Payroll API Service.

Provides integration with Check's payroll API for:
- Company management
- Employee management
- Payroll processing
- Benefits administration
"""
from __future__ import annotations

import httpx
from typing import Any, Optional, List
from datetime import datetime

from app.core.config import get_settings


class CheckService:
    """Service for interacting with Check Payroll API."""

    def __init__(self, company_check_id: Optional[str] = None):
        """Initialize Check service.

        Args:
            company_check_id: The Check company ID for this tenant
        """
        self.settings = get_settings()
        self.company_check_id = company_check_id
        self.base_url = self.settings.check_api_base_url

    def _get_headers(self) -> dict:
        """Get authorization headers for Check API."""
        api_key = self.settings.check_api_key

        if not api_key:
            raise ValueError("Check API key not configured")

        # Check uses Bearer token authentication
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> Any:
        """Make a request to Check API."""
        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self._get_headers(),
                json=data,
                params=params,
            )

            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise Exception(
                    f"Check API error: {response.status_code} - {error_data.get('error', {}).get('message', 'Unknown error')}"
                )

            if response.status_code == 204:
                return None

            return response.json()

    # ==================== Company Endpoints ====================

    async def get_company(self) -> dict:
        """Get the Check company for this tenant."""
        if not self.company_check_id:
            raise ValueError("Company Check ID not set")
        return await self._request("GET", f"/companies/{self.company_check_id}")

    async def create_company(self, data: dict) -> dict:
        """Create a new Check company."""
        result = await self._request("POST", "/companies", data=data)
        self.company_check_id = result.get("id")
        return result

    async def update_company(self, data: dict) -> dict:
        """Update the Check company."""
        if not self.company_check_id:
            raise ValueError("Company Check ID not set")
        return await self._request("PATCH", f"/companies/{self.company_check_id}", data=data)

    # ==================== Employee Endpoints ====================

    async def list_employees(self, page: int = 1, per_page: int = 50) -> List[dict]:
        """List all employees for the company."""
        if not self.company_check_id:
            raise ValueError("Company Check ID not set")

        result = await self._request(
            "GET",
            "/employees",
            params={
                "company": self.company_check_id,
                "page": page,
                "per_page": per_page,
            }
        )
        return result.get("results", []) if isinstance(result, dict) else result

    async def get_employee(self, employee_id: str) -> dict:
        """Get a specific employee."""
        return await self._request("GET", f"/employees/{employee_id}")

    async def create_employee(self, data: dict) -> dict:
        """Create a new employee."""
        if not self.company_check_id:
            raise ValueError("Company Check ID not set")
        data["company"] = self.company_check_id
        return await self._request("POST", "/employees", data=data)

    async def update_employee(self, employee_id: str, data: dict) -> dict:
        """Update an employee."""
        return await self._request("PATCH", f"/employees/{employee_id}", data=data)

    async def delete_employee(self, employee_id: str) -> None:
        """Delete an employee."""
        await self._request("DELETE", f"/employees/{employee_id}")

    # ==================== Payroll Endpoints ====================

    async def list_payrolls(self, page: int = 1, per_page: int = 50) -> List[dict]:
        """List all payrolls for the company."""
        if not self.company_check_id:
            raise ValueError("Company Check ID not set")

        result = await self._request(
            "GET",
            "/payrolls",
            params={
                "company": self.company_check_id,
                "page": page,
                "per_page": per_page,
            }
        )
        return result.get("results", []) if isinstance(result, dict) else result

    async def get_payroll(self, payroll_id: str) -> dict:
        """Get a specific payroll."""
        return await self._request("GET", f"/payrolls/{payroll_id}")

    async def create_payroll(self, data: dict) -> dict:
        """Create a new payroll run."""
        if not self.company_check_id:
            raise ValueError("Company Check ID not set")
        data["company"] = self.company_check_id
        return await self._request("POST", "/payrolls", data=data)

    async def update_payroll(self, payroll_id: str, data: dict) -> dict:
        """Update a payroll."""
        return await self._request("PATCH", f"/payrolls/{payroll_id}", data=data)

    async def preview_payroll(self, payroll_id: str) -> dict:
        """Preview a payroll before approval."""
        return await self._request("POST", f"/payrolls/{payroll_id}/preview")

    async def approve_payroll(self, payroll_id: str) -> dict:
        """Approve a payroll for processing."""
        return await self._request("POST", f"/payrolls/{payroll_id}/approve")

    async def cancel_payroll(self, payroll_id: str) -> dict:
        """Cancel a payroll."""
        return await self._request("POST", f"/payrolls/{payroll_id}/cancel")

    # ==================== Benefits Endpoints ====================

    async def list_benefits(self, employee_id: Optional[str] = None) -> List[dict]:
        """List benefits, optionally filtered by employee."""
        if not self.company_check_id:
            raise ValueError("Company Check ID not set")

        params = {"company": self.company_check_id}
        if employee_id:
            params["employee"] = employee_id

        result = await self._request("GET", "/benefits", params=params)
        return result.get("results", []) if isinstance(result, dict) else result

    async def get_benefit(self, benefit_id: str) -> dict:
        """Get a specific benefit."""
        return await self._request("GET", f"/benefits/{benefit_id}")

    async def create_benefit(self, data: dict) -> dict:
        """Create a new benefit for an employee."""
        return await self._request("POST", "/benefits", data=data)

    async def update_benefit(self, benefit_id: str, data: dict) -> dict:
        """Update a benefit."""
        return await self._request("PATCH", f"/benefits/{benefit_id}", data=data)

    async def delete_benefit(self, benefit_id: str) -> None:
        """Delete a benefit."""
        await self._request("DELETE", f"/benefits/{benefit_id}")

    # ==================== Company Benefits Endpoints ====================

    async def list_company_benefits(self) -> List[dict]:
        """List company-level benefit plans."""
        if not self.company_check_id:
            raise ValueError("Company Check ID not set")

        result = await self._request(
            "GET",
            "/company_benefits",
            params={"company": self.company_check_id}
        )
        return result.get("results", []) if isinstance(result, dict) else result

    async def create_company_benefit(self, data: dict) -> dict:
        """Create a new company-level benefit."""
        if not self.company_check_id:
            raise ValueError("Company Check ID not set")
        data["company"] = self.company_check_id
        return await self._request("POST", "/company_benefits", data=data)

    async def update_company_benefit(self, benefit_id: str, data: dict) -> dict:
        """Update a company benefit."""
        return await self._request("PATCH", f"/company_benefits/{benefit_id}", data=data)

    async def delete_company_benefit(self, benefit_id: str) -> None:
        """Delete a company benefit."""
        await self._request("DELETE", f"/company_benefits/{benefit_id}")

    # ==================== Contractors Endpoints ====================

    async def list_contractors(self, page: int = 1, per_page: int = 50) -> List[dict]:
        """List all contractors for the company."""
        if not self.company_check_id:
            raise ValueError("Company Check ID not set")

        result = await self._request(
            "GET",
            "/contractors",
            params={
                "company": self.company_check_id,
                "page": page,
                "per_page": per_page,
            }
        )
        return result.get("results", []) if isinstance(result, dict) else result

    async def create_contractor(self, data: dict) -> dict:
        """Create a new contractor."""
        if not self.company_check_id:
            raise ValueError("Company Check ID not set")
        data["company"] = self.company_check_id
        return await self._request("POST", "/contractors", data=data)

    # ==================== Workplaces Endpoints ====================

    async def list_workplaces(self) -> List[dict]:
        """List all workplaces for the company."""
        if not self.company_check_id:
            raise ValueError("Company Check ID not set")

        result = await self._request(
            "GET",
            "/workplaces",
            params={"company": self.company_check_id}
        )
        return result.get("results", []) if isinstance(result, dict) else result

    async def create_workplace(self, data: dict) -> dict:
        """Create a new workplace."""
        if not self.company_check_id:
            raise ValueError("Company Check ID not set")
        data["company"] = self.company_check_id
        return await self._request("POST", "/workplaces", data=data)
