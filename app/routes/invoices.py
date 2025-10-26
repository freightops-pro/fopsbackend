from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import List, Optional
from sqlalchemy.orm import Session
from app.config.db import get_db
from app.schema.invoiceSchema import InvoiceCreate, InvoiceOut, InvoiceUpdate
from app.services.invoice_service import (
    list_invoices,
    get_invoice,
    create_invoice,
    update_invoice,
    delete_invoice,
)

router = APIRouter(prefix="/api/invoices", tags=["Invoices"])


@router.get("", response_model=List[InvoiceOut])
def get_invoices(
    companyId: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return list_invoices(db, company_id=companyId, skip=skip, limit=limit)


@router.post("", response_model=InvoiceOut, status_code=201)
def add_invoice(payload: InvoiceCreate, db: Session = Depends(get_db)):
    return create_invoice(db, payload)


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice_detail(invoice_id: str = Path(...), db: Session = Depends(get_db)):
    invoice = get_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.patch("/{invoice_id}", response_model=InvoiceOut)
@router.put("/{invoice_id}", response_model=InvoiceOut)
def update_invoice_route(invoice_id: str, payload: InvoiceUpdate, db: Session = Depends(get_db)):
    try:
        invoice = update_invoice(db, invoice_id, payload)
        return invoice
    except ValueError:
        raise HTTPException(status_code=404, detail="Invoice not found")


@router.delete("/{invoice_id}", status_code=204)
def delete_invoice_route(invoice_id: str, db: Session = Depends(get_db)):
    ok = delete_invoice(db, invoice_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return None
