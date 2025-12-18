from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.banking import BankingAccount, BankingCard, BankingCustomer, BankingTransaction
from app.schemas.banking import (
    BankingAccountCreate,
    BankingAccountResponse,
    BankingCardCreate,
    BankingCardResponse,
    BankingCustomerCreate,
    BankingCustomerResponse,
    BankingTransactionResponse,
)
from app.services.synctera_service import (
    get_synctera_client,
    SyncteraClient,
    SyncteraError,
    AccountCreateRequest,
    CardCreateRequest,
)

logger = logging.getLogger(__name__)


class BankingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._synctera: Optional[SyncteraClient] = None

    @property
    def synctera(self) -> SyncteraClient:
        """Get Synctera client (lazy load)."""
        if self._synctera is None:
            self._synctera = get_synctera_client()
        return self._synctera

    async def ensure_customer(self, company_id: str, payload: BankingCustomerCreate) -> BankingCustomerResponse:
        existing = await self.db.execute(
            select(BankingCustomer).where(BankingCustomer.company_id == company_id)
        )
        customer = existing.scalar_one_or_none()
        if customer:
            return BankingCustomerResponse.model_validate(customer)

        customer = BankingCustomer(
            id=str(uuid.uuid4()),
            company_id=company_id,
            status="pending",
        )
        self.db.add(customer)
        await self.db.commit()
        await self.db.refresh(customer)
        return BankingCustomerResponse.model_validate(customer)

    async def list_accounts(self, company_id: str) -> List[BankingAccountResponse]:
        result = await self.db.execute(
            select(BankingAccount)
            .where(BankingAccount.company_id == company_id)
            .order_by(BankingAccount.created_at.desc())
        )
        return [BankingAccountResponse.model_validate(account) for account in result.scalars().all()]

    async def create_account(self, company_id: str, payload: BankingAccountCreate) -> BankingAccountResponse:
        """Create a new bank account, optionally via Synctera."""
        # Get customer to find Synctera business ID
        customer_result = await self.db.execute(
            select(BankingCustomer).where(BankingCustomer.id == payload.customer_id)
        )
        customer = customer_result.scalar_one_or_none()

        synctera_account_id = None
        account_number = None
        routing_number = None

        # If Synctera is configured and customer has Synctera business ID, create in Synctera
        if self.synctera.is_configured and customer and customer.synctera_business_id:
            try:
                synctera_request = AccountCreateRequest(
                    account_type=payload.account_type,
                    business_id=customer.synctera_business_id,
                    nickname=payload.nickname,
                )
                synctera_response = await self.synctera.create_account(synctera_request)
                synctera_account_id = synctera_response.get("id")
                account_number = synctera_response.get("account_number_masked")
                routing_number = synctera_response.get("routing_number")
                logger.info(f"Created Synctera account: {synctera_account_id}")
            except SyncteraError as e:
                logger.error(f"Synctera account creation failed: {e.message}")
                # Continue with local-only account if Synctera fails
            except Exception as e:
                logger.error(f"Unexpected error creating Synctera account: {e}")

        account = BankingAccount(
            id=str(uuid.uuid4()),
            company_id=company_id,
            customer_id=payload.customer_id,
            account_type=payload.account_type,
            nickname=payload.nickname,
            status="active" if synctera_account_id else "pending",
            balance=0,
            synctera_id=synctera_account_id,
            account_number=account_number,
            routing_number=routing_number,
        )
        self.db.add(account)
        await self.db.commit()
        await self.db.refresh(account)
        return BankingAccountResponse.model_validate(account)

    async def issue_card(self, payload: BankingCardCreate) -> BankingCardResponse:
        """Issue a new card, optionally via Synctera."""
        # Get account to find Synctera account ID
        account_result = await self.db.execute(
            select(BankingAccount).where(BankingAccount.id == payload.account_id)
        )
        account = account_result.scalar_one_or_none()

        synctera_card_id = None
        last_four = "0000"
        expiration_month = None
        expiration_year = None

        # If Synctera is configured and account has Synctera ID, create in Synctera
        if self.synctera.is_configured and account and account.synctera_id:
            try:
                # Get card products to find appropriate product ID
                card_products = await self.synctera.list_card_products()
                card_product_id = None
                card_type = getattr(payload, 'card_type', 'virtual').lower()

                # Find matching card product
                for product in card_products:
                    if card_type == "virtual" and product.get("form") == "VIRTUAL":
                        card_product_id = product.get("id")
                        break
                    elif card_type == "physical" and product.get("form") == "PHYSICAL":
                        card_product_id = product.get("id")
                        break

                if card_product_id:
                    synctera_request = CardCreateRequest(
                        account_id=account.synctera_id,
                        card_product_id=card_product_id,
                        type=card_type.upper(),
                        form=card_type.upper(),
                    )
                    synctera_response = await self.synctera.create_card(synctera_request)
                    synctera_card_id = synctera_response.get("id")
                    last_four = synctera_response.get("last_four", "0000")
                    expiration_month = synctera_response.get("expiration_month")
                    expiration_year = synctera_response.get("expiration_year")
                    logger.info(f"Created Synctera card: {synctera_card_id}")
                else:
                    logger.warning(f"No card product found for type: {card_type}")
            except SyncteraError as e:
                logger.error(f"Synctera card creation failed: {e.message}")
            except Exception as e:
                logger.error(f"Unexpected error creating Synctera card: {e}")

        card = BankingCard(
            id=str(uuid.uuid4()),
            account_id=payload.account_id,
            cardholder_name=payload.cardholder_name,
            card_type=getattr(payload, 'card_type', 'virtual'),
            last_four=last_four,
            status="active" if synctera_card_id else "pending",
            synctera_id=synctera_card_id,
            expiration_month=expiration_month,
            expiration_year=expiration_year,
        )
        self.db.add(card)
        await self.db.commit()
        await self.db.refresh(card)
        return BankingCardResponse.model_validate(card)

    async def list_cards(self, account_id: str) -> List[BankingCardResponse]:
        result = await self.db.execute(
            select(BankingCard)
            .where(BankingCard.account_id == account_id)
            .order_by(BankingCard.created_at.desc())
        )
        return [BankingCardResponse.model_validate(card) for card in result.scalars().all()]

    async def list_transactions(self, account_id: str) -> List[BankingTransactionResponse]:
        result = await self.db.execute(
            select(BankingTransaction)
            .where(BankingTransaction.account_id == account_id)
            .order_by(BankingTransaction.posted_at.desc())
        )
        return [BankingTransactionResponse.model_validate(txn) for txn in result.scalars().all()]

    async def record_transaction(
        self,
        account_id: str,
        amount: float,
        description: str,
        category: str = "general",
    ) -> BankingTransactionResponse:
        txn = BankingTransaction(
            id=str(uuid.uuid4()),
            account_id=account_id,
            amount=amount,
            description=description,
            category=category,
            posted_at=datetime.utcnow(),
            pending=False,
        )
        self.db.add(txn)
        await self.db.commit()
        await self.db.refresh(txn)
        return BankingTransactionResponse.model_validate(txn)

