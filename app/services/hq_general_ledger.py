"""HQ General Ledger Manager - Double-Entry Accounting Engine.

This is the accounting core that tracks every penny in the system.
Follows GAAP double-entry bookkeeping: Debits always equal Credits.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
import logging

from sqlalchemy import select, func, and_, or_, case, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hq_general_ledger import (
    HQChartOfAccounts,
    HQJournalEntry,
    HQGeneralLedgerEntry,
    HQUsageLog,
    HQRecurringBilling,
    AccountType,
    AccountSubtype,
    JournalEntryStatus,
    UsageMetricType,
    BillingFrequency,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes for Clean Interface
# ============================================================================

@dataclass
class LedgerLine:
    """A single line in a journal entry (either debit or credit)."""
    account_number: str
    amount: Decimal
    is_debit: bool
    memo: Optional[str] = None
    tenant_id: Optional[str] = None


@dataclass
class JournalEntryInput:
    """Input for creating a journal entry."""
    description: str
    lines: List[LedgerLine]
    transaction_date: Optional[datetime] = None
    reference: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    tenant_id: Optional[str] = None


@dataclass
class AccountBalance:
    """Account balance summary."""
    account_id: str
    account_number: str
    account_name: str
    account_type: AccountType
    debit_total: Decimal
    credit_total: Decimal
    balance: Decimal


@dataclass
class ProfitLossReport:
    """Monthly P&L report structure."""
    period_start: date
    period_end: date
    revenue: Dict[str, Decimal]
    cost_of_revenue: Dict[str, Decimal]
    expenses: Dict[str, Decimal]
    total_revenue: Decimal
    total_cogs: Decimal
    gross_profit: Decimal
    total_expenses: Decimal
    net_income: Decimal
    tenant_breakdown: Optional[Dict[str, Dict[str, Decimal]]] = None


@dataclass
class BalanceSheetReport:
    """Balance sheet report structure."""
    as_of_date: date
    assets: Dict[str, Decimal]
    liabilities: Dict[str, Decimal]
    equity: Dict[str, Decimal]
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal


# ============================================================================
# General Ledger Manager
# ============================================================================

class GeneralLedgerManager:
    """
    Core accounting engine implementing double-entry bookkeeping.

    Every financial transaction creates balanced journal entries where:
    - Total Debits = Total Credits
    - Assets and Expenses increase with debits
    - Liabilities, Equity, and Revenue increase with credits
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._account_cache: Dict[str, HQChartOfAccounts] = {}

    # ========================================================================
    # Journal Entry Operations
    # ========================================================================

    async def create_journal_entry(
        self,
        entry: JournalEntryInput,
        created_by_id: Optional[str] = None,
        auto_post: bool = False,
    ) -> HQJournalEntry:
        """
        Create a new journal entry with balanced debit/credit lines.

        Args:
            entry: The journal entry input with lines
            created_by_id: ID of the user creating the entry
            auto_post: Whether to automatically post the entry

        Returns:
            The created journal entry

        Raises:
            ValueError: If debits don't equal credits
        """
        # Validate balance
        total_debits, total_credits = self._calculate_totals(entry.lines)
        if total_debits != total_credits:
            raise ValueError(
                f"Journal entry is unbalanced: "
                f"Debits={total_debits}, Credits={total_credits}"
            )

        # Generate entry number
        entry_number = await self._generate_entry_number()

        # Create journal entry header
        journal_entry = HQJournalEntry(
            id=str(uuid.uuid4()),
            entry_number=entry_number,
            reference=entry.reference,
            transaction_date=entry.transaction_date or datetime.utcnow(),
            description=entry.description,
            status=JournalEntryStatus.DRAFT,
            source_type=entry.source_type,
            source_id=entry.source_id,
            tenant_id=entry.tenant_id,
            total_debits=total_debits,
            total_credits=total_credits,
            created_by_id=created_by_id,
        )
        self.db.add(journal_entry)

        # Create individual GL entries
        for line in entry.lines:
            account = await self._get_account_by_number(line.account_number)
            if not account:
                raise ValueError(f"Account not found: {line.account_number}")

            gl_entry = HQGeneralLedgerEntry(
                id=str(uuid.uuid4()),
                journal_entry_id=journal_entry.id,
                debit_account_id=account.id if line.is_debit else None,
                credit_account_id=account.id if not line.is_debit else None,
                amount=line.amount,
                memo=line.memo,
                tenant_id=line.tenant_id or entry.tenant_id,
            )
            self.db.add(gl_entry)

        await self.db.flush()

        # Auto-post if requested
        if auto_post:
            await self.post_journal_entry(journal_entry.id, created_by_id)

        return journal_entry

    async def post_journal_entry(
        self,
        journal_entry_id: str,
        posted_by_id: Optional[str] = None,
    ) -> HQJournalEntry:
        """Post a journal entry, making it immutable and updating account balances."""
        result = await self.db.execute(
            select(HQJournalEntry).where(HQJournalEntry.id == journal_entry_id)
        )
        entry = result.scalar_one_or_none()

        if not entry:
            raise ValueError(f"Journal entry not found: {journal_entry_id}")

        if entry.status == JournalEntryStatus.POSTED:
            raise ValueError("Journal entry is already posted")

        if entry.status == JournalEntryStatus.VOID:
            raise ValueError("Cannot post a voided entry")

        # Update account balances
        await self._update_account_balances(journal_entry_id)

        # Mark as posted
        entry.status = JournalEntryStatus.POSTED
        entry.posted_by_id = posted_by_id
        entry.posted_at = datetime.utcnow()

        await self.db.flush()
        return entry

    async def void_journal_entry(
        self,
        journal_entry_id: str,
        voided_by_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> HQJournalEntry:
        """Void a journal entry by creating a reversing entry."""
        result = await self.db.execute(
            select(HQJournalEntry).where(HQJournalEntry.id == journal_entry_id)
        )
        entry = result.scalar_one_or_none()

        if not entry:
            raise ValueError(f"Journal entry not found: {journal_entry_id}")

        if entry.status == JournalEntryStatus.VOID:
            raise ValueError("Journal entry is already voided")

        # If posted, create reversing entry
        if entry.status == JournalEntryStatus.POSTED:
            await self._create_reversing_entry(entry, voided_by_id, reason)

        # Mark original as void
        entry.status = JournalEntryStatus.VOID
        entry.voided_at = datetime.utcnow()
        entry.voided_by_id = voided_by_id

        await self.db.flush()
        return entry

    # ========================================================================
    # Common Accounting Transactions
    # ========================================================================

    async def book_subscription_revenue(
        self,
        tenant_id: str,
        amount: Decimal,
        description: str,
        invoice_id: Optional[str] = None,
    ) -> HQJournalEntry:
        """
        Book subscription revenue for a tenant.

        Debit: Accounts Receivable (1200)
        Credit: SaaS Revenue (4010)
        """
        entry = JournalEntryInput(
            description=description,
            reference=invoice_id,
            source_type="invoice",
            source_id=invoice_id,
            tenant_id=tenant_id,
            lines=[
                LedgerLine(
                    account_number="1200",  # Accounts Receivable
                    amount=amount,
                    is_debit=True,
                    tenant_id=tenant_id,
                ),
                LedgerLine(
                    account_number="4010",  # SaaS Revenue
                    amount=amount,
                    is_debit=False,
                    tenant_id=tenant_id,
                ),
            ],
        )
        return await self.create_journal_entry(entry, auto_post=True)

    async def book_payment_received(
        self,
        tenant_id: str,
        amount: Decimal,
        payment_method: str,
        payment_id: Optional[str] = None,
    ) -> HQJournalEntry:
        """
        Book payment received from customer.

        Debit: Cash/Bank (1000)
        Credit: Accounts Receivable (1200)
        """
        entry = JournalEntryInput(
            description=f"Payment received via {payment_method}",
            reference=payment_id,
            source_type="payment",
            source_id=payment_id,
            tenant_id=tenant_id,
            lines=[
                LedgerLine(
                    account_number="1000",  # Cash
                    amount=amount,
                    is_debit=True,
                ),
                LedgerLine(
                    account_number="1200",  # Accounts Receivable
                    amount=amount,
                    is_debit=False,
                    tenant_id=tenant_id,
                ),
            ],
        )
        return await self.create_journal_entry(entry, auto_post=True)

    async def book_ai_cogs(
        self,
        tenant_id: str,
        amount: Decimal,
        model: str,
        tokens_used: int,
        usage_log_id: Optional[str] = None,
    ) -> HQJournalEntry:
        """
        Book AI compute costs (COGS) attributed to a tenant.

        Debit: AI Compute Costs (5010)
        Credit: Accounts Payable - AI Providers (2100)
        """
        entry = JournalEntryInput(
            description=f"AI compute: {model} ({tokens_used:,} tokens)",
            source_type="ai_usage",
            source_id=usage_log_id,
            tenant_id=tenant_id,
            lines=[
                LedgerLine(
                    account_number="5010",  # AI Compute Costs
                    amount=amount,
                    is_debit=True,
                    memo=f"Model: {model}",
                    tenant_id=tenant_id,
                ),
                LedgerLine(
                    account_number="2100",  # Accounts Payable
                    amount=amount,
                    is_debit=False,
                    memo="AI Provider",
                ),
            ],
        )
        return await self.create_journal_entry(entry, auto_post=True)

    async def book_payroll_expense(
        self,
        amount: Decimal,
        payroll_run_id: str,
        description: str,
    ) -> HQJournalEntry:
        """
        Book payroll expense from Check.

        Debit: Payroll Expense (6100)
        Credit: Cash (1000)
        """
        entry = JournalEntryInput(
            description=description,
            reference=payroll_run_id,
            source_type="payroll",
            source_id=payroll_run_id,
            lines=[
                LedgerLine(
                    account_number="6100",  # Payroll Expense
                    amount=amount,
                    is_debit=True,
                ),
                LedgerLine(
                    account_number="1000",  # Cash
                    amount=amount,
                    is_debit=False,
                ),
            ],
        )
        return await self.create_journal_entry(entry, auto_post=True)

    async def book_vendor_bill(
        self,
        vendor_id: str,
        amount: Decimal,
        expense_account: str,
        description: str,
        bill_id: Optional[str] = None,
    ) -> HQJournalEntry:
        """
        Book a vendor bill.

        Debit: Expense Account (varies)
        Credit: Accounts Payable (2000)
        """
        entry = JournalEntryInput(
            description=description,
            reference=bill_id,
            source_type="bill",
            source_id=bill_id,
            lines=[
                LedgerLine(
                    account_number=expense_account,
                    amount=amount,
                    is_debit=True,
                ),
                LedgerLine(
                    account_number="2000",  # Accounts Payable
                    amount=amount,
                    is_debit=False,
                    memo=f"Vendor: {vendor_id}",
                ),
            ],
        )
        return await self.create_journal_entry(entry, auto_post=True)

    async def book_bill_payment(
        self,
        vendor_id: str,
        amount: Decimal,
        payment_method: str,
        bill_id: Optional[str] = None,
    ) -> HQJournalEntry:
        """
        Book payment to vendor.

        Debit: Accounts Payable (2000)
        Credit: Cash (1000)
        """
        entry = JournalEntryInput(
            description=f"Bill payment via {payment_method}",
            reference=bill_id,
            source_type="bill_payment",
            source_id=bill_id,
            lines=[
                LedgerLine(
                    account_number="2000",  # Accounts Payable
                    amount=amount,
                    is_debit=True,
                    memo=f"Vendor: {vendor_id}",
                ),
                LedgerLine(
                    account_number="1000",  # Cash
                    amount=amount,
                    is_debit=False,
                ),
            ],
        )
        return await self.create_journal_entry(entry, auto_post=True)

    # ========================================================================
    # Financial Reports
    # ========================================================================

    async def get_profit_loss_report(
        self,
        start_date: date,
        end_date: date,
        tenant_id: Optional[str] = None,
        include_tenant_breakdown: bool = False,
    ) -> ProfitLossReport:
        """
        Generate a Profit & Loss report for the specified period.

        This is the SQL query Atlas uses to generate the Monthly P&L Report.
        """
        # Revenue accounts (4000-4999)
        revenue_query = """
            SELECT
                coa.account_number,
                coa.account_name,
                COALESCE(SUM(
                    CASE WHEN gle.credit_account_id IS NOT NULL THEN gle.amount
                         WHEN gle.debit_account_id IS NOT NULL THEN -gle.amount
                         ELSE 0 END
                ), 0) as balance
            FROM hq_chart_of_accounts coa
            LEFT JOIN hq_general_ledger_entry gle ON (
                gle.credit_account_id = coa.id OR gle.debit_account_id = coa.id
            )
            LEFT JOIN hq_journal_entry je ON gle.journal_entry_id = je.id
            WHERE coa.account_type = 'revenue'
              AND je.status = 'posted'
              AND je.transaction_date >= :start_date
              AND je.transaction_date <= :end_date
              {tenant_filter}
            GROUP BY coa.id, coa.account_number, coa.account_name
            ORDER BY coa.account_number
        """

        # COGS accounts (5000-5999)
        cogs_query = """
            SELECT
                coa.account_number,
                coa.account_name,
                COALESCE(SUM(
                    CASE WHEN gle.debit_account_id IS NOT NULL THEN gle.amount
                         WHEN gle.credit_account_id IS NOT NULL THEN -gle.amount
                         ELSE 0 END
                ), 0) as balance
            FROM hq_chart_of_accounts coa
            LEFT JOIN hq_general_ledger_entry gle ON (
                gle.credit_account_id = coa.id OR gle.debit_account_id = coa.id
            )
            LEFT JOIN hq_journal_entry je ON gle.journal_entry_id = je.id
            WHERE coa.account_type = 'cost_of_revenue'
              AND je.status = 'posted'
              AND je.transaction_date >= :start_date
              AND je.transaction_date <= :end_date
              {tenant_filter}
            GROUP BY coa.id, coa.account_number, coa.account_name
            ORDER BY coa.account_number
        """

        # Expense accounts (6000-6999)
        expense_query = """
            SELECT
                coa.account_number,
                coa.account_name,
                COALESCE(SUM(
                    CASE WHEN gle.debit_account_id IS NOT NULL THEN gle.amount
                         WHEN gle.credit_account_id IS NOT NULL THEN -gle.amount
                         ELSE 0 END
                ), 0) as balance
            FROM hq_chart_of_accounts coa
            LEFT JOIN hq_general_ledger_entry gle ON (
                gle.credit_account_id = coa.id OR gle.debit_account_id = coa.id
            )
            LEFT JOIN hq_journal_entry je ON gle.journal_entry_id = je.id
            WHERE coa.account_type = 'expense'
              AND je.status = 'posted'
              AND je.transaction_date >= :start_date
              AND je.transaction_date <= :end_date
              {tenant_filter}
            GROUP BY coa.id, coa.account_number, coa.account_name
            ORDER BY coa.account_number
        """

        tenant_filter = ""
        params = {"start_date": start_date, "end_date": end_date}
        if tenant_id:
            tenant_filter = "AND (je.tenant_id = :tenant_id OR gle.tenant_id = :tenant_id)"
            params["tenant_id"] = tenant_id

        # Execute queries
        revenue_result = await self.db.execute(
            text(revenue_query.format(tenant_filter=tenant_filter)), params
        )
        cogs_result = await self.db.execute(
            text(cogs_query.format(tenant_filter=tenant_filter)), params
        )
        expense_result = await self.db.execute(
            text(expense_query.format(tenant_filter=tenant_filter)), params
        )

        # Process results
        revenue = {}
        total_revenue = Decimal("0")
        for row in revenue_result:
            revenue[f"{row.account_number} - {row.account_name}"] = Decimal(str(row.balance))
            total_revenue += Decimal(str(row.balance))

        cost_of_revenue = {}
        total_cogs = Decimal("0")
        for row in cogs_result:
            cost_of_revenue[f"{row.account_number} - {row.account_name}"] = Decimal(str(row.balance))
            total_cogs += Decimal(str(row.balance))

        expenses = {}
        total_expenses = Decimal("0")
        for row in expense_result:
            expenses[f"{row.account_number} - {row.account_name}"] = Decimal(str(row.balance))
            total_expenses += Decimal(str(row.balance))

        gross_profit = total_revenue - total_cogs
        net_income = gross_profit - total_expenses

        # Get tenant breakdown if requested
        tenant_breakdown = None
        if include_tenant_breakdown and not tenant_id:
            tenant_breakdown = await self._get_tenant_pl_breakdown(start_date, end_date)

        return ProfitLossReport(
            period_start=start_date,
            period_end=end_date,
            revenue=revenue,
            cost_of_revenue=cost_of_revenue,
            expenses=expenses,
            total_revenue=total_revenue,
            total_cogs=total_cogs,
            gross_profit=gross_profit,
            total_expenses=total_expenses,
            net_income=net_income,
            tenant_breakdown=tenant_breakdown,
        )

    async def get_balance_sheet(self, as_of_date: date) -> BalanceSheetReport:
        """Generate a Balance Sheet as of a specific date."""
        # Assets query
        assets_query = """
            SELECT
                coa.account_number,
                coa.account_name,
                coa.current_balance as balance
            FROM hq_chart_of_accounts coa
            WHERE coa.account_type = 'asset'
              AND coa.is_active = true
            ORDER BY coa.account_number
        """

        # Liabilities query
        liabilities_query = """
            SELECT
                coa.account_number,
                coa.account_name,
                coa.current_balance as balance
            FROM hq_chart_of_accounts coa
            WHERE coa.account_type = 'liability'
              AND coa.is_active = true
            ORDER BY coa.account_number
        """

        # Equity query
        equity_query = """
            SELECT
                coa.account_number,
                coa.account_name,
                coa.current_balance as balance
            FROM hq_chart_of_accounts coa
            WHERE coa.account_type = 'equity'
              AND coa.is_active = true
            ORDER BY coa.account_number
        """

        assets_result = await self.db.execute(text(assets_query))
        liabilities_result = await self.db.execute(text(liabilities_query))
        equity_result = await self.db.execute(text(equity_query))

        assets = {}
        total_assets = Decimal("0")
        for row in assets_result:
            balance = Decimal(str(row.balance)) if row.balance else Decimal("0")
            assets[f"{row.account_number} - {row.account_name}"] = balance
            total_assets += balance

        liabilities = {}
        total_liabilities = Decimal("0")
        for row in liabilities_result:
            balance = Decimal(str(row.balance)) if row.balance else Decimal("0")
            liabilities[f"{row.account_number} - {row.account_name}"] = balance
            total_liabilities += balance

        equity = {}
        total_equity = Decimal("0")
        for row in equity_result:
            balance = Decimal(str(row.balance)) if row.balance else Decimal("0")
            equity[f"{row.account_number} - {row.account_name}"] = balance
            total_equity += balance

        return BalanceSheetReport(
            as_of_date=as_of_date,
            assets=assets,
            liabilities=liabilities,
            equity=equity,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            total_equity=total_equity,
        )

    async def get_tenant_profit_margin(
        self,
        tenant_id: str,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Calculate per-tenant profit margin.

        This is the key metric for understanding unit economics:
        - Tenant Revenue
        - Attributed AI COGS
        - Gross Margin per Tenant
        """
        query = """
            SELECT
                je.tenant_id,
                t.name as tenant_name,
                COALESCE(SUM(
                    CASE WHEN coa.account_type = 'revenue'
                         AND gle.credit_account_id IS NOT NULL
                         THEN gle.amount ELSE 0 END
                ), 0) as revenue,
                COALESCE(SUM(
                    CASE WHEN coa.account_type = 'cost_of_revenue'
                         AND gle.debit_account_id IS NOT NULL
                         THEN gle.amount ELSE 0 END
                ), 0) as cogs
            FROM hq_journal_entry je
            JOIN hq_general_ledger_entry gle ON gle.journal_entry_id = je.id
            JOIN hq_chart_of_accounts coa ON (
                coa.id = gle.debit_account_id OR coa.id = gle.credit_account_id
            )
            LEFT JOIN hq_tenant t ON je.tenant_id = t.id
            WHERE je.status = 'posted'
              AND je.transaction_date >= :start_date
              AND je.transaction_date <= :end_date
              AND (je.tenant_id = :tenant_id OR gle.tenant_id = :tenant_id)
            GROUP BY je.tenant_id, t.name
        """

        result = await self.db.execute(
            text(query),
            {"tenant_id": tenant_id, "start_date": start_date, "end_date": end_date}
        )
        row = result.fetchone()

        if not row:
            return {
                "tenant_id": tenant_id,
                "revenue": Decimal("0"),
                "cogs": Decimal("0"),
                "gross_profit": Decimal("0"),
                "gross_margin_percent": Decimal("0"),
            }

        revenue = Decimal(str(row.revenue)) if row.revenue else Decimal("0")
        cogs = Decimal(str(row.cogs)) if row.cogs else Decimal("0")
        gross_profit = revenue - cogs
        margin_percent = (gross_profit / revenue * 100) if revenue > 0 else Decimal("0")

        return {
            "tenant_id": tenant_id,
            "tenant_name": row.tenant_name,
            "revenue": revenue,
            "cogs": cogs,
            "gross_profit": gross_profit,
            "gross_margin_percent": margin_percent.quantize(Decimal("0.01")),
        }

    # ========================================================================
    # Chart of Accounts Operations
    # ========================================================================

    async def create_account(
        self,
        account_number: str,
        account_name: str,
        account_type: AccountType,
        account_subtype: Optional[AccountSubtype] = None,
        description: Optional[str] = None,
        parent_account_id: Optional[str] = None,
        is_system: bool = False,
    ) -> HQChartOfAccounts:
        """Create a new account in the Chart of Accounts."""
        account = HQChartOfAccounts(
            id=str(uuid.uuid4()),
            account_number=account_number,
            account_name=account_name,
            account_type=account_type,
            account_subtype=account_subtype,
            description=description,
            parent_account_id=parent_account_id,
            is_system=is_system,
            current_balance=Decimal("0"),
        )
        self.db.add(account)
        await self.db.flush()
        return account

    async def get_chart_of_accounts(
        self,
        account_type: Optional[AccountType] = None,
        include_inactive: bool = False,
    ) -> List[HQChartOfAccounts]:
        """Get all accounts, optionally filtered by type."""
        query = select(HQChartOfAccounts)

        if account_type:
            query = query.where(HQChartOfAccounts.account_type == account_type)

        if not include_inactive:
            query = query.where(HQChartOfAccounts.is_active == True)

        query = query.order_by(HQChartOfAccounts.account_number)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_account_balance(
        self,
        account_id: str,
        as_of_date: Optional[date] = None,
    ) -> AccountBalance:
        """Get the balance for a specific account."""
        result = await self.db.execute(
            select(HQChartOfAccounts).where(HQChartOfAccounts.id == account_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            raise ValueError(f"Account not found: {account_id}")

        # Calculate running balance from posted entries
        date_filter = ""
        params = {"account_id": account_id}
        if as_of_date:
            date_filter = "AND je.transaction_date <= :as_of_date"
            params["as_of_date"] = as_of_date

        query = f"""
            SELECT
                COALESCE(SUM(CASE WHEN gle.debit_account_id = :account_id THEN gle.amount ELSE 0 END), 0) as debits,
                COALESCE(SUM(CASE WHEN gle.credit_account_id = :account_id THEN gle.amount ELSE 0 END), 0) as credits
            FROM hq_general_ledger_entry gle
            JOIN hq_journal_entry je ON gle.journal_entry_id = je.id
            WHERE (gle.debit_account_id = :account_id OR gle.credit_account_id = :account_id)
              AND je.status = 'posted'
              {date_filter}
        """

        balance_result = await self.db.execute(text(query), params)
        row = balance_result.fetchone()

        debit_total = Decimal(str(row.debits)) if row.debits else Decimal("0")
        credit_total = Decimal(str(row.credits)) if row.credits else Decimal("0")

        # Calculate balance based on account type
        # Assets and Expenses have normal debit balances
        # Liabilities, Equity, and Revenue have normal credit balances
        if account.account_type in [AccountType.ASSET, AccountType.EXPENSE, AccountType.COST_OF_REVENUE]:
            balance = debit_total - credit_total
        else:
            balance = credit_total - debit_total

        return AccountBalance(
            account_id=account.id,
            account_number=account.account_number,
            account_name=account.account_name,
            account_type=account.account_type,
            debit_total=debit_total,
            credit_total=credit_total,
            balance=balance,
        )

    # ========================================================================
    # Usage Metering (AI COGS Tracking)
    # ========================================================================

    async def log_ai_usage(
        self,
        tenant_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_per_1k_input: Decimal,
        cost_per_1k_output: Decimal,
    ) -> Tuple[HQUsageLog, Optional[HQJournalEntry]]:
        """
        Log AI usage and optionally book the COGS.

        Returns the usage log and the journal entry if auto-booking is enabled.
        """
        total_tokens = input_tokens + output_tokens
        input_cost = (Decimal(input_tokens) / 1000) * cost_per_1k_input
        output_cost = (Decimal(output_tokens) / 1000) * cost_per_1k_output
        total_cost = input_cost + output_cost

        usage_log = HQUsageLog(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            metric_type=UsageMetricType.AI_TOKENS_USED,
            metric_value=Decimal(total_tokens),
            unit_cost=cost_per_1k_input,  # Simplified
            total_cost=total_cost,
            ai_metadata={
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "input_cost": float(input_cost),
                "output_cost": float(output_cost),
            },
        )
        self.db.add(usage_log)
        await self.db.flush()

        # Auto-book if cost is significant (> $0.01)
        journal_entry = None
        if total_cost >= Decimal("0.01"):
            journal_entry = await self.book_ai_cogs(
                tenant_id=tenant_id,
                amount=total_cost.quantize(Decimal("0.01")),
                model=model,
                tokens_used=total_tokens,
                usage_log_id=usage_log.id,
            )

        return usage_log, journal_entry

    async def get_ai_costs_by_tenant(
        self,
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        """Get AI costs aggregated by tenant for a period."""
        query = """
            SELECT
                ul.tenant_id,
                t.name as tenant_name,
                COUNT(*) as request_count,
                SUM(ul.metric_value) as total_tokens,
                SUM(ul.total_cost) as total_cost
            FROM hq_usage_log ul
            LEFT JOIN hq_tenant t ON ul.tenant_id = t.id
            WHERE ul.metric_type = 'ai_tokens_used'
              AND ul.recorded_at >= :start_date
              AND ul.recorded_at <= :end_date
            GROUP BY ul.tenant_id, t.name
            ORDER BY total_cost DESC
        """

        result = await self.db.execute(
            text(query),
            {"start_date": start_date, "end_date": end_date}
        )

        return [
            {
                "tenant_id": row.tenant_id,
                "tenant_name": row.tenant_name,
                "request_count": row.request_count,
                "total_tokens": int(row.total_tokens) if row.total_tokens else 0,
                "total_cost": Decimal(str(row.total_cost)) if row.total_cost else Decimal("0"),
            }
            for row in result
        ]

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    def _calculate_totals(self, lines: List[LedgerLine]) -> Tuple[Decimal, Decimal]:
        """Calculate total debits and credits from lines."""
        total_debits = sum(
            line.amount for line in lines if line.is_debit
        )
        total_credits = sum(
            line.amount for line in lines if not line.is_debit
        )
        return Decimal(total_debits), Decimal(total_credits)

    async def _generate_entry_number(self) -> str:
        """Generate a unique journal entry number."""
        year = datetime.utcnow().year
        result = await self.db.execute(
            select(func.count(HQJournalEntry.id)).where(
                HQJournalEntry.entry_number.like(f"JE-{year}-%")
            )
        )
        count = result.scalar() or 0
        return f"JE-{year}-{(count + 1):05d}"

    async def _get_account_by_number(self, account_number: str) -> Optional[HQChartOfAccounts]:
        """Get account by account number with caching."""
        if account_number in self._account_cache:
            return self._account_cache[account_number]

        result = await self.db.execute(
            select(HQChartOfAccounts).where(
                HQChartOfAccounts.account_number == account_number
            )
        )
        account = result.scalar_one_or_none()

        if account:
            self._account_cache[account_number] = account

        return account

    async def _update_account_balances(self, journal_entry_id: str) -> None:
        """Update account balances when posting a journal entry."""
        result = await self.db.execute(
            select(HQGeneralLedgerEntry).where(
                HQGeneralLedgerEntry.journal_entry_id == journal_entry_id
            )
        )
        entries = result.scalars().all()

        for entry in entries:
            if entry.debit_account_id:
                await self._adjust_account_balance(
                    entry.debit_account_id,
                    entry.amount,
                    is_debit=True
                )
            if entry.credit_account_id:
                await self._adjust_account_balance(
                    entry.credit_account_id,
                    entry.amount,
                    is_debit=False
                )

    async def _adjust_account_balance(
        self,
        account_id: str,
        amount: Decimal,
        is_debit: bool,
    ) -> None:
        """Adjust an account's balance based on debit/credit rules."""
        result = await self.db.execute(
            select(HQChartOfAccounts).where(HQChartOfAccounts.id == account_id)
        )
        account = result.scalar_one_or_none()
        if not account:
            return

        # Assets and Expenses increase with debits
        # Liabilities, Equity, and Revenue increase with credits
        if account.account_type in [AccountType.ASSET, AccountType.EXPENSE, AccountType.COST_OF_REVENUE]:
            if is_debit:
                account.current_balance += amount
            else:
                account.current_balance -= amount
        else:  # LIABILITY, EQUITY, REVENUE
            if is_debit:
                account.current_balance -= amount
            else:
                account.current_balance += amount

    async def _create_reversing_entry(
        self,
        original: HQJournalEntry,
        created_by_id: Optional[str],
        reason: Optional[str],
    ) -> HQJournalEntry:
        """Create a reversing entry for a voided journal entry."""
        result = await self.db.execute(
            select(HQGeneralLedgerEntry).where(
                HQGeneralLedgerEntry.journal_entry_id == original.id
            )
        )
        original_entries = result.scalars().all()

        # Swap debits and credits
        lines = []
        for entry in original_entries:
            if entry.debit_account_id:
                account = await self._get_account_by_id(entry.debit_account_id)
                lines.append(LedgerLine(
                    account_number=account.account_number if account else "",
                    amount=entry.amount,
                    is_debit=False,  # Reverse: was debit, now credit
                    memo=f"Reversal: {entry.memo}" if entry.memo else "Reversal",
                    tenant_id=entry.tenant_id,
                ))
            if entry.credit_account_id:
                account = await self._get_account_by_id(entry.credit_account_id)
                lines.append(LedgerLine(
                    account_number=account.account_number if account else "",
                    amount=entry.amount,
                    is_debit=True,  # Reverse: was credit, now debit
                    memo=f"Reversal: {entry.memo}" if entry.memo else "Reversal",
                    tenant_id=entry.tenant_id,
                ))

        reversal_entry = JournalEntryInput(
            description=f"VOID: {original.description}" + (f" - {reason}" if reason else ""),
            reference=f"VOID-{original.entry_number}",
            source_type="void",
            source_id=original.id,
            tenant_id=original.tenant_id,
            lines=lines,
        )

        return await self.create_journal_entry(reversal_entry, created_by_id, auto_post=True)

    async def _get_account_by_id(self, account_id: str) -> Optional[HQChartOfAccounts]:
        """Get account by ID."""
        result = await self.db.execute(
            select(HQChartOfAccounts).where(HQChartOfAccounts.id == account_id)
        )
        return result.scalar_one_or_none()

    async def _get_tenant_pl_breakdown(
        self,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Dict[str, Decimal]]:
        """Get P&L breakdown by tenant."""
        query = """
            SELECT
                COALESCE(je.tenant_id, gle.tenant_id) as tenant_id,
                t.name as tenant_name,
                SUM(CASE
                    WHEN coa.account_type = 'revenue' AND gle.credit_account_id IS NOT NULL
                    THEN gle.amount ELSE 0 END
                ) as revenue,
                SUM(CASE
                    WHEN coa.account_type = 'cost_of_revenue' AND gle.debit_account_id IS NOT NULL
                    THEN gle.amount ELSE 0 END
                ) as cogs
            FROM hq_journal_entry je
            JOIN hq_general_ledger_entry gle ON gle.journal_entry_id = je.id
            JOIN hq_chart_of_accounts coa ON (
                coa.id = gle.debit_account_id OR coa.id = gle.credit_account_id
            )
            LEFT JOIN hq_tenant t ON COALESCE(je.tenant_id, gle.tenant_id) = t.id
            WHERE je.status = 'posted'
              AND je.transaction_date >= :start_date
              AND je.transaction_date <= :end_date
              AND COALESCE(je.tenant_id, gle.tenant_id) IS NOT NULL
            GROUP BY COALESCE(je.tenant_id, gle.tenant_id), t.name
        """

        result = await self.db.execute(
            text(query),
            {"start_date": start_date, "end_date": end_date}
        )

        breakdown = {}
        for row in result:
            tenant_key = row.tenant_name or row.tenant_id
            revenue = Decimal(str(row.revenue)) if row.revenue else Decimal("0")
            cogs = Decimal(str(row.cogs)) if row.cogs else Decimal("0")
            breakdown[tenant_key] = {
                "revenue": revenue,
                "cogs": cogs,
                "gross_profit": revenue - cogs,
                "gross_margin": ((revenue - cogs) / revenue * 100).quantize(Decimal("0.01")) if revenue > 0 else Decimal("0"),
            }

        return breakdown


# ============================================================================
# Singleton Instance
# ============================================================================

async def get_gl_manager(db: AsyncSession) -> GeneralLedgerManager:
    """Get a GeneralLedgerManager instance."""
    return GeneralLedgerManager(db)
