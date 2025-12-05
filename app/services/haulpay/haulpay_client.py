"""
HaulPay API Client
Based on: https://docs.haulpay.io/carrier-api
"""

import logging
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger(__name__)


class HaulPayClient:
    """Client for interacting with HaulPay API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.haulpay.io/v1/external_api",
        staging: bool = False,
    ):
        """
        Initialize HaulPay client.
        
        Args:
            api_key: Bearer token for authentication
            base_url: Base API URL (defaults to production)
            staging: If True, uses staging environment
        """
        if staging:
            base_url = base_url.replace("api", "api-staging")
        
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to HaulPay API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            json_data: JSON body data
            files: Files for multipart/form-data uploads
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Use multipart/form-data if files are provided
        headers = self.headers.copy()
        if files:
            # Remove Content-Type header for multipart requests (httpx will set it)
            headers.pop("Content-Type", None)
        
        async with httpx.AsyncClient(timeout=60.0) as client:  # Longer timeout for file uploads
            try:
                if files:
                    # Multipart form data request
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=params,
                        data=json_data,  # Form data
                        files=files,  # File uploads
                    )
                else:
                    # Standard JSON request
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        params=params,
                        json=json_data,
                    )
                response.raise_for_status()
                return response.json() if response.content else {}
            except httpx.HTTPStatusError as e:
                logger.error(f"HaulPay API error: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"HaulPay API request failed: {e}")
                raise

    # Debtor endpoints
    async def list_debtors(self, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List debtors (customers/brokers who owe money).
        
        Args:
            search: Optional search query for debtor name
        """
        params = {}
        if search:
            params["search"] = search
        return await self._request("GET", "debtors_list", params=params)

    async def get_debtor_relationships(self) -> List[Dict[str, Any]]:
        """
        Get list of debtor relationships for the client.
        Use this to sync active debtors and check status.
        """
        return await self._request("GET", "debtor_relationships_list")

    async def create_debtor_relationship(
        self,
        debtor_id: str,
        external_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a relationship between client and debtor.
        
        Args:
            debtor_id: HaulPay debtor ID
            external_id: External ID to store in HaulPay (your system's ID)
        """
        payload = {"debtor_id": debtor_id}
        if external_id:
            payload["external_id"] = external_id
        return await self._request("POST", "debtor_relationships", json_data=payload)

    # Carrier endpoints
    async def list_carriers(
        self,
        search: Optional[str] = None,
        mc: Optional[str] = None,
        dot: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List carriers (trucking companies).
        
        Args:
            search: Search query for carrier name
            mc: MC number filter
            dot: DOT number filter
        """
        params = {}
        if search:
            params["search"] = search
        if mc:
            params["mc"] = mc
        if dot:
            params["dot"] = dot
        return await self._request("GET", "carrier_list", params=params)

    async def get_carrier_relationships(self) -> List[Dict[str, Any]]:
        """
        Get list of carrier relationships for the client.
        Use this to sync active carriers and check status.
        """
        return await self._request("GET", "carrier_relationships_list")

    async def create_carrier_relationship(
        self,
        carrier_id: str,
        external_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a relationship between client and carrier.
        
        Args:
            carrier_id: HaulPay carrier ID
            external_id: External ID to store in HaulPay (your system's ID)
        """
        payload = {"carrier_id": carrier_id}
        if external_id:
            payload["external_id"] = external_id
        return await self._request("POST", "carrier_relationships", json_data=payload)

    # Invoice/Factoring endpoints
    async def create_invoice(
        self,
        debtor_id: str,
        carrier_id: str,
        amount: float,
        invoice_number: str,
        due_date: str,
        line_items: Optional[List[Dict[str, Any]]] = None,
        contract_type: Optional[str] = None,
        documents: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Submit an invoice to HaulPay for factoring with optional document attachments.
        HaulPay will purchase the invoice and advance funds to the carrier.
        
        Args:
            debtor_id: HaulPay debtor ID (broker/customer who owes)
            carrier_id: HaulPay carrier ID (your company)
            amount: Invoice total amount
            invoice_number: Invoice number (external reference)
            due_date: Due date (ISO format)
            line_items: Optional line items
            contract_type: Optional contract type
            documents: Optional list of document attachments. Each dict should have:
                - file_content: bytes - File content
                - filename: str - Original filename
                - document_type: str - Type (e.g., "pod", "bol", "rate_confirmation", "invoice")
        
        Returns:
            Factoring response with:
            - id: HaulPay invoice ID
            - status: submitted, approved, funded, paid, etc.
            - advance_rate: Percentage of invoice advanced (e.g., 0.85 for 85%)
            - advance_amount: Amount advanced to carrier
            - reserve_amount: Amount held in reserve
            - factoring_fee: Fee charged by HaulPay
            - funded_at: When funds were advanced (if funded)
        """
        # Prepare form data
        form_data = {
            "debtor_id": debtor_id,
            "carrier_id": carrier_id,
            "amount": str(amount),
            "invoice_number": invoice_number,
            "due_date": due_date,
        }
        
        if line_items:
            import json
            form_data["line_items"] = json.dumps(line_items)
        if contract_type:
            form_data["contract_type"] = contract_type
        
        # Prepare file uploads if documents provided
        files = None
        if documents:
            files = {}
            for idx, doc in enumerate(documents):
                file_content = doc.get("file_content")
                filename = doc.get("filename", f"document_{idx}.pdf")
                document_type = doc.get("document_type", "attachment")
                
                if file_content:
                    # Create file tuple: (filename, content, content_type)
                    content_type = doc.get("content_type", "application/pdf")
                    files[f"documents[{idx}][file]"] = (filename, file_content, content_type)
                    files[f"documents[{idx}][type]"] = (None, document_type)
        
        return await self._request("POST", "invoices", json_data=form_data, files=files)
    
    async def upload_document_to_invoice(
        self,
        invoice_id: str,
        file_content: bytes,
        filename: str,
        document_type: str = "attachment",
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload a document to an existing HaulPay invoice.
        
        Args:
            invoice_id: HaulPay invoice ID
            file_content: File content as bytes
            filename: Original filename
            document_type: Type of document (pod, bol, rate_confirmation, invoice, etc.)
            content_type: MIME type (defaults to application/pdf)
        
        Returns:
            Upload result with document ID
        """
        if not content_type:
            content_type = "application/pdf"
        
        files = {
            "file": (filename, file_content, content_type),
            "document_type": (None, document_type),
        }
        
        return await self._request(
            "POST",
            f"invoices/{invoice_id}/documents",
            files=files,
        )

    async def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Get invoice details."""
        return await self._request("GET", f"invoices/{invoice_id}")

    async def list_invoices(
        self,
        debtor_id: Optional[str] = None,
        carrier_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List invoices with optional filters.
        
        Args:
            debtor_id: Filter by debtor
            carrier_id: Filter by carrier
            status: Filter by status (pending, paid, etc.)
        """
        params = {}
        if debtor_id:
            params["debtor_id"] = debtor_id
        if carrier_id:
            params["carrier_id"] = carrier_id
        if status:
            params["status"] = status
        
        return await self._request("GET", "invoices", params=params)

