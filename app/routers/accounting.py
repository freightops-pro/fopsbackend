from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.accounting import (
    AccountingBasicReport,
    CustomerCreate,
    CustomerResponse,
    CustomerSummary,
    CustomerUpdate,
    CustomersSummaryResponse,
    InvoiceCreate,
    InvoiceResponse,
    LedgerSummaryResponse,
    SettlementCreate,
    SettlementResponse,
    VendorCreate,
    VendorResponse,
    VendorUpdate,
    VendorsSummaryResponse,
)
from app.services.accounting import (
    AccountingReportService,
    CustomerService,
    InvoiceService,
    LedgerService,
    SettlementService,
    VendorService,
)

router = APIRouter()


async def _accounting_services(db: AsyncSession = Depends(get_db)) -> tuple[LedgerService, InvoiceService, SettlementService, AccountingReportService, CustomerService]:
    return LedgerService(db), InvoiceService(db), SettlementService(db), AccountingReportService(db), CustomerService(db)


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.company_id


@router.get("/ledger", response_model=LedgerSummaryResponse)
async def get_ledger_summary(
    company_id: str = Depends(_company_id),
    services: tuple[LedgerService, InvoiceService, SettlementService, AccountingReportService, CustomerService] = Depends(_accounting_services),
) -> LedgerSummaryResponse:
    ledger_service, _, _, _, _ = services
    return await ledger_service.summary(company_id)


@router.get("/invoices", response_model=List[InvoiceResponse])
async def list_invoices(
    company_id: str = Depends(_company_id),
    services: tuple[LedgerService, InvoiceService, SettlementService, AccountingReportService, CustomerService] = Depends(_accounting_services),
) -> List[InvoiceResponse]:
    _, invoice_service, _, _, _ = services
    invoices = await invoice_service.list_invoices(company_id)
    return [InvoiceResponse.model_validate(invoice) for invoice in invoices]


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: str,
    company_id: str = Depends(_company_id),
    services: tuple[LedgerService, InvoiceService, SettlementService, AccountingReportService, CustomerService] = Depends(_accounting_services),
) -> InvoiceResponse:
    _, invoice_service, _, _, _ = services
    try:
        invoice = await invoice_service.get_invoice(company_id, invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return InvoiceResponse.model_validate(invoice)


@router.post("/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: InvoiceCreate,
    company_id: str = Depends(_company_id),
    services: tuple[LedgerService, InvoiceService, SettlementService, AccountingReportService, CustomerService] = Depends(_accounting_services),
) -> InvoiceResponse:
    _, invoice_service, _, _, _ = services
    invoice = await invoice_service.create_invoice(company_id, payload)
    return InvoiceResponse.model_validate(invoice)


@router.get("/settlements", response_model=List[SettlementResponse])
async def list_settlements(
    company_id: str = Depends(_company_id),
    services: tuple[LedgerService, InvoiceService, SettlementService, AccountingReportService, CustomerService] = Depends(_accounting_services),
) -> List[SettlementResponse]:
    _, _, settlement_service, _, _ = services
    settlements = await settlement_service.list_settlements(company_id)
    return [SettlementResponse.model_validate(settlement) for settlement in settlements]


@router.post("/settlements", response_model=SettlementResponse, status_code=status.HTTP_201_CREATED)
async def create_settlement(
    payload: SettlementCreate,
    company_id: str = Depends(_company_id),
    services: tuple[LedgerService, InvoiceService, SettlementService, AccountingReportService, CustomerService] = Depends(_accounting_services),
) -> SettlementResponse:
    _, _, settlement_service, _, _ = services
    settlement = await settlement_service.create_settlement(company_id, payload)
    return SettlementResponse.model_validate(settlement)


@router.get("/reports/basic")
async def get_basic_report(
    period: str = "month",
    company_id: str = Depends(_company_id),
    services: tuple[LedgerService, InvoiceService, SettlementService, AccountingReportService, CustomerService] = Depends(_accounting_services),
) -> dict:
    """Get basic accounting report for the specified period."""
    _, _, _, report_service, _ = services
    from app.schemas.accounting import AccountingBasicReport
    report_data = await report_service.basic_report(company_id, period)
    return report_data


# Customer endpoints
@router.get("/customers/summary", response_model=CustomersSummaryResponse)
async def get_customers_summary(
    company_id: str = Depends(_company_id),
    services: tuple[LedgerService, InvoiceService, SettlementService, AccountingReportService, CustomerService] = Depends(_accounting_services),
) -> CustomersSummaryResponse:
    """Get summary of all customers with metrics."""
    _, _, _, _, customer_service = services
    return await customer_service.get_customers_summary(company_id)


@router.get("/customers", response_model=List[CustomerResponse])
async def list_customers(
    status: str | None = None,
    company_id: str = Depends(_company_id),
    services: tuple[LedgerService, InvoiceService, SettlementService, AccountingReportService, CustomerService] = Depends(_accounting_services),
) -> List[CustomerResponse]:
    """List all customers for the company, optionally filtered by status."""
    _, _, _, _, customer_service = services
    customers = await customer_service.list_customers(company_id, status)
    return [CustomerResponse.model_validate(customer) for customer in customers]


@router.get("/customers/{customer_id}/summary", response_model=CustomerSummary)
async def get_customer_summary(
    customer_id: str,
    company_id: str = Depends(_company_id),
    services: tuple[LedgerService, InvoiceService, SettlementService, AccountingReportService, CustomerService] = Depends(_accounting_services),
) -> CustomerSummary:
    """Get customer summary with outstanding amounts."""
    _, _, _, _, customer_service = services
    try:
        return await customer_service.get_customer_summary(company_id, customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    company_id: str = Depends(_company_id),
    services: tuple[LedgerService, InvoiceService, SettlementService, AccountingReportService, CustomerService] = Depends(_accounting_services),
) -> CustomerResponse:
    """Get a single customer by ID."""
    _, _, _, _, customer_service = services
    try:
        customer = await customer_service.get_customer(company_id, customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return CustomerResponse.model_validate(customer)


@router.post("/customers", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerCreate,
    company_id: str = Depends(_company_id),
    services: tuple[LedgerService, InvoiceService, SettlementService, AccountingReportService, CustomerService] = Depends(_accounting_services),
) -> CustomerResponse:
    """Create a new customer."""
    _, _, _, _, customer_service = services
    customer = await customer_service.create_customer(company_id, payload)
    return CustomerResponse.model_validate(customer)


@router.patch("/customers/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    company_id: str = Depends(_company_id),
    services: tuple[LedgerService, InvoiceService, SettlementService, AccountingReportService, CustomerService] = Depends(_accounting_services),
) -> CustomerResponse:
    """Update an existing customer."""
    _, _, _, _, customer_service = services
    try:
        customer = await customer_service.update_customer(company_id, customer_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return CustomerResponse.model_validate(customer)


@router.delete("/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: str,
    company_id: str = Depends(_company_id),
    services: tuple[LedgerService, InvoiceService, SettlementService, AccountingReportService, CustomerService] = Depends(_accounting_services),
) -> None:
    """Soft delete a customer by setting is_active to False."""
    _, _, _, _, customer_service = services
    try:
        await customer_service.delete_customer(company_id, customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# Vendor endpoints
async def _vendor_service(db: AsyncSession = Depends(get_db)) -> VendorService:
    return VendorService(db)


@router.get("/vendors/summary", response_model=VendorsSummaryResponse)
async def get_vendors_summary(
    company_id: str = Depends(_company_id),
    vendor_service: VendorService = Depends(_vendor_service),
) -> VendorsSummaryResponse:
    """Get summary of all vendors with metrics."""
    return await vendor_service.get_vendors_summary(company_id)


@router.get("/vendors", response_model=List[VendorResponse])
async def list_vendors(
    status: str | None = None,
    category: str | None = None,
    company_id: str = Depends(_company_id),
    vendor_service: VendorService = Depends(_vendor_service),
) -> List[VendorResponse]:
    """List all vendors for the company, optionally filtered by status or category."""
    vendors = await vendor_service.list_vendors(company_id, status, category)
    return [VendorResponse.model_validate(vendor) for vendor in vendors]


@router.get("/vendors/{vendor_id}", response_model=VendorResponse)
async def get_vendor(
    vendor_id: str,
    company_id: str = Depends(_company_id),
    vendor_service: VendorService = Depends(_vendor_service),
) -> VendorResponse:
    """Get a single vendor by ID."""
    try:
        vendor = await vendor_service.get_vendor(company_id, vendor_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return VendorResponse.model_validate(vendor)


@router.post("/vendors", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
async def create_vendor(
    payload: VendorCreate,
    company_id: str = Depends(_company_id),
    vendor_service: VendorService = Depends(_vendor_service),
) -> VendorResponse:
    """Create a new vendor."""
    vendor = await vendor_service.create_vendor(company_id, payload)
    return VendorResponse.model_validate(vendor)


@router.patch("/vendors/{vendor_id}", response_model=VendorResponse)
async def update_vendor(
    vendor_id: str,
    payload: VendorUpdate,
    company_id: str = Depends(_company_id),
    vendor_service: VendorService = Depends(_vendor_service),
) -> VendorResponse:
    """Update an existing vendor."""
    try:
        vendor = await vendor_service.update_vendor(company_id, vendor_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return VendorResponse.model_validate(vendor)


@router.delete("/vendors/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor(
    vendor_id: str,
    company_id: str = Depends(_company_id),
    vendor_service: VendorService = Depends(_vendor_service),
) -> None:
    """Soft delete a vendor by setting is_active to False."""
    try:
        await vendor_service.delete_vendor(company_id, vendor_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
