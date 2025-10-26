from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import uuid
from typing import List, Optional, Dict, Any

from app.models.customer import Customer
from app.schema.customerSchema import CustomerCreate, CustomerUpdate


def _ensure_customer_schema(db: Session) -> None:
    """Self-heal: ensure new columns exist without full migrations."""
    try:
        dialect = db.bind.dialect.name if db.bind else ""
        if dialect == "postgresql":
            # Add missing columns defensively
            db.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS \"creditLimit\" NUMERIC"))
            db.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS \"paymentTerms\" INTEGER"))
            db.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS status VARCHAR"))
            db.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS \"totalRevenue\" NUMERIC DEFAULT 0"))
            db.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS \"lastOrder\" DATE"))
            db.execute(text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS details JSON"))
            db.commit()
        elif dialect == "sqlite":
            # SQLite: type is flexible; add as TEXT if not exists
            try:
                for stmt in [
                    "ALTER TABLE customers ADD COLUMN \"creditLimit\" NUMERIC",
                    "ALTER TABLE customers ADD COLUMN \"paymentTerms\" INTEGER",
                    "ALTER TABLE customers ADD COLUMN status TEXT",
                    "ALTER TABLE customers ADD COLUMN \"totalRevenue\" NUMERIC DEFAULT 0",
                    "ALTER TABLE customers ADD COLUMN \"lastOrder\" TEXT",
                    "ALTER TABLE customers ADD COLUMN details TEXT",
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


def list_customers(db: Session, company_id: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[Customer]:
    _ensure_customer_schema(db)
    q = db.query(Customer)
    if company_id:
        q = q.filter(Customer.companyId == company_id)
    return q.order_by(Customer.createdAt.desc()).offset(skip).limit(limit).all()


def get_customer(db: Session, customer_id: str) -> Optional[Customer]:
    return db.query(Customer).filter(Customer.id == customer_id).first()


core_fields = {
    # Columns physically present on Customer model
    "name", "contactPerson", "email", "phone",
    "address", "city", "state", "zipCode",
    "creditLimit", "paymentTerms", "status", "totalRevenue", "lastOrder",
}


def create_customer(db: Session, payload: CustomerCreate) -> Customer:
    _ensure_customer_schema(db)
    new_id = str(uuid.uuid4())
    # Split between core columns and extra details
    payload_dict = payload.model_dump(exclude_none=True)
    core_data = {k: v for k, v in payload_dict.items() if k in core_fields}
    extra = {k: v for k, v in payload_dict.items() if k not in core_fields and k != "companyId"}
    cust = Customer(
        id=new_id,
        companyId=payload.companyId,
        **core_data,
        details=extra or None,
    )
    db.add(cust)
    db.commit()
    db.refresh(cust)
    return cust


def update_customer(db: Session, customer_id: str, payload: CustomerUpdate) -> Customer:
    _ensure_customer_schema(db)
    cust = get_customer(db, customer_id)
    if not cust:
        raise ValueError("Customer not found")
    data = payload.model_dump(exclude_unset=True)
    # Apply updates: known columns directly, others into details JSON
    details = dict(cust.details or {})
    for k, v in data.items():
        if k in core_fields and hasattr(cust, k):
            setattr(cust, k, v)
        else:
            details[k] = v
    cust.details = details or None
    cust.updatedAt = datetime.utcnow()
    db.add(cust)
    db.commit()
    db.refresh(cust)
    return cust


def delete_customer(db: Session, customer_id: str) -> bool:
    _ensure_customer_schema(db)
    cust = get_customer(db, customer_id)
    if not cust:
        return False
    db.delete(cust)
    db.commit()
    return True
