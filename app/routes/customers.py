from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import List, Optional
from sqlalchemy.orm import Session
from app.config.db import get_db
from app.schema.customerSchema import CustomerCreate, CustomerOut, CustomerUpdate
from app.services.customer_service import (
    list_customers,
    get_customer,
    create_customer,
    update_customer,
    delete_customer,
)

router = APIRouter(prefix="/api/customers", tags=["Customers"])


@router.get("", response_model=List[CustomerOut])
def get_customers(
    companyId: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return list_customers(db, company_id=companyId, skip=skip, limit=limit)


@router.post("", response_model=CustomerOut, status_code=201)
def add_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    return create_customer(db, payload)


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer_detail(customer_id: str = Path(...), db: Session = Depends(get_db)):
    cust = get_customer(db, customer_id)
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    return cust


@router.patch("/{customer_id}", response_model=CustomerOut)
@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer_route(customer_id: str, payload: CustomerUpdate, db: Session = Depends(get_db)):
    try:
        cust = update_customer(db, customer_id, payload)
        return cust
    except ValueError:
        raise HTTPException(status_code=404, detail="Customer not found")


@router.delete("/{customer_id}", status_code=204)
def delete_customer_route(customer_id: str, db: Session = Depends(get_db)):
    ok = delete_customer(db, customer_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Customer not found")
    return None
