from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import uuid
from typing import List, Optional
from decimal import Decimal

from app.models.invoice import Invoice
from app.schema.invoiceSchema import InvoiceCreate, InvoiceUpdate


def _ensure_invoice_schema(db: Session) -> None:
    try:
        dialect = db.bind.dialect.name if db.bind else ""
        if dialect == "postgresql":
            # Add any missing columns for PostgreSQL
            db.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS notes TEXT"))
            db.commit()
        elif dialect == "sqlite":
            try:
                db.execute(text("ALTER TABLE invoices ADD COLUMN notes TEXT"))
            except Exception:
                db.rollback()
            db.commit()
    except Exception:
        db.rollback()


def list_invoices(db: Session, company_id: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[Invoice]:
    _ensure_invoice_schema(db)
    q = db.query(Invoice)
    if company_id:
        q = q.filter(Invoice.companyId == company_id)
    return q.order_by(Invoice.createdAt.desc()).offset(skip).limit(limit).all()


def get_invoice(db: Session, invoice_id: str) -> Optional[Invoice]:
    return db.query(Invoice).filter(Invoice.id == invoice_id).first()


def create_invoice(db: Session, payload: InvoiceCreate) -> Invoice:
    _ensure_invoice_schema(db)
    new_id = str(uuid.uuid4())
    
    # Convert line items to dict format for JSON storage
    line_items_dict = [item.model_dump() for item in payload.lineItems]
    
    invoice = Invoice(
        id=new_id,
        companyId=payload.companyId,
        # Header Information
        invoiceNumber=payload.invoiceNumber,
        invoiceDate=payload.invoiceDate,
        consigneePO=payload.consigneePO,
        shipperBL=payload.shipperBL,
        shippingSCAC=payload.shippingSCAC,
        paymentMethod=payload.paymentMethod,
        deliveryDate=payload.deliveryDate,
        actualPickupDate=payload.actualPickupDate,
        transportationMethod=payload.transportationMethod,
        currencyCode=payload.currencyCode,
        # Bill To Information
        billToName=payload.billToName,
        billToAddress=payload.billToAddress,
        billToCodeType=payload.billToCodeType,
        billToCode=payload.billToCode,
        # Shipper Information
        shipperName=payload.shipperName,
        shipperAddress=payload.shipperAddress,
        shipperCodeType=payload.shipperCodeType,
        shipperCode=payload.shipperCode,
        # Consignee Information
        consigneeName=payload.consigneeName,
        consigneeAddress=payload.consigneeAddress,
        consigneeCodeType=payload.consigneeCodeType,
        consigneeCode=payload.consigneeCode,
        # Line Items
        lineItems=line_items_dict,
        # Additional Load Details
        routingSequenceCode=payload.routingSequenceCode,
        cityOfExchange=payload.cityOfExchange,
        equipmentInitial=payload.equipmentInitial,
        equipmentNumber=payload.equipmentNumber,
        ladingQty=payload.ladingQty,
        ladingQtyUOM=payload.ladingQtyUOM,
        totalWeight=payload.totalWeight,
        totalWeightUOM=payload.totalWeightUOM,
        # Status and metadata
        status=payload.status,
        totalAmount=payload.totalAmount,
        notes=payload.notes,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def update_invoice(db: Session, invoice_id: str, payload: InvoiceUpdate) -> Invoice:
    _ensure_invoice_schema(db)
    invoice = get_invoice(db, invoice_id)
    if not invoice:
        raise ValueError("Invoice not found")
    
    data = payload.model_dump(exclude_unset=True)
    
    # Handle line items conversion if provided
    if 'lineItems' in data and data['lineItems'] is not None:
        data['lineItems'] = [item.model_dump() for item in data['lineItems']]
    
    for k, v in data.items():
        if hasattr(invoice, k):
            setattr(invoice, k, v)
    
    invoice.updatedAt = datetime.utcnow()
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def delete_invoice(db: Session, invoice_id: str) -> bool:
    _ensure_invoice_schema(db)
    invoice = get_invoice(db, invoice_id)
    if not invoice:
        return False
    db.delete(invoice)
    db.commit()
    return True


def calculate_total_amount(line_items: List[dict]) -> Decimal:
    """Calculate total amount from line items"""
    total = Decimal('0.00')
    for item in line_items:
        try:
            charge = Decimal(str(item.get('charge', '0')))
            total += charge
        except (ValueError, TypeError):
            continue
    return total
