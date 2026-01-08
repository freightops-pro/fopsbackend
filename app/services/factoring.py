"""Factoring service for managing freight factoring operations."""
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.factoring import FactoringProvider, FactoringTransaction
from app.models.load import Load
from app.schemas.factoring import (
    BatchSendToFactoringRequest,
    FactoringProviderCreate,
    FactoringProviderUpdate,
    FactoringWebhookPayload,
    SendToFactoringRequest,
)


class FactoringService:
    """Service for managing factoring operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ========== Provider Management ==========

    async def create_provider(
        self, company_id: str, provider_data: FactoringProviderCreate
    ) -> FactoringProvider:
        """Create a new factoring provider configuration."""
        provider = FactoringProvider(
            id=str(uuid4()),
            company_id=company_id,
            provider_name=provider_data.provider_name,
            factoring_rate=provider_data.factoring_rate,
            advance_rate=provider_data.advance_rate,
            payment_terms_days=provider_data.payment_terms_days,
            is_active=provider_data.is_active,
            api_key=provider_data.api_key,
            api_endpoint=provider_data.api_endpoint,
            webhook_secret=provider_data.webhook_secret,
            is_configured=bool(provider_data.api_key and provider_data.api_endpoint),
        )

        self.db.add(provider)
        await self.db.commit()
        await self.db.refresh(provider)
        return provider

    async def get_provider(self, company_id: str, provider_id: str) -> Optional[FactoringProvider]:
        """Get a factoring provider by ID."""
        query = select(FactoringProvider).where(
            FactoringProvider.company_id == company_id,
            FactoringProvider.id == provider_id,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_active_provider(self, company_id: str) -> Optional[FactoringProvider]:
        """Get the active factoring provider for a company."""
        query = select(FactoringProvider).where(
            FactoringProvider.company_id == company_id,
            FactoringProvider.is_active == True,
            FactoringProvider.is_configured == True,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_providers(self, company_id: str) -> List[FactoringProvider]:
        """List all factoring providers for a company."""
        query = select(FactoringProvider).where(
            FactoringProvider.company_id == company_id
        ).order_by(FactoringProvider.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_provider(
        self, company_id: str, provider_id: str, provider_data: FactoringProviderUpdate
    ) -> Optional[FactoringProvider]:
        """Update a factoring provider."""
        provider = await self.get_provider(company_id, provider_id)
        if not provider:
            return None

        # Update fields
        for field, value in provider_data.model_dump(exclude_unset=True).items():
            setattr(provider, field, value)

        # Update is_configured status
        provider.is_configured = bool(provider.api_key and provider.api_endpoint)
        provider.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(provider)
        return provider

    # ========== Transaction Management ==========

    async def send_to_factoring(
        self, company_id: str, request: SendToFactoringRequest
    ) -> FactoringTransaction:
        """Send a single load to factoring."""
        # Get active provider
        provider = await self.get_active_provider(company_id)
        if not provider:
            raise ValueError("No active factoring provider configured")

        # Get load
        load_query = select(Load).where(
            Load.company_id == company_id,
            Load.id == request.load_id,
        )
        load_result = await self.db.execute(load_query)
        load = load_result.scalar_one_or_none()
        if not load:
            raise ValueError("Load not found")

        # Calculate factoring amounts
        invoice_amount = float(load.base_rate)
        factoring_fee = invoice_amount * (provider.factoring_rate / 100)
        advance_amount = invoice_amount * (provider.advance_rate / 100)
        reserve_amount = invoice_amount - advance_amount

        # Create transaction
        transaction = FactoringTransaction(
            id=str(uuid4()),
            company_id=company_id,
            provider_id=provider.id,
            load_id=request.load_id,
            invoice_id=request.invoice_id,
            invoice_amount=invoice_amount,
            factoring_fee=factoring_fee,
            advance_amount=advance_amount,
            reserve_amount=reserve_amount,
            status="PENDING",
            documents_submitted=request.documents,
            notes=request.notes,
        )

        self.db.add(transaction)

        # Update load
        load.factoring_enabled = "true"
        load.factoring_status = "PENDING"
        load.factored_amount = advance_amount
        load.factoring_fee_amount = factoring_fee

        await self.db.commit()
        await self.db.refresh(transaction)

        # Send to factoring provider API (placeholder)
        await self._send_to_provider_api(provider, transaction, load)

        return transaction

    async def batch_send_to_factoring(
        self, company_id: str, request: BatchSendToFactoringRequest
    ) -> List[FactoringTransaction]:
        """Send multiple loads to factoring in a batch."""
        batch_id = str(uuid4())
        transactions = []

        for load_id in request.load_ids:
            send_request = SendToFactoringRequest(
                load_id=load_id,
                notes=request.batch_notes,
            )
            try:
                transaction = await self.send_to_factoring(company_id, send_request)
                transaction.batch_id = batch_id
                transactions.append(transaction)
            except Exception as e:
                # Log error but continue with other loads
                print(f"Failed to send load {load_id} to factoring: {e}")
                continue

        await self.db.commit()
        return transactions

    async def get_transaction(
        self, company_id: str, transaction_id: str
    ) -> Optional[FactoringTransaction]:
        """Get a factoring transaction by ID."""
        query = select(FactoringTransaction).where(
            FactoringTransaction.company_id == company_id,
            FactoringTransaction.id == transaction_id,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_transactions(
        self, company_id: str, status: Optional[str] = None
    ) -> List[FactoringTransaction]:
        """List factoring transactions for a company."""
        query = select(FactoringTransaction).where(
            FactoringTransaction.company_id == company_id
        )

        if status:
            query = query.where(FactoringTransaction.status == status)

        query = query.order_by(FactoringTransaction.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def process_webhook(
        self, company_id: str, payload: FactoringWebhookPayload
    ) -> Optional[FactoringTransaction]:
        """Process a webhook from the factoring provider."""
        # Find transaction by external reference or internal ID
        query = select(FactoringTransaction).where(
            FactoringTransaction.company_id == company_id,
        )

        if payload.external_reference_id:
            query = query.where(
                FactoringTransaction.external_reference_id == payload.external_reference_id
            )
        else:
            query = query.where(FactoringTransaction.id == payload.transaction_id)

        result = await self.db.execute(query)
        transaction = result.scalar_one_or_none()

        if not transaction:
            return None

        # Update transaction status
        transaction.status = payload.status
        transaction.updated_at = datetime.utcnow()

        # Update timestamps based on status
        if payload.status == "SENT" and not transaction.sent_at:
            transaction.sent_at = payload.timestamp
        elif payload.status == "ACCEPTED" and not transaction.accepted_at:
            transaction.accepted_at = payload.timestamp
        elif payload.status == "VERIFIED" and not transaction.verified_at:
            transaction.verified_at = payload.timestamp
        elif payload.status == "FUNDED" and not transaction.funded_at:
            transaction.funded_at = payload.timestamp
        elif payload.status == "PAID" and not transaction.paid_at:
            transaction.paid_at = payload.timestamp
        elif payload.status == "REJECTED" and not transaction.rejected_at:
            transaction.rejected_at = payload.timestamp
            transaction.rejection_reason = payload.rejection_reason

        # Update payment details
        if payload.payment_method:
            transaction.payment_method = payload.payment_method
        if payload.payment_reference:
            transaction.payment_reference = payload.payment_reference

        # Update associated load status
        load_query = select(Load).where(Load.id == transaction.load_id)
        load_result = await self.db.execute(load_query)
        load = load_result.scalar_one_or_none()

        if load:
            load.factoring_status = payload.status

        await self.db.commit()
        await self.db.refresh(transaction)
        return transaction

    async def get_factoring_summary(self, company_id: str) -> Dict:
        """Get summary of factoring activity for a company."""
        transactions = await self.list_transactions(company_id)

        total_factored = sum(t.invoice_amount for t in transactions)
        total_fees = sum(t.factoring_fee for t in transactions)
        pending = sum(1 for t in transactions if t.status == "PENDING")
        funded = sum(1 for t in transactions if t.status == "FUNDED")
        paid = sum(1 for t in transactions if t.status == "PAID")

        return {
            "total_transactions": len(transactions),
            "total_factored_amount": total_factored,
            "total_fees": total_fees,
            "pending_count": pending,
            "funded_count": funded,
            "paid_count": paid,
        }

    # ========== Private Methods ==========

    async def _send_to_provider_api(
        self, provider: FactoringProvider, transaction: FactoringTransaction, load: Load
    ) -> None:
        """
        Send transaction to factoring provider's API (HaulPay).

        HaulPay Integration Details:
        - Base URL: https://api.haulpay.io/v1/external_api/
        - Staging URL: https://api-staging.haulpay.io/v1/external_api/
        - Authentication: Bearer token in Authorization header
        - Format: JSON request/response

        This is a placeholder implementation. In production, this would:
        1. Format the request according to HaulPay's API spec
        2. Include Bearer token authentication
        3. Send load/invoice details and documents
        4. Handle the response and update transaction accordingly
        """
        # TODO: Implement actual HaulPay API integration
        # For now, just mark as sent
        transaction.status = "SENT"
        transaction.sent_at = datetime.utcnow()
        transaction.external_reference_id = f"HAULPAY-{transaction.id[:8]}"

        # Placeholder for HaulPay API call
        # Production implementation would look like:
        #
        # import httpx
        #
        # base_url = provider.api_endpoint or "https://api.haulpay.io/v1/external_api"
        #
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(
        #         f"{base_url}/invoices",  # Actual endpoint TBD from HaulPay docs
        #         headers={
        #             "Authorization": f"Bearer {provider.api_key}",
        #             "Content-Type": "application/json"
        #         },
        #         json={
        #             "invoice_id": transaction.invoice_id,
        #             "invoice_number": transaction.invoice_id,
        #             "amount": transaction.invoice_amount,
        #             "customer_name": load.customer_name,
        #             "load_id": load.id,
        #             "documents": transaction.documents_submitted,
        #             "metadata": {
        #                 "load_type": load.load_type,
        #                 "commodity": load.commodity,
        #             }
        #         },
        #         timeout=30.0
        #     )
        #
        #     if response.status_code in [200, 201, 202]:
        #         data = response.json()
        #         transaction.external_reference_id = data.get("reference_id") or data.get("id")
        #         transaction.status = "SENT"
        #     else:
        #         transaction.status = "REJECTED"
        #         transaction.rejection_reason = f"API Error: {response.status_code} - {response.text}"
        #         transaction.rejected_at = datetime.utcnow()

        await self.db.commit()
