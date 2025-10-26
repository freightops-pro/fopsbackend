from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import List, Optional
from sqlalchemy.orm import Session
from app.config.db import get_db
from app.schema.billSchema import BillCreate, BillOut, BillUpdate, VendorBillCreate
from app.services.bill_service import (
    list_bills,
    get_bill,
    create_bill,
    update_bill,
    delete_bill,
    create_vendor_and_bill,
)

router = APIRouter(prefix="/api/bills", tags=["Bills"])


@router.get("", response_model=List[BillOut])
def get_bills(
    companyId: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return list_bills(db, company_id=companyId, skip=skip, limit=limit)


@router.post("", response_model=BillOut, status_code=201)
def add_bill(payload: BillCreate, db: Session = Depends(get_db)):
    return create_bill(db, payload)


@router.post("/vendor-bill", response_model=BillOut, status_code=201)
def add_vendor_and_bill(payload: VendorBillCreate, db: Session = Depends(get_db)):
    return create_vendor_and_bill(db, payload)


@router.get("/{bill_id}", response_model=BillOut)
def get_bill_detail(bill_id: str = Path(...), db: Session = Depends(get_db)):
    b = get_bill(db, bill_id)
    if not b:
        raise HTTPException(status_code=404, detail="Bill not found")
    return b


@router.patch("/{bill_id}", response_model=BillOut)
@router.put("/{bill_id}", response_model=BillOut)
def update_bill_route(bill_id: str, payload: BillUpdate, db: Session = Depends(get_db)):
    try:
        b = update_bill(db, bill_id, payload)
        return b
    except ValueError:
        raise HTTPException(status_code=404, detail="Bill not found")


@router.delete("/{bill_id}", status_code=204)
def delete_bill_route(bill_id: str, db: Session = Depends(get_db)):
    ok = delete_bill(db, bill_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Bill not found")
    return None


