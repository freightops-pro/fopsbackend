from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import uuid
from typing import List, Optional

from app.models.bill import Bill
from app.models.vendor import Vendor
from app.schema.billSchema import BillCreate, BillUpdate, VendorBillCreate


def _ensure_bill_schema(db: Session) -> None:
    try:
        dialect = db.bind.dialect.name if db.bind else ""
        if dialect == "postgresql":
            db.execute(text("ALTER TABLE bills ADD COLUMN IF NOT EXISTS notes TEXT"))
            db.commit()
        elif dialect == "sqlite":
            try:
                db.execute(text("ALTER TABLE bills ADD COLUMN notes TEXT"))
            except Exception:
                db.rollback()
            db.commit()
    except Exception:
        db.rollback()


def list_bills(db: Session, company_id: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[Bill]:
    _ensure_bill_schema(db)
    q = db.query(Bill)
    if company_id:
        q = q.filter(Bill.company_id == company_id)
    return q.order_by(Bill.created_at.desc()).offset(skip).limit(limit).all()


def get_bill(db: Session, bill_id: str) -> Optional[Bill]:
    return db.query(Bill).filter(Bill.id == bill_id).first()


def create_bill(db: Session, payload: BillCreate) -> Bill:
    _ensure_bill_schema(db)
    new_id = str(uuid.uuid4())
    bill = Bill(
        id=new_id,
        company_id=payload.companyId,
        vendor_id=payload.vendorId,
        vendor_name=payload.vendorName,
        amount=payload.amount,
        bill_date=payload.billDate,
        due_date=payload.dueDate,
        category=payload.category,
        status=payload.status or "pending",
        notes=payload.notes,
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return bill


def update_bill(db: Session, bill_id: str, payload: BillUpdate) -> Bill:
    _ensure_bill_schema(db)
    bill = get_bill(db, bill_id)
    if not bill:
        raise ValueError("Bill not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        if hasattr(bill, k):
            setattr(bill, k, v)
    bill.updated_at = datetime.utcnow()
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return bill


def delete_bill(db: Session, bill_id: str) -> bool:
    _ensure_bill_schema(db)
    bill = get_bill(db, bill_id)
    if not bill:
        return False
    db.delete(bill)
    db.commit()
    return True


def create_vendor_and_bill(db: Session, payload: VendorBillCreate) -> Bill:
    """Create a vendor and associated bill in a single transaction"""
    _ensure_bill_schema(db)
    
    # Create vendor first
    vendor_id = str(uuid.uuid4())
    vendor = Vendor(
        id=vendor_id,
        company_id=payload.companyId,
        # Personal Details
        title=payload.title,
        first_name=payload.firstName,
        middle_name=payload.middleName,
        last_name=payload.lastName,
        suffix=payload.suffix,
        # Company Details
        company=payload.company,
        display_name=payload.displayName,
        print_on_check=payload.printOnCheck,
        # Address Information
        address=payload.address,
        city=payload.city,
        state=payload.state,
        zip_code=payload.zipCode,
        country=payload.country,
        # Contact Information
        email=payload.email,
        phone=payload.phone,
        mobile=payload.mobile,
        fax=payload.fax,
        other=payload.other,
        website=payload.website,
        # Financial Information
        billing_rate=payload.billingRate,
        terms=payload.terms,
        opening_balance=payload.openingBalance,
        balance_as_of=payload.balanceAsOf,
        account_number=payload.accountNumber,
        # 1099 Tracking
        tax_id=payload.taxId,
        track_payments_for_1099=payload.trackPaymentsFor1099,
    )
    db.add(vendor)
    
    # Create bill linked to the vendor
    bill_id = str(uuid.uuid4())
    bill = Bill(
        id=bill_id,
        company_id=payload.companyId,
        vendor_id=vendor_id,
        vendor_name=payload.displayName,  # Use display name as vendor name
        amount=payload.amount,
        bill_date=payload.billDate,
        due_date=payload.dueDate,
        category=payload.category,
        status=payload.status or "pending",
        notes=payload.notes,
    )
    db.add(bill)
    
    # Commit both vendor and bill
    db.commit()
    db.refresh(bill)
    return bill


