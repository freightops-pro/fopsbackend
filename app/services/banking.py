from __future__ import annotations

import uuid
from datetime import datetime
from typing import List

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


class BankingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

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
        account = BankingAccount(
            id=str(uuid.uuid4()),
            company_id=company_id,
            customer_id=payload.customer_id,
            account_type=payload.account_type,
            nickname=payload.nickname,
            status="active",
            balance=0,
        )
        self.db.add(account)
        await self.db.commit()
        await self.db.refresh(account)
        return BankingAccountResponse.model_validate(account)

    async def issue_card(self, payload: BankingCardCreate) -> BankingCardResponse:
        card = BankingCard(
            id=str(uuid.uuid4()),
            account_id=payload.account_id,
            cardholder_name=payload.cardholder_name,
            card_type=payload.card_type,
            last_four="0000",
            status="active",
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

