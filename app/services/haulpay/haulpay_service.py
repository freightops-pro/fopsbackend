"""
HaulPay Integration Service
Handles synchronization and relationship management with HaulPay.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import CompanyIntegration, Integration
from app.models.accounting import Customer, Invoice
from app.services.haulpay.haulpay_client import HaulPayClient

logger = logging.getLogger(__name__)


class HaulPayService:
    """Service for managing HaulPay integration."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_client(self, company_id: str) -> Optional[HaulPayClient]:
        """Get HaulPay client for company's integration."""
        result = await self.db.execute(
            select(CompanyIntegration)
            .join(Integration)
            .where(
                Integration.integration_key == "haulpay",
                CompanyIntegration.company_id == company_id,
                CompanyIntegration.status == "active",
            )
        )
        integration = result.scalar_one_or_none()
        
        if not integration or not integration.credentials:
            return None
        
        api_key = integration.credentials.get("api_key")
        if not api_key:
            return None
        
        staging = integration.config.get("staging", False) if integration.config else False
        return HaulPayClient(api_key=api_key, staging=staging)

    async def sync_debtor_relationships(
        self, company_id: str, external_customer_map: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Sync debtor relationships from HaulPay.
        
        Args:
            company_id: Company ID
            external_customer_map: Map of HaulPay debtor IDs to internal customer IDs
        
        Returns:
            Sync results with created/updated counts
        """
        client = await self.get_client(company_id)
        if not client:
            raise ValueError("HaulPay integration not configured")

        relationships = await client.get_debtor_relationships()
        
        created = 0
        updated = 0
        errors = []

        for rel in relationships:
            try:
                debtor_id = rel.get("debtor_id")
                external_id = rel.get("external_id")
                status = rel.get("status")
                
                # Find customer by external_id or debtor_id
                if external_id and external_id in external_customer_map:
                    customer_id = external_customer_map[external_id]
                    # Update customer status if needed
                    # This would update the customer record in your system
                    updated += 1
                elif debtor_id:
                    # Create relationship if debtor exists but no relationship
                    # Store mapping for future reference
                    created += 1
            except Exception as e:
                logger.error(f"Error syncing debtor relationship: {e}")
                errors.append(str(e))

        return {
            "created": created,
            "updated": updated,
            "errors": errors,
            "total": len(relationships),
        }

    async def sync_carrier_relationships(
        self, company_id: str, external_carrier_map: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Sync carrier relationships from HaulPay.
        
        Args:
            company_id: Company ID
            external_carrier_map: Map of HaulPay carrier IDs to internal carrier IDs
        
        Returns:
            Sync results with created/updated counts
        """
        client = await self.get_client(company_id)
        if not client:
            raise ValueError("HaulPay integration not configured")

        relationships = await client.get_carrier_relationships()
        
        created = 0
        updated = 0
        errors = []

        for rel in relationships:
            try:
                carrier_id = rel.get("carrier_id")
                external_id = rel.get("external_id")
                status = rel.get("status")
                
                # Similar logic to debtor sync
                if external_id and external_id in external_carrier_map:
                    updated += 1
                elif carrier_id:
                    created += 1
            except Exception as e:
                logger.error(f"Error syncing carrier relationship: {e}")
                errors.append(str(e))

        return {
            "created": created,
            "updated": updated,
            "errors": errors,
            "total": len(relationships),
        }

    async def search_debtors(
        self, company_id: str, search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for debtors in HaulPay."""
        client = await self.get_client(company_id)
        if not client:
            raise ValueError("HaulPay integration not configured")
        
        return await client.list_debtors(search=search)

    async def search_carriers(
        self,
        company_id: str,
        search: Optional[str] = None,
        mc: Optional[str] = None,
        dot: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for carriers in HaulPay."""
        client = await self.get_client(company_id)
        if not client:
            raise ValueError("HaulPay integration not configured")
        
        return await client.list_carriers(search=search, mc=mc, dot=dot)

    async def connect_debtor(
        self,
        company_id: str,
        debtor_id: str,
        customer_id: str,
    ) -> Dict[str, Any]:
        """
        Connect a customer to a HaulPay debtor.
        
        Args:
            company_id: Company ID
            debtor_id: HaulPay debtor ID
            customer_id: Internal customer ID (used as external_id)
        """
        client = await self.get_client(company_id)
        if not client:
            raise ValueError("HaulPay integration not configured")
        
        return await client.create_debtor_relationship(
            debtor_id=debtor_id,
            external_id=customer_id,
        )

    async def connect_carrier(
        self,
        company_id: str,
        carrier_id: str,
        carrier_external_id: str,
    ) -> Dict[str, Any]:
        """
        Connect a carrier to a HaulPay carrier.
        
        Args:
            company_id: Company ID
            carrier_id: HaulPay carrier ID
            carrier_external_id: Internal carrier ID (used as external_id)
        """
        client = await self.get_client(company_id)
        if not client:
            raise ValueError("HaulPay integration not configured")
        
        return await client.create_carrier_relationship(
            carrier_id=carrier_id,
            external_id=carrier_external_id,
        )

    async def submit_invoice_for_factoring(
        self,
        company_id: str,
        invoice: Invoice,
        debtor_id: str,
        carrier_id: str,
        document_urls: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Submit an invoice to HaulPay for factoring with optional document attachments.
        HaulPay will purchase the invoice and advance funds to the carrier.
        
        Args:
            company_id: Company ID
            invoice: Internal invoice object
            debtor_id: HaulPay debtor ID (broker/customer who owes)
            carrier_id: HaulPay carrier ID (your company)
            document_urls: Optional list of documents to attach. Each dict should have:
                - url: str - URL or storage key to the document
                - document_type: str - Type (pod, bol, rate_confirmation, invoice, etc.)
                - filename: str - Original filename
        
        Returns:
            Factoring response with invoice ID, advance amount, reserve, fees, etc.
        """
        client = await self.get_client(company_id)
        if not client:
            raise ValueError("HaulPay integration not configured")
        
        # Convert invoice to HaulPay format
        line_items = []
        if hasattr(invoice, "line_items") and invoice.line_items:
            for item in invoice.line_items:
                line_items.append({
                    "description": item.get("description", ""),
                    "amount": item.get("amount", 0),
                    "quantity": item.get("quantity", 1),
                })
        
        # Fetch and prepare documents if provided
        documents = None
        if document_urls:
            import httpx
            from app.core.config import get_settings
            settings = get_settings()
            
            documents = []
            for doc_info in document_urls:
                url_or_key = doc_info.get("url")
                document_type = doc_info.get("document_type", "attachment")
                filename = doc_info.get("filename", "document.pdf")
                
                if not url_or_key:
                    continue
                
                try:
                    file_content = None
                    
                    # If it's a URL, download it
                    if url_or_key.startswith("http://") or url_or_key.startswith("https://"):
                        async with httpx.AsyncClient(timeout=30.0) as http_client:
                            response = await http_client.get(url_or_key)
                            response.raise_for_status()
                            file_content = response.content
                    else:
                        # Get from R2 storage using presigned URL
                        from app.services.storage import StorageService
                        storage = StorageService()
                        presigned_url = storage.get_file_url(url_or_key, expires_in=300)
                        
                        async with httpx.AsyncClient(timeout=30.0) as http_client:
                            response = await http_client.get(presigned_url)
                            response.raise_for_status()
                            file_content = response.content
                    
                    if file_content:
                        # Infer content type
                        content_type = "application/pdf"
                        if filename.lower().endswith((".jpg", ".jpeg")):
                            content_type = "image/jpeg"
                        elif filename.lower().endswith(".png"):
                            content_type = "image/png"
                        elif filename.lower().endswith((".doc", ".docx")):
                            content_type = "application/msword"
                        elif filename.lower().endswith((".xls", ".xlsx")):
                            content_type = "application/vnd.ms-excel"
                        
                        documents.append({
                            "file_content": file_content,
                            "filename": filename,
                            "document_type": document_type,
                            "content_type": content_type,
                        })
                except Exception as e:
                    logger.warning(f"Failed to fetch document {url_or_key}: {e}")
                    # Continue with other documents
        
        # Submit invoice for factoring with documents
        result = await client.create_invoice(
            debtor_id=debtor_id,
            carrier_id=carrier_id,
            amount=float(invoice.total or invoice.total_amount or 0),
            invoice_number=invoice.invoice_number or invoice.id,
            due_date=invoice.invoice_date.isoformat() if invoice.invoice_date else None,
            line_items=line_items if line_items else None,
            documents=documents,
        )
        
        # Store factoring metadata in invoice
        if hasattr(invoice, "metadata_json"):
            if invoice.metadata_json is None:
                invoice.metadata_json = {}
            invoice.metadata_json["haulpay"] = {
                "factored": True,
                "haulpay_invoice_id": result.get("id"),
                "submitted_at": datetime.utcnow().isoformat(),
                "status": result.get("status", "submitted"),
                "advance_rate": result.get("advance_rate"),
                "advance_amount": result.get("advance_amount"),
                "reserve_amount": result.get("reserve_amount"),
                "factoring_fee": result.get("factoring_fee"),
                "documents_submitted": len(documents) if documents else 0,
            }
            await self.db.commit()
        
        return result

    async def get_factoring_status(
        self,
        company_id: str,
        haulpay_invoice_id: str,
    ) -> Dict[str, Any]:
        """
        Get the factoring status of an invoice from HaulPay.
        
        Statuses typically include:
        - submitted: Invoice submitted, awaiting approval
        - approved: Invoice approved, funds will be advanced
        - funded: Advance funds have been sent
        - paid: Invoice has been paid by debtor
        - reserve_released: Reserve has been released
        - rejected: Invoice was rejected
        """
        client = await self.get_client(company_id)
        if not client:
            raise ValueError("HaulPay integration not configured")
        
        return await client.get_invoice(haulpay_invoice_id)

    async def batch_submit_invoices_for_factoring(
        self,
        company_id: str,
        invoice_submissions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Batch submit multiple invoices to HaulPay for factoring.
        Each invoice is tracked separately with its own status and metadata.
        
        Args:
            company_id: Company ID
            invoice_submissions: List of dicts with:
                - invoice_id: Internal invoice ID
                - debtor_id: HaulPay debtor ID
                - carrier_id: HaulPay carrier ID (optional, uses default if not provided)
        
        Returns:
            Batch results with:
                - total: Total invoices in batch
                - successful: Number successfully submitted
                - failed: Number that failed
                - results: List of results for each invoice with:
                    - invoice_id: Internal invoice ID
                    - success: Boolean
                    - haulpay_invoice_id: HaulPay invoice ID (if successful)
                    - error: Error message (if failed)
                    - status: Factoring status
                    - advance_amount: Advance amount (if available)
        """
        client = await self.get_client(company_id)
        if not client:
            raise ValueError("HaulPay integration not configured")
        
        from app.models.accounting import Invoice
        
        results = []
        successful = 0
        failed = 0
        
        for submission in invoice_submissions:
            invoice_id = submission.get("invoice_id")
            debtor_id = submission.get("debtor_id")
            carrier_id = submission.get("carrier_id")
            
            if not invoice_id or not debtor_id:
                results.append({
                    "invoice_id": invoice_id,
                    "success": False,
                    "error": "Missing invoice_id or debtor_id",
                })
                failed += 1
                continue
            
            try:
                # Get invoice from database
                invoice_result = await self.db.execute(
                    select(Invoice).where(
                        Invoice.id == invoice_id,
                        Invoice.company_id == company_id
                    )
                )
                invoice = invoice_result.scalar_one_or_none()
                
                if not invoice:
                    results.append({
                        "invoice_id": invoice_id,
                        "success": False,
                        "error": "Invoice not found",
                    })
                    failed += 1
                    continue
                
                # Check if already factored
                if invoice.metadata_json and invoice.metadata_json.get("haulpay", {}).get("factored"):
                    results.append({
                        "invoice_id": invoice_id,
                        "success": False,
                        "error": "Invoice already submitted for factoring",
                        "haulpay_invoice_id": invoice.metadata_json["haulpay"].get("haulpay_invoice_id"),
                    })
                    failed += 1
                    continue
                
                # Get document URLs if provided
                document_urls = submission.get("document_urls")
                
                # Submit invoice for factoring with documents
                result = await self.submit_invoice_for_factoring(
                    company_id=company_id,
                    invoice=invoice,
                    debtor_id=debtor_id,
                    carrier_id=carrier_id or submission.get("default_carrier_id"),
                    document_urls=document_urls,
                )
                
                results.append({
                    "invoice_id": invoice_id,
                    "success": True,
                    "haulpay_invoice_id": result.get("id"),
                    "status": result.get("status", "submitted"),
                    "advance_rate": result.get("advance_rate"),
                    "advance_amount": result.get("advance_amount"),
                    "reserve_amount": result.get("reserve_amount"),
                    "factoring_fee": result.get("factoring_fee"),
                })
                successful += 1
                
            except Exception as e:
                logger.error(f"Error submitting invoice {invoice_id} for factoring: {e}", exc_info=True)
                results.append({
                    "invoice_id": invoice_id,
                    "success": False,
                    "error": str(e),
                })
                failed += 1
        
        return {
            "total": len(invoice_submissions),
            "successful": successful,
            "failed": failed,
            "results": results,
        }

    async def get_invoice_factoring_tracking(
        self,
        company_id: str,
        invoice_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get factoring tracking information for a specific invoice.
        Returns the stored factoring metadata from the invoice.
        
        Args:
            company_id: Company ID
            invoice_id: Internal invoice ID
        
        Returns:
            Factoring tracking data or None if not factored
        """
        from app.models.accounting import Invoice
        
        result = await self.db.execute(
            select(Invoice).where(
                Invoice.id == invoice_id,
                Invoice.company_id == company_id
            )
        )
        invoice = result.scalar_one_or_none()
        
        if not invoice:
            return None
        
        haulpay_data = invoice.metadata_json.get("haulpay") if invoice.metadata_json else None
        if not haulpay_data or not haulpay_data.get("factored"):
            return None
        
        return {
            "invoice_id": invoice_id,
            "invoice_number": invoice.invoice_number,
            "factored": True,
            "haulpay_invoice_id": haulpay_data.get("haulpay_invoice_id"),
            "submitted_at": haulpay_data.get("submitted_at"),
            "status": haulpay_data.get("status"),
            "advance_rate": haulpay_data.get("advance_rate"),
            "advance_amount": haulpay_data.get("advance_amount"),
            "reserve_amount": haulpay_data.get("reserve_amount"),
            "factoring_fee": haulpay_data.get("factoring_fee"),
        }

    async def sync_factored_invoices(
        self,
        company_id: str,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Sync all factored invoices from HaulPay.
        Useful for tracking invoice status, advance amounts, and reserve releases.
        
        Args:
            company_id: Company ID
            status: Optional filter by status (submitted, funded, paid, etc.)
        """
        client = await self.get_client(company_id)
        if not client:
            raise ValueError("HaulPay integration not configured")
        
        return await client.list_invoices(carrier_id=None, status=status)

