from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import List, Optional
from sqlalchemy.orm import Session
from app.config.db import get_db
from app.schema.vendorSchema import VendorCreate, VendorOut, VendorUpdate
from app.services.vendor_service import (
    list_vendors,
    get_vendor,
    create_vendor,
    update_vendor,
    delete_vendor,
)

router = APIRouter(prefix="/api/vendors", tags=["Vendors"])


@router.get("", response_model=List[VendorOut])
def get_vendors(
    companyId: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return list_vendors(db, company_id=companyId, skip=skip, limit=limit)


@router.post("", response_model=VendorOut, status_code=201)
def add_vendor(payload: VendorCreate, db: Session = Depends(get_db)):
    return create_vendor(db, payload)


@router.get("/{vendor_id}", response_model=VendorOut)
def get_vendor_detail(vendor_id: str = Path(...), db: Session = Depends(get_db)):
    vendor = get_vendor(db, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor


@router.patch("/{vendor_id}", response_model=VendorOut)
@router.put("/{vendor_id}", response_model=VendorOut)
def update_vendor_route(vendor_id: str, payload: VendorUpdate, db: Session = Depends(get_db)):
    try:
        vendor = update_vendor(db, vendor_id, payload)
        return vendor
    except ValueError:
        raise HTTPException(status_code=404, detail="Vendor not found")


@router.delete("/{vendor_id}", status_code=204)
def delete_vendor_route(vendor_id: str, db: Session = Depends(get_db)):
    ok = delete_vendor(db, vendor_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return None 