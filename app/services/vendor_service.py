from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import uuid
from typing import List, Optional, Dict, Any

from app.models.vendor import Vendor
from app.schema.vendorSchema import VendorCreate, VendorUpdate


def _ensure_vendor_schema(db: Session) -> None:
    """Self-heal: ensure new columns exist without full migrations."""
    try:
        dialect = db.bind.dialect.name if db.bind else ""
        if dialect == "postgresql":
            # Add missing columns defensively
            db.execute(text("ALTER TABLE vendors ADD COLUMN IF NOT EXISTS category VARCHAR"))
            db.execute(text("ALTER TABLE vendors ADD COLUMN IF NOT EXISTS \"paymentTerms\" INTEGER"))
            db.execute(text("ALTER TABLE vendors ADD COLUMN IF NOT EXISTS status VARCHAR"))
            db.execute(text("ALTER TABLE vendors ADD COLUMN IF NOT EXISTS \"totalSpend\" NUMERIC DEFAULT 0"))
            db.execute(text("ALTER TABLE vendors ADD COLUMN IF NOT EXISTS \"lastPayment\" DATE"))
            db.execute(text("ALTER TABLE vendors ADD COLUMN IF NOT EXISTS details JSON"))
            db.commit()
        elif dialect == "sqlite":
            # SQLite: type is flexible; add as TEXT if not exists
            try:
                for stmt in [
                    "ALTER TABLE vendors ADD COLUMN category TEXT",
                    "ALTER TABLE vendors ADD COLUMN \"paymentTerms\" INTEGER",
                    "ALTER TABLE vendors ADD COLUMN status TEXT",
                    "ALTER TABLE vendors ADD COLUMN \"totalSpend\" NUMERIC DEFAULT 0",
                    "ALTER TABLE vendors ADD COLUMN \"lastPayment\" TEXT",
                    "ALTER TABLE vendors ADD COLUMN details TEXT",
                ]:
                    try:
                        db.execute(text(stmt))
                    except Exception:
                        db.rollback()
                db.commit()
            except Exception:
                db.rollback()
    except Exception:
        # Don't block requests if introspection fails
        db.rollback()


def list_vendors(db: Session, company_id: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[Vendor]:
    _ensure_vendor_schema(db)
    q = db.query(Vendor)
    if company_id:
        q = q.filter(Vendor.companyId == company_id)
    return q.order_by(Vendor.createdAt.desc()).offset(skip).limit(limit).all()


def get_vendor(db: Session, vendor_id: str) -> Optional[Vendor]:
    return db.query(Vendor).filter(Vendor.id == vendor_id).first()


core_fields = {
    # Columns physically present on Vendor model
    "name", "contactPerson", "email", "phone",
    "address", "city", "state", "zipCode",
    "category", "paymentTerms", "status", "totalSpend", "lastPayment",
}


def create_vendor(db: Session, payload: VendorCreate) -> Vendor:
    _ensure_vendor_schema(db)
    new_id = str(uuid.uuid4())
    # Split between core columns and extra details
    payload_dict = payload.model_dump(exclude_none=True)
    core_data = {k: v for k, v in payload_dict.items() if k in core_fields}
    extra = {k: v for k, v in payload_dict.items() if k not in core_fields and k != "companyId"}
    vendor = Vendor(
        id=new_id,
        companyId=payload.companyId,
        **core_data,
        details=extra or None,
    )
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


def update_vendor(db: Session, vendor_id: str, payload: VendorUpdate) -> Vendor:
    _ensure_vendor_schema(db)
    vendor = get_vendor(db, vendor_id)
    if not vendor:
        raise ValueError("Vendor not found")
    data = payload.model_dump(exclude_unset=True)
    # Apply updates: known columns directly, others into details JSON
    details = dict(vendor.details or {})
    for k, v in data.items():
        if k in core_fields and hasattr(vendor, k):
            setattr(vendor, k, v)
        else:
            details[k] = v
    vendor.details = details or None
    vendor.updatedAt = datetime.utcnow()
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


def delete_vendor(db: Session, vendor_id: str) -> bool:
    _ensure_vendor_schema(db)
    vendor = get_vendor(db, vendor_id)
    if not vendor:
        return False
    db.delete(vendor)
    db.commit()
    return True 