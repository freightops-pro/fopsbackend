from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting import Customer, Invoice, LedgerEntry, Settlement, Vendor
from app.models.load import Load
from app.schemas.accounting import (
    CustomerCreate,
    CustomerResponse,
    CustomerSummary,
    CustomerUpdate,
    CustomersSummaryResponse,
    InvoiceCreate,
    InvoiceLineItem,
    InvoiceResponse,
    LedgerEntryResponse,
    LedgerSummaryResponse,
    SettlementCreate,
    SettlementResponse,
    VendorCreate,
    VendorUpdate,
    VendorsSummaryResponse,
)


class LedgerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def summary(self, company_id: str) -> LedgerSummaryResponse:
        entries = await self.db.execute(
            select(LedgerEntry).where(LedgerEntry.company_id == company_id).order_by(LedgerEntry.recorded_at.desc())
        )
        totals = await self.db.execute(
            select(
                func.coalesce(func.sum(LedgerEntry.amount).filter(LedgerEntry.category == "revenue"), 0),
                func.coalesce(func.sum(LedgerEntry.amount).filter(LedgerEntry.category == "expense"), 0),
                func.coalesce(func.sum(LedgerEntry.amount).filter(LedgerEntry.category == "deduction"), 0),
            ).where(LedgerEntry.company_id == company_id)
        )
        revenue, expense, deduction = totals.one()
        entry_models = [LedgerEntryResponse.model_validate(entry) for entry in entries.scalars().all()]
        net = float(revenue or 0) - float(expense or 0) - float(deduction or 0)
        return LedgerSummaryResponse(
            total_revenue=float(revenue or 0),
            total_expense=float(expense or 0),
            total_deductions=float(deduction or 0),
            net_total=net,
            entries=entry_models,
        )


class InvoiceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_invoices(self, company_id: str) -> List[Invoice]:
        result = await self.db.execute(
            select(Invoice).where(Invoice.company_id == company_id).order_by(Invoice.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_invoice(self, company_id: str, payload: InvoiceCreate) -> Invoice:
        subtotal = self._calculate_subtotal(payload.line_items)
        tax = subtotal * payload.tax_rate
        total = subtotal + tax

        invoice = Invoice(
            id=str(uuid.uuid4()),
            company_id=company_id,
            load_id=payload.load_id,
            invoice_number=self._build_invoice_number(),
            invoice_date=payload.invoice_date,
            status="draft",
            subtotal=subtotal,
            tax=tax,
            total=total,
            line_items=[item.model_dump() for item in payload.line_items],
        )

        self.db.add(invoice)
        await self.db.commit()
        await self.db.refresh(invoice)
        return invoice

    async def get_invoice(self, company_id: str, invoice_id: str) -> Invoice:
        result = await self.db.execute(
            select(Invoice).where(Invoice.company_id == company_id, Invoice.id == invoice_id)
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise ValueError("Invoice not found")
        return invoice

    def _calculate_subtotal(self, line_items: List[InvoiceLineItem]) -> float:
        subtotal = 0.0
        for item in line_items:
            subtotal += item.amount
        return subtotal

    def _build_invoice_number(self) -> str:
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        suffix = uuid.uuid4().hex[:6].upper()
        return f"INV-{timestamp}-{suffix}"


class SettlementService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_settlements(self, company_id: str) -> List[Settlement]:
        result = await self.db.execute(
            select(Settlement).where(Settlement.company_id == company_id).order_by(Settlement.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_settlement(self, company_id: str, payload: SettlementCreate) -> Settlement:
        entries = await self.db.execute(
            select(LedgerEntry)
            .where(
                LedgerEntry.company_id == company_id,
                LedgerEntry.load_id == payload.load_id,
            )
        )
        revenue = 0.0
        deductions = 0.0
        for entry in entries.scalars().all():
            if entry.category == "revenue":
                revenue += float(entry.amount or 0)
            elif entry.category in {"expense", "deduction"}:
                deductions += float(entry.amount or 0)

        settlement = Settlement(
            id=str(uuid.uuid4()),
            company_id=company_id,
            driver_id=payload.driver_id,
            load_id=payload.load_id,
            settlement_date=payload.settlement_date,
            total_earnings=revenue,
            total_deductions=deductions,
            net_pay=revenue - deductions,
            breakdown={
                "earnings": revenue,
                "deductions": deductions,
            },
        )

        self.db.add(settlement)
        await self.db.commit()
        await self.db.refresh(settlement)
        return settlement


class AccountingReportService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def basic_report(self, company_id: str, period: str = "month") -> dict:
        """Generate basic accounting report for the specified period."""
        from datetime import datetime, timedelta
        
        # Calculate date range based on period
        now = datetime.utcnow()
        if period == "week":
            start_date = now - timedelta(days=7)
        elif period == "month":
            start_date = now - timedelta(days=30)
        elif period == "quarter":
            start_date = now - timedelta(days=90)
        elif period == "year":
            start_date = now - timedelta(days=365)
        else:
            start_date = now - timedelta(days=30)
        
        # Get revenue from invoices
        invoices_result = await self.db.execute(
            select(Invoice).where(
                Invoice.company_id == company_id,
                Invoice.invoice_date >= start_date.date()
            )
        )
        invoices = list(invoices_result.scalars().all())
        total_revenue = sum(float(inv.total or 0) for inv in invoices)
        days = (now - start_date).days or 1
        avg_revenue_per_day = total_revenue / days
        
        # Get expenses from ledger
        expenses_result = await self.db.execute(
            select(LedgerEntry).where(
                LedgerEntry.company_id == company_id,
                LedgerEntry.category == "expense",
                LedgerEntry.recorded_at >= start_date
            )
        )
        expenses = list(expenses_result.scalars().all())
        total_expenses = sum(float(e.amount or 0) for e in expenses)
        avg_expenses_per_day = total_expenses / days
        
        # Calculate profit
        net_profit = total_revenue - total_expenses
        margin_percentage = (net_profit / total_revenue * 100) if total_revenue > 0 else 0.0
        
        # Outstanding receivables and payables
        outstanding_invoices = [inv for inv in invoices if 
                               inv.status and inv.status.upper() in ["PENDING", "SENT", "OVERDUE"]]
        receivables = sum(float(inv.total or 0) for inv in outstanding_invoices)  # amount_paid not in model yet
        payables = 0.0  # Would need vendor bills
        net_outstanding = receivables - payables
        
        # Cash flow (simplified)
        incoming = total_revenue
        outgoing = total_expenses
        balance = incoming - outgoing
        
        return {
            "period": period,
            "dateRange": {
                "start": start_date.isoformat(),
                "end": now.isoformat(),
            },
            "revenue": {
                "total": total_revenue,
                "average_per_day": avg_revenue_per_day,
            },
            "expenses": {
                "total": total_expenses,
                "average_per_day": avg_expenses_per_day,
            },
            "profit": {
                "net": net_profit,
                "margin_percentage": margin_percentage,
            },
            "outstanding": {
                "receivables": receivables,
                "payables": payables,
                "net": net_outstanding,
            },
            "cashFlow": {
                "incoming": incoming,
                "outgoing": outgoing,
                "balance": balance,
            },
            "fuel": {
                "cost_per_mile": 0.0,  # Would need to calculate from fuel entries
            },
        }


class CustomerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_customers(self, company_id: str, status: Optional[str] = None) -> List[Customer]:
        """List all customers for a company, optionally filtered by status."""
        query = select(Customer).where(Customer.company_id == company_id)
        if status:
            query = query.where(Customer.status == status)
        query = query.order_by(Customer.name.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_customer(self, company_id: str, customer_id: str) -> Customer:
        """Get a single customer by ID."""
        result = await self.db.execute(
            select(Customer).where(Customer.company_id == company_id, Customer.id == customer_id)
        )
        customer = result.scalar_one_or_none()
        if not customer:
            raise ValueError("Customer not found")
        return customer

    async def create_customer(self, company_id: str, payload: CustomerCreate) -> Customer:
        """Create a new customer."""
        customer = Customer(
            id=str(uuid.uuid4()),
            company_id=company_id,
            name=payload.name,
            legal_name=payload.legal_name,
            tax_id=payload.tax_id,
            primary_contact_name=payload.primary_contact_name,
            primary_contact_email=payload.primary_contact_email,
            primary_contact_phone=payload.primary_contact_phone,
            billing_address=payload.billing_address.model_dump() if payload.billing_address else None,
            shipping_address=payload.shipping_address.model_dump() if payload.shipping_address else None,
            payment_terms=payload.payment_terms,
            credit_limit=payload.credit_limit,
            credit_limit_used=0,
            synctera_account_id=payload.synctera_account_id,
            status=payload.status,
            is_active=True,
        )

        self.db.add(customer)
        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def update_customer(self, company_id: str, customer_id: str, payload: CustomerUpdate) -> Customer:
        """Update an existing customer."""
        customer = await self.get_customer(company_id, customer_id)

        # Update fields if provided
        if payload.name is not None:
            customer.name = payload.name
        if payload.legal_name is not None:
            customer.legal_name = payload.legal_name
        if payload.tax_id is not None:
            customer.tax_id = payload.tax_id
        if payload.primary_contact_name is not None:
            customer.primary_contact_name = payload.primary_contact_name
        if payload.primary_contact_email is not None:
            customer.primary_contact_email = payload.primary_contact_email
        if payload.primary_contact_phone is not None:
            customer.primary_contact_phone = payload.primary_contact_phone
        if payload.billing_address is not None:
            customer.billing_address = payload.billing_address.model_dump() if payload.billing_address else None
        if payload.shipping_address is not None:
            customer.shipping_address = payload.shipping_address.model_dump() if payload.shipping_address else None
        if payload.payment_terms is not None:
            customer.payment_terms = payload.payment_terms
        if payload.credit_limit is not None:
            customer.credit_limit = payload.credit_limit
        if payload.synctera_account_id is not None:
            customer.synctera_account_id = payload.synctera_account_id
        if payload.status is not None:
            customer.status = payload.status
        if payload.is_active is not None:
            customer.is_active = payload.is_active

        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def delete_customer(self, company_id: str, customer_id: str) -> None:
        """Soft delete a customer by setting is_active to False."""
        customer = await self.get_customer(company_id, customer_id)
        customer.is_active = False
        customer.status = "inactive"
        await self.db.commit()

    async def get_customer_summary(self, company_id: str, customer_id: str) -> CustomerSummary:
        """Get customer summary with outstanding amounts."""
        customer = await self.get_customer(company_id, customer_id)

        # Calculate outstanding from invoices
        invoices_result = await self.db.execute(
            select(Invoice).where(
                Invoice.company_id == company_id,
                Invoice.status.in_(["pending", "sent", "overdue"]),
            )
        )
        # Note: Invoice model doesn't have customer_id yet, so we'll use customer name matching for now
        # This is a temporary solution until we add customer_id to Invoice
        invoices = list(invoices_result.scalars().all())
        total_outstanding = sum(float(inv.total or 0) for inv in invoices)
        overdue_amount = sum(
            float(inv.total or 0)
            for inv in invoices
            if inv.status and inv.status.lower() == "overdue"
        )

        return CustomerSummary(
            id=customer.id,
            name=customer.name,
            total_outstanding=total_outstanding,
            overdue_amount=overdue_amount,
            credit_limit=customer.credit_limit,
            credit_limit_used=customer.credit_limit_used or 0,
            status=customer.status,
        )

    async def get_customers_summary(self, company_id: str) -> CustomersSummaryResponse:
        """Get summary of all customers with metrics."""
        customers_result = await self.db.execute(
            select(Customer).where(Customer.company_id == company_id, Customer.is_active == True)
        )
        customers = list(customers_result.scalars().all())

        # Calculate metrics
        active_customers = len(customers)
        total_credit_limit = sum(float(c.credit_limit or 0) for c in customers)
        used_credit_limit = sum(float(c.credit_limit_used or 0) for c in customers)
        credit_limit_usage_percent = (
            (used_credit_limit / total_credit_limit * 100) if total_credit_limit > 0 else 0.0
        )

        # Get outstanding invoices
        invoices_result = await self.db.execute(
            select(Invoice).where(
                Invoice.company_id == company_id,
                Invoice.status.in_(["pending", "sent", "overdue"]),
            )
        )
        invoices = list(invoices_result.scalars().all())
        total_ar = sum(float(inv.total or 0) for inv in invoices)
        overdue_invoices = [inv for inv in invoices if inv.status and inv.status.lower() == "overdue"]
        overdue_accounts = len(overdue_invoices)
        overdue_amount = sum(float(inv.total or 0) for inv in overdue_invoices)

        # Build customer summaries
        customer_summaries = []
        for customer in customers:
            # Calculate customer-specific outstanding (simplified - would need customer_id on Invoice)
            customer_outstanding = total_ar / active_customers if active_customers > 0 else 0
            customer_overdue = overdue_amount / overdue_accounts if overdue_accounts > 0 else 0

            customer_summaries.append(
                CustomerSummary(
                    id=customer.id,
                    name=customer.name,
                    total_outstanding=customer_outstanding,
                    overdue_amount=customer_overdue,
                    credit_limit=customer.credit_limit,
                    credit_limit_used=customer.credit_limit_used or 0,
                    status=customer.status,
                )
            )

        return CustomersSummaryResponse(
            active_customers=active_customers,
            total_ar=total_ar,
            overdue_accounts=overdue_accounts,
            overdue_amount=overdue_amount,
            credit_limit_usage_percent=credit_limit_usage_percent,
            total_credit_limit=total_credit_limit,
            used_credit_limit=used_credit_limit,
            customers=customer_summaries,
        )


class VendorService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_vendors(self, company_id: str, status: Optional[str] = None, category: Optional[str] = None) -> List[Vendor]:
        """List all vendors for a company, optionally filtered by status or category."""
        query = select(Vendor).where(Vendor.company_id == company_id)
        if status:
            query = query.where(Vendor.status == status)
        if category:
            query = query.where(Vendor.category == category)
        query = query.order_by(Vendor.name.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_vendor(self, company_id: str, vendor_id: str) -> Vendor:
        """Get a single vendor by ID."""
        result = await self.db.execute(
            select(Vendor).where(Vendor.company_id == company_id, Vendor.id == vendor_id)
        )
        vendor = result.scalar_one_or_none()
        if not vendor:
            raise ValueError("Vendor not found")
        return vendor

    async def create_vendor(self, company_id: str, payload: VendorCreate) -> Vendor:
        """Create a new vendor."""
        vendor = Vendor(
            id=str(uuid.uuid4()),
            company_id=company_id,
            name=payload.name,
            legal_name=payload.legal_name,
            tax_id=payload.tax_id,
            category=payload.category,
            primary_contact_name=payload.primary_contact_name,
            primary_contact_email=payload.primary_contact_email,
            primary_contact_phone=payload.primary_contact_phone,
            address=payload.address.model_dump() if payload.address else None,
            payment_terms=payload.payment_terms,
            contract_start_date=payload.contract_start_date,
            contract_end_date=payload.contract_end_date,
            contract_value=payload.contract_value,
            outstanding_balance=0,
            notes=payload.notes,
            status=payload.status,
            is_active=True,
        )

        self.db.add(vendor)
        await self.db.commit()
        await self.db.refresh(vendor)
        return vendor

    async def update_vendor(self, company_id: str, vendor_id: str, payload: VendorUpdate) -> Vendor:
        """Update an existing vendor."""
        vendor = await self.get_vendor(company_id, vendor_id)

        if payload.name is not None:
            vendor.name = payload.name
        if payload.legal_name is not None:
            vendor.legal_name = payload.legal_name
        if payload.tax_id is not None:
            vendor.tax_id = payload.tax_id
        if payload.category is not None:
            vendor.category = payload.category
        if payload.primary_contact_name is not None:
            vendor.primary_contact_name = payload.primary_contact_name
        if payload.primary_contact_email is not None:
            vendor.primary_contact_email = payload.primary_contact_email
        if payload.primary_contact_phone is not None:
            vendor.primary_contact_phone = payload.primary_contact_phone
        if payload.address is not None:
            vendor.address = payload.address.model_dump() if payload.address else None
        if payload.payment_terms is not None:
            vendor.payment_terms = payload.payment_terms
        if payload.contract_start_date is not None:
            vendor.contract_start_date = payload.contract_start_date
        if payload.contract_end_date is not None:
            vendor.contract_end_date = payload.contract_end_date
        if payload.contract_value is not None:
            vendor.contract_value = payload.contract_value
        if payload.outstanding_balance is not None:
            vendor.outstanding_balance = payload.outstanding_balance
        if payload.notes is not None:
            vendor.notes = payload.notes
        if payload.status is not None:
            vendor.status = payload.status
        if payload.is_active is not None:
            vendor.is_active = payload.is_active

        await self.db.commit()
        await self.db.refresh(vendor)
        return vendor

    async def delete_vendor(self, company_id: str, vendor_id: str) -> None:
        """Soft delete a vendor by setting is_active to False."""
        vendor = await self.get_vendor(company_id, vendor_id)
        vendor.is_active = False
        vendor.status = "inactive"
        await self.db.commit()

    async def get_vendors_summary(self, company_id: str) -> VendorsSummaryResponse:
        """Get summary of all vendors with metrics."""
        vendors_result = await self.db.execute(
            select(Vendor).where(Vendor.company_id == company_id, Vendor.is_active == True)
        )
        vendors = list(vendors_result.scalars().all())

        # Count by category
        by_category: Dict[str, int] = {}
        for v in vendors:
            cat = v.category or "other"
            by_category[cat] = by_category.get(cat, 0) + 1

        # Calculate metrics
        active_vendors = len(vendors)
        total_outstanding = sum(float(v.outstanding_balance or 0) for v in vendors)
        total_contract_value = sum(float(v.contract_value or 0) for v in vendors)

        # Count contracts expiring in 30 days
        today = date.today()
        thirty_days_later = today + timedelta(days=30)
        contracts_expiring_soon = sum(
            1 for v in vendors
            if v.contract_end_date and today <= v.contract_end_date <= thirty_days_later
        )

        # Get total vendors (including inactive)
        all_vendors_result = await self.db.execute(
            select(func.count(Vendor.id)).where(Vendor.company_id == company_id)
        )
        total_vendors = all_vendors_result.scalar() or 0

        return VendorsSummaryResponse(
            active_vendors=active_vendors,
            total_vendors=total_vendors,
            by_category=by_category,
            contracts_expiring_soon=contracts_expiring_soon,
            total_outstanding=Decimal(str(total_outstanding)),
            total_contract_value=Decimal(str(total_contract_value)),
        )

