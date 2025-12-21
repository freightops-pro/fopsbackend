"""DQF (Driver Qualification File) API routes."""

from typing import List, Optional
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.api import deps
from app.core.db import get_db_sync
from app.schemas.onboarding import (
    DQFDocumentCreate,
    DQFDocumentUpdate,
    DQFDocumentResponse,
    DQFSummaryResponse,
)
from app.models.onboarding import DQFDocument, VerificationStatus
from app.models.driver import Driver

router = APIRouter()


def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    """Extract company ID from current user."""
    return current_user.company_id


def _user_id(current_user=Depends(deps.get_current_user)) -> str:
    """Extract user ID from current user."""
    return current_user.id


@router.post("/documents", response_model=DQFDocumentResponse, status_code=status.HTTP_201_CREATED)
def create_dqf_document(
    payload: DQFDocumentCreate,
    company_id: str = Depends(_company_id),
    user_id: str = Depends(_user_id),
    db: Session = Depends(get_db_sync),
) -> DQFDocumentResponse:
    """
    Add a document to a driver's DQF.

    Creates a DQF document record. File should already be uploaded to storage
    (use /api/upload endpoint first) and provide the file_url here.
    """
    import uuid

    # Verify driver belongs to company
    driver = db.query(Driver).filter(
        Driver.id == payload.driver_id,
        Driver.company_id == company_id
    ).first()

    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Driver not found: {payload.driver_id}"
        )

    # Check if document is expired
    is_expired = False
    if payload.expiration_date:
        is_expired = payload.expiration_date < date.today()

    # Create DQF document
    document = DQFDocument(
        id=str(uuid.uuid4()),
        driver_id=payload.driver_id,
        company_id=company_id,
        document_category=payload.document_category,  # type: ignore
        document_type=payload.document_type,
        document_name=payload.document_name,
        file_url=payload.file_url,
        file_size=payload.file_size,
        file_type=payload.file_type,
        issue_date=payload.issue_date,
        expiration_date=payload.expiration_date,
        is_expired=is_expired,
        verification_status=VerificationStatus.PENDING,
        uploaded_by=user_id,
        uploaded_at=datetime.utcnow()
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return DQFDocumentResponse.model_validate(document)


@router.get("/documents/{document_id}", response_model=DQFDocumentResponse)
def get_dqf_document(
    document_id: str,
    company_id: str = Depends(_company_id),
    db: Session = Depends(get_db_sync),
) -> DQFDocumentResponse:
    """Get a specific DQF document by ID."""
    document = db.query(DQFDocument).filter(
        DQFDocument.id == document_id,
        DQFDocument.company_id == company_id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DQF document not found: {document_id}"
        )

    return DQFDocumentResponse.model_validate(document)


@router.patch("/documents/{document_id}", response_model=DQFDocumentResponse)
def update_dqf_document(
    document_id: str,
    payload: DQFDocumentUpdate,
    company_id: str = Depends(_company_id),
    user_id: str = Depends(_user_id),
    db: Session = Depends(get_db_sync),
) -> DQFDocumentResponse:
    """
    Update a DQF document.

    Can update document name, dates, verification status, and notes.
    """
    document = db.query(DQFDocument).filter(
        DQFDocument.id == document_id,
        DQFDocument.company_id == company_id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DQF document not found: {document_id}"
        )

    # Update fields
    if payload.document_name is not None:
        document.document_name = payload.document_name

    if payload.issue_date is not None:
        document.issue_date = payload.issue_date

    if payload.expiration_date is not None:
        document.expiration_date = payload.expiration_date
        document.is_expired = payload.expiration_date < date.today()

    if payload.verification_status is not None:
        document.verification_status = payload.verification_status  # type: ignore
        document.verified_by = user_id
        document.verified_at = datetime.utcnow()

    if payload.verification_notes is not None:
        document.verification_notes = payload.verification_notes

    db.commit()
    db.refresh(document)

    return DQFDocumentResponse.model_validate(document)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_dqf_document(
    document_id: str,
    company_id: str = Depends(_company_id),
    db: Session = Depends(get_db_sync),
) -> None:
    """Delete a DQF document."""
    document = db.query(DQFDocument).filter(
        DQFDocument.id == document_id,
        DQFDocument.company_id == company_id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DQF document not found: {document_id}"
        )

    db.delete(document)
    db.commit()


@router.get("/drivers/{driver_id}/documents", response_model=List[DQFDocumentResponse])
def get_driver_dqf_documents(
    driver_id: str,
    category: Optional[str] = Query(None, description="Filter by document category"),
    verification_status: Optional[str] = Query(None, description="Filter by verification status"),
    company_id: str = Depends(_company_id),
    db: Session = Depends(get_db_sync),
) -> List[DQFDocumentResponse]:
    """
    Get all DQF documents for a driver.

    Optional filters:
    - category: application, license, medical, background, training, certification, other
    - verification_status: pending, verified, rejected, expired
    """
    # Verify driver belongs to company
    driver = db.query(Driver).filter(
        Driver.id == driver_id,
        Driver.company_id == company_id
    ).first()

    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Driver not found: {driver_id}"
        )

    query = db.query(DQFDocument).filter(
        DQFDocument.driver_id == driver_id,
        DQFDocument.company_id == company_id
    )

    if category:
        query = query.filter(DQFDocument.document_category == category)

    if verification_status:
        query = query.filter(DQFDocument.verification_status == verification_status)

    documents = query.order_by(DQFDocument.uploaded_at.desc()).all()

    return [DQFDocumentResponse.model_validate(d) for d in documents]


@router.get("/drivers/{driver_id}/summary", response_model=DQFSummaryResponse)
def get_driver_dqf_summary(
    driver_id: str,
    company_id: str = Depends(_company_id),
    db: Session = Depends(get_db_sync),
) -> DQFSummaryResponse:
    """
    Get DQF compliance summary for a driver.

    Shows:
    - Total documents
    - Verified vs pending
    - Expired documents
    - Expiring soon (within 30 days)
    - Compliance percentage
    - Document breakdown by category
    """
    # Verify driver belongs to company
    driver = db.query(Driver).filter(
        Driver.id == driver_id,
        Driver.company_id == company_id
    ).first()

    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Driver not found: {driver_id}"
        )

    # Get all documents
    documents = db.query(DQFDocument).filter(
        DQFDocument.driver_id == driver_id,
        DQFDocument.company_id == company_id
    ).all()

    total_documents = len(documents)
    verified_documents = sum(1 for d in documents if d.verification_status == VerificationStatus.VERIFIED)
    pending_documents = sum(1 for d in documents if d.verification_status == VerificationStatus.PENDING)
    expired_documents = sum(1 for d in documents if d.is_expired)

    # Documents expiring within 30 days
    thirty_days_from_now = date.today() + timedelta(days=30)
    expiring_soon = [
        d for d in documents
        if d.expiration_date
        and not d.is_expired
        and d.expiration_date <= thirty_days_from_now
    ]
    expiring_soon_count = len(expiring_soon)

    # Compliance percentage (verified documents / total documents)
    compliance_percentage = (verified_documents / total_documents * 100) if total_documents > 0 else 0

    # Documents by category
    documents_by_category = {}
    for doc in documents:
        category = doc.document_category.value if hasattr(doc.document_category, 'value') else str(doc.document_category)
        documents_by_category[category] = documents_by_category.get(category, 0) + 1

    # Upcoming expirations (sorted by date)
    upcoming_expirations = sorted(
        [DQFDocumentResponse.model_validate(d) for d in expiring_soon],
        key=lambda x: x.expiration_date if x.expiration_date else date.max
    )

    return DQFSummaryResponse(
        driver_id=driver_id,
        driver_name=f"{driver.first_name} {driver.last_name}",
        total_documents=total_documents,
        verified_documents=verified_documents,
        pending_documents=pending_documents,
        expired_documents=expired_documents,
        expiring_soon_count=expiring_soon_count,
        compliance_percentage=round(compliance_percentage, 2),
        documents_by_category=documents_by_category,
        upcoming_expirations=upcoming_expirations
    )


@router.get("/drivers/{driver_id}/expiring", response_model=List[DQFDocumentResponse])
def get_expiring_documents(
    driver_id: str,
    days: int = Query(30, description="Number of days to look ahead"),
    company_id: str = Depends(_company_id),
    db: Session = Depends(get_db_sync),
) -> List[DQFDocumentResponse]:
    """
    Get documents expiring within specified days.

    Default: 30 days
    Use for generating expiration alerts and reminders.
    """
    # Verify driver belongs to company
    driver = db.query(Driver).filter(
        Driver.id == driver_id,
        Driver.company_id == company_id
    ).first()

    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Driver not found: {driver_id}"
        )

    cutoff_date = date.today() + timedelta(days=days)

    documents = db.query(DQFDocument).filter(
        DQFDocument.driver_id == driver_id,
        DQFDocument.company_id == company_id,
        DQFDocument.expiration_date.isnot(None),
        DQFDocument.is_expired == False,
        DQFDocument.expiration_date <= cutoff_date
    ).order_by(DQFDocument.expiration_date).all()

    return [DQFDocumentResponse.model_validate(d) for d in documents]


@router.get("/expiring-company-wide", response_model=List[DQFDocumentResponse])
def get_company_expiring_documents(
    days: int = Query(30, description="Number of days to look ahead"),
    company_id: str = Depends(_company_id),
    db: Session = Depends(get_db_sync),
) -> List[DQFDocumentResponse]:
    """
    Get all documents expiring within specified days across all company drivers.

    Useful for compliance dashboard showing company-wide expiration alerts.
    """
    cutoff_date = date.today() + timedelta(days=days)

    documents = db.query(DQFDocument).filter(
        DQFDocument.company_id == company_id,
        DQFDocument.expiration_date.isnot(None),
        DQFDocument.is_expired == False,
        DQFDocument.expiration_date <= cutoff_date
    ).order_by(DQFDocument.expiration_date).all()

    return [DQFDocumentResponse.model_validate(d) for d in documents]
