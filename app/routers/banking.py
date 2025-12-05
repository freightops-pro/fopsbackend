import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import deps
from app.core.db import get_db
from app.models.banking import (
    BankingApplication,
    BankingApplicationDocument,
    BankingBusiness,
    BankingPerson,
)
from app.schemas.banking import (
    BankingAccountCreate,
    BankingAccountResponse,
    BankingApplicationCreate,
    BankingApplicationResponse,
    BankingApplicationSummary,
    BankingApplicationUpdate,
    BankingCardCreate,
    BankingCardResponse,
    BankingCustomerCreate,
    BankingCustomerResponse,
    BankingTransactionResponse,
    BusinessResponse,
    DocumentResponse,
    PersonResponse,
)
from app.services.banking import BankingService

logger = logging.getLogger(__name__)

router = APIRouter()


async def _service(db: AsyncSession = Depends(get_db)) -> BankingService:
    return BankingService(db)


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.company_id


@router.post("/customer", response_model=BankingCustomerResponse, status_code=status.HTTP_201_CREATED)
async def ensure_customer(
    payload: BankingCustomerCreate,
    company_id: str = Depends(_company_id),
    service: BankingService = Depends(_service),
) -> BankingCustomerResponse:
    return await service.ensure_customer(company_id, payload)


@router.get("/accounts", response_model=List[BankingAccountResponse])
async def list_accounts(
    company_id: str = Depends(_company_id),
    service: BankingService = Depends(_service),
) -> List[BankingAccountResponse]:
    return await service.list_accounts(company_id)


@router.post("/accounts", response_model=BankingAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: BankingAccountCreate,
    company_id: str = Depends(_company_id),
    service: BankingService = Depends(_service),
) -> BankingAccountResponse:
    return await service.create_account(company_id, payload)


@router.get("/accounts/{account_id}/cards", response_model=List[BankingCardResponse])
async def list_cards(
    account_id: str,
    service: BankingService = Depends(_service),
) -> List[BankingCardResponse]:
    return await service.list_cards(account_id)


@router.post("/accounts/{account_id}/cards", response_model=BankingCardResponse, status_code=status.HTTP_201_CREATED)
async def issue_card(
    account_id: str,
    payload: BankingCardCreate,
    service: BankingService = Depends(_service),
) -> BankingCardResponse:
    if payload.account_id != account_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account id mismatch")
    return await service.issue_card(payload)


@router.get("/accounts/{account_id}/transactions", response_model=List[BankingTransactionResponse])
async def list_transactions(
    account_id: str,
    service: BankingService = Depends(_service),
) -> List[BankingTransactionResponse]:
    return await service.list_transactions(account_id)


# =============================================================================
# Banking Application Endpoints (Multi-step KYB Onboarding)
# =============================================================================


def _generate_reference() -> str:
    """Generate a unique application reference."""
    return f"APP-{uuid.uuid4().hex[:8].upper()}"


def _build_application_response(app: BankingApplication) -> BankingApplicationResponse:
    """Build full application response from model."""
    primary = None
    owners = []
    signers = []

    for person in app.people:
        person_resp = PersonResponse.model_validate(person)
        if person.person_type == "primary":
            primary = person_resp
        elif person.person_type == "owner":
            owners.append(person_resp)
        elif person.person_type == "signer":
            signers.append(person_resp)

    return BankingApplicationResponse(
        id=app.id,
        reference=app.reference,
        status=app.status,
        kyc_status=app.kyc_status,
        submitted_at=app.submitted_at,
        created_at=app.created_at,
        updated_at=app.updated_at,
        business=BusinessResponse.model_validate(app.business) if app.business else None,
        primary=primary,
        owners=owners,
        signers=signers,
        documents=[DocumentResponse.model_validate(d) for d in app.documents],
        account_choices=app.account_choices,
    )


@router.get("/applications", response_model=List[BankingApplicationSummary])
async def list_applications(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> List[BankingApplicationSummary]:
    """List all banking applications for the company."""
    result = await db.execute(
        select(BankingApplication)
        .where(BankingApplication.company_id == company_id)
        .options(selectinload(BankingApplication.business))
        .order_by(BankingApplication.created_at.desc())
    )
    applications = result.scalars().all()

    return [
        BankingApplicationSummary(
            id=app.id,
            reference=app.reference,
            status=app.status,
            business_name=app.business.legal_name if app.business else None,
            kyc_status=app.kyc_status,
            submitted_at=app.submitted_at,
            created_at=app.created_at,
        )
        for app in applications
    ]


@router.get("/applications/{application_id}", response_model=BankingApplicationResponse)
async def get_application(
    application_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> BankingApplicationResponse:
    """Get a specific banking application with all details."""
    result = await db.execute(
        select(BankingApplication)
        .where(
            BankingApplication.id == application_id,
            BankingApplication.company_id == company_id,
        )
        .options(
            selectinload(BankingApplication.business),
            selectinload(BankingApplication.people),
            selectinload(BankingApplication.documents),
        )
    )
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    return _build_application_response(app)


@router.post("/applications", response_model=BankingApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: BankingApplicationCreate,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> BankingApplicationResponse:
    """Create a new banking application with all KYB data."""
    try:
        # Create application record
        app_id = str(uuid.uuid4())
        application = BankingApplication(
            id=app_id,
            company_id=company_id,
            reference=_generate_reference(),
            status="submitted",
            submitted_at=datetime.utcnow(),
            account_choices=payload.account_choices.model_dump() if payload.account_choices else None,
        )
        db.add(application)

        # Create business record
        business_id = str(uuid.uuid4())
        business = BankingBusiness(
            id=business_id,
            application_id=app_id,
            legal_name=payload.business.legal_name,
            dba=payload.business.dba,
            entity_type=payload.business.entity_type,
            ein=payload.business.ein,
            formation_date=payload.business.formation_date,
            state_of_formation=payload.business.state_of_formation,
            physical_address=payload.business.physical_address,
            mailing_address=payload.business.mailing_address,
            phone=payload.business.phone,
            website=payload.business.website,
            naics_code=payload.business.naics_code,
            industry_description=payload.business.industry_description,
            employees=payload.business.employees,
            estimated_revenue=payload.business.estimated_revenue,
            monthly_volume=payload.business.monthly_volume,
            cash_heavy=payload.business.cash_heavy,
            international_transactions=payload.business.international_transactions,
        )
        db.add(business)

        # Create primary applicant
        primary_id = str(uuid.uuid4())
        primary_person = BankingPerson(
            id=primary_id,
            application_id=app_id,
            person_type="primary",
            first_name=payload.primary.first_name,
            last_name=payload.primary.last_name,
            dob=payload.primary.dob,
            ssn_last4=payload.primary.ssn_last4,
            address=payload.primary.address,
            email=payload.primary.email,
            phone=payload.primary.phone,
            citizenship=payload.primary.citizenship,
            id_type=payload.primary.id_type,
            id_file_url=payload.primary.id_file_url,
        )
        db.add(primary_person)
        application.primary_person_id = primary_id

        # Create owners
        for owner_data in payload.owners:
            owner = BankingPerson(
                id=str(uuid.uuid4()),
                application_id=app_id,
                person_type="owner",
                first_name=owner_data.first_name,
                last_name=owner_data.last_name,
                dob=owner_data.dob,
                ssn_last4=owner_data.ssn_last4,
                address=owner_data.address,
                email=owner_data.email,
                phone=owner_data.phone,
                citizenship=owner_data.citizenship,
                ownership_pct=owner_data.ownership_pct,
                is_controller=owner_data.is_controller,
                role=owner_data.role,
                id_type=owner_data.id_type,
                id_file_url=owner_data.id_file_url,
            )
            db.add(owner)

        # Create signers
        for signer_data in payload.signers:
            signer = BankingPerson(
                id=str(uuid.uuid4()),
                application_id=app_id,
                person_type="signer",
                first_name=signer_data.first_name,
                last_name=signer_data.last_name,
                dob=signer_data.dob,
                ssn_last4=signer_data.ssn_last4,
                address=signer_data.address,
                email=signer_data.email,
                phone=signer_data.phone,
                citizenship=signer_data.citizenship,
                role=signer_data.role,
                id_type=signer_data.id_type,
                id_file_url=signer_data.id_file_url,
            )
            db.add(signer)

        # Create document records
        for doc_type, file_name in payload.documents.items():
            if file_name:
                doc = BankingApplicationDocument(
                    id=str(uuid.uuid4()),
                    application_id=app_id,
                    doc_type=doc_type,
                    file_name=file_name,
                )
                db.add(doc)

        await db.commit()

        # Reload with relationships
        result = await db.execute(
            select(BankingApplication)
            .where(BankingApplication.id == app_id)
            .options(
                selectinload(BankingApplication.business),
                selectinload(BankingApplication.people),
                selectinload(BankingApplication.documents),
            )
        )
        app = result.scalar_one()

        logger.info(f"Created banking application {app.reference} for company {company_id}")

        # TODO: Queue KYC/OFAC screening job here
        # await queue_kyc_check(app)

        return _build_application_response(app)

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create banking application: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create application: {str(e)}",
        )


@router.patch("/applications/{application_id}", response_model=BankingApplicationResponse)
async def update_application(
    application_id: str,
    payload: BankingApplicationUpdate,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> BankingApplicationResponse:
    """Update application status (admin use)."""
    result = await db.execute(
        select(BankingApplication)
        .where(
            BankingApplication.id == application_id,
            BankingApplication.company_id == company_id,
        )
        .options(
            selectinload(BankingApplication.business),
            selectinload(BankingApplication.people),
            selectinload(BankingApplication.documents),
        )
    )
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    if payload.status:
        app.status = payload.status
        if payload.status == "approved":
            app.reviewed_at = datetime.utcnow()
        elif payload.status == "rejected":
            app.reviewed_at = datetime.utcnow()
            app.rejection_reason = payload.rejection_reason

    if payload.kyc_status:
        app.kyc_status = payload.kyc_status
        if payload.kyc_status in ("passed", "failed"):
            app.kyc_completed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(app)

    return _build_application_response(app)


@router.delete("/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a draft application."""
    result = await db.execute(
        select(BankingApplication).where(
            BankingApplication.id == application_id,
            BankingApplication.company_id == company_id,
        )
    )
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    if app.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft applications can be deleted",
        )

    await db.delete(app)
    await db.commit()

