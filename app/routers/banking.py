import logging
import uuid
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import deps
from app.core.db import get_db
from app.core.config import get_settings
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
from app.services.synctera_service import (
    get_synctera_client,
    SyncteraClient,
    SyncteraError,
    BusinessCreateRequest,
    PersonCreateRequest,
    AccountCreateRequest,
    CardCreateRequest,
    AddressRequest,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


def _get_synctera() -> SyncteraClient:
    """Get Synctera client dependency."""
    return get_synctera_client()


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


# =============================================================================
# Banking Status Endpoints (Required by Frontend)
# =============================================================================


@router.get("/activation-status")
async def get_activation_status(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get banking activation status for current company."""
    from app.models.banking import BankingCustomer

    result = await db.execute(
        select(BankingCustomer).where(BankingCustomer.company_id == company_id)
    )
    customer = result.scalar_one_or_none()

    # Check for any applications
    app_result = await db.execute(
        select(BankingApplication)
        .where(BankingApplication.company_id == company_id)
        .order_by(BankingApplication.created_at.desc())
    )
    applications = app_result.scalars().all()
    latest_app = applications[0] if applications else None

    if not customer and not latest_app:
        return {
            "status": "not_started",
            "has_customer": False,
            "has_application": False,
            "message": "Banking not set up. Submit an application to get started.",
        }

    if latest_app:
        app_status = latest_app.status
        if app_status == "approved":
            return {
                "status": "approved",
                "has_customer": customer is not None,
                "has_application": True,
                "application_id": latest_app.id,
                "message": "Banking application approved. You can now create accounts.",
            }
        elif app_status == "rejected":
            return {
                "status": "rejected",
                "has_customer": customer is not None,
                "has_application": True,
                "application_id": latest_app.id,
                "rejection_reason": latest_app.rejection_reason,
                "message": "Banking application was rejected.",
            }
        elif app_status in ("submitted", "pending_review"):
            return {
                "status": "pending_review",
                "has_customer": customer is not None,
                "has_application": True,
                "application_id": latest_app.id,
                "message": "Banking application is under review.",
            }
        else:
            return {
                "status": "draft",
                "has_customer": customer is not None,
                "has_application": True,
                "application_id": latest_app.id,
                "message": "Complete and submit your banking application.",
            }

    return {
        "status": "pending",
        "has_customer": True,
        "has_application": False,
        "customer_id": customer.id if customer else None,
        "message": "Banking customer exists but no application submitted.",
    }


@router.get("/status/{company_id}")
async def get_banking_status(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
) -> Dict[str, Any]:
    """Get comprehensive banking status for a company."""
    from app.models.banking import BankingCustomer, BankingAccount

    # Check customer
    cust_result = await db.execute(
        select(BankingCustomer).where(BankingCustomer.company_id == company_id)
    )
    customer = cust_result.scalar_one_or_none()

    # Check applications
    app_result = await db.execute(
        select(BankingApplication)
        .where(BankingApplication.company_id == company_id)
        .order_by(BankingApplication.created_at.desc())
    )
    applications = app_result.scalars().all()
    latest_app = applications[0] if applications else None

    # Check accounts
    accounts_count = 0
    if customer:
        acc_result = await db.execute(
            select(BankingAccount).where(BankingAccount.company_id == company_id)
        )
        accounts_count = len(acc_result.scalars().all())

    return {
        "has_customer": customer is not None,
        "customer_id": customer.id if customer else None,
        "customer_status": customer.status if customer else None,
        "has_application": latest_app is not None,
        "application_status": latest_app.status if latest_app else None,
        "kyc_status": latest_app.kyc_status if latest_app else None,
        "has_accounts": accounts_count > 0,
        "accounts_count": accounts_count,
    }


@router.get("/customers/company/{company_id}", response_model=BankingCustomerResponse)
async def get_customer_by_company(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
) -> BankingCustomerResponse:
    """Get banking customer by company ID."""
    from app.models.banking import BankingCustomer

    result = await db.execute(
        select(BankingCustomer).where(BankingCustomer.company_id == company_id)
    )
    customer = result.scalar_one_or_none()

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Banking customer not found for this company",
        )

    return BankingCustomerResponse.model_validate(customer)


@router.get("/customers/{customer_id}/accounts")
async def get_customer_accounts(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
) -> Dict[str, Any]:
    """Get all accounts for a banking customer."""
    from app.models.banking import BankingAccount

    result = await db.execute(
        select(BankingAccount)
        .where(BankingAccount.customer_id == customer_id)
        .order_by(BankingAccount.created_at.desc())
    )
    accounts = result.scalars().all()

    return {
        "accounts": [BankingAccountResponse.model_validate(acc) for acc in accounts],
        "total": len(accounts),
    }


@router.post("/cards", response_model=BankingCardResponse, status_code=status.HTTP_201_CREATED)
async def create_card(
    payload: BankingCardCreate,
    service: BankingService = Depends(_service),
    current_user=Depends(deps.get_current_user),
) -> BankingCardResponse:
    """Create a new card for an account."""
    return await service.issue_card(payload)


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


async def _submit_to_synctera(
    app: BankingApplication,
    db: AsyncSession,
) -> None:
    """
    Background task to submit application to Synctera for KYB verification.

    This creates the business and persons in Synctera and triggers verification.
    """
    synctera = get_synctera_client()

    if not synctera.is_configured:
        logger.warning("Synctera not configured - skipping KYB submission")
        app.kyc_status = "pending_manual_review"
        await db.commit()
        return

    try:
        # Parse address from JSON string if needed
        physical_address = app.business.physical_address
        if isinstance(physical_address, str):
            import json
            physical_address = json.loads(physical_address)

        # Create business in Synctera
        business_request = BusinessCreateRequest(
            legal_name=app.business.legal_name,
            doing_business_as=app.business.dba,
            entity_type=app.business.entity_type or "LLC",
            ein=app.business.ein or "",
            formation_date=app.business.formation_date,
            formation_state=app.business.state_of_formation,
            legal_address=AddressRequest(
                address_line_1=physical_address.get("line1", ""),
                address_line_2=physical_address.get("line2"),
                city=physical_address.get("city", ""),
                state=physical_address.get("state", ""),
                postal_code=physical_address.get("zip", ""),
                country_code="US",
            ),
            phone_number=app.business.phone,
            website=app.business.website,
            naics_code=app.business.naics_code,
            industry=app.business.industry_description,
        )

        synctera_business = await synctera.create_business(business_request)
        synctera_business_id = synctera_business.get("id")

        # Store Synctera business ID
        app.business.synctera_id = synctera_business_id
        app.synctera_business_id = synctera_business_id

        # Create persons in Synctera (primary applicant and owners)
        for person in app.people:
            person_address = person.address
            if isinstance(person_address, str):
                import json
                person_address = json.loads(person_address)

            person_request = PersonCreateRequest(
                first_name=person.first_name,
                last_name=person.last_name,
                dob=person.dob or date(1980, 1, 1),  # Default if not provided
                ssn_last_4=person.ssn_last4,
                email=person.email or "",
                phone_number=person.phone,
                legal_address=AddressRequest(
                    address_line_1=person_address.get("line1", "") if person_address else "",
                    address_line_2=person_address.get("line2") if person_address else None,
                    city=person_address.get("city", "") if person_address else "",
                    state=person_address.get("state", "") if person_address else "",
                    postal_code=person_address.get("zip", "") if person_address else "",
                    country_code="US",
                ),
                is_customer=True,
            )

            synctera_person = await synctera.create_person(
                person_request,
                business_id=synctera_business_id,
            )
            person.synctera_id = synctera_person.get("id")

        # Trigger KYB verification
        await synctera.verify_business(synctera_business_id)

        # Update application status
        app.status = "pending_review"
        app.kyc_status = "pending"

        await db.commit()
        logger.info(f"Submitted application {app.reference} to Synctera (business_id: {synctera_business_id})")

    except SyncteraError as e:
        logger.error(f"Synctera submission failed for {app.reference}: {e.message}")
        app.status = "synctera_error"
        app.kyc_status = "error"
        app.rejection_reason = f"Synctera error: {e.message}"
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to submit {app.reference} to Synctera: {e}", exc_info=True)
        app.status = "error"
        app.kyc_status = "error"
        await db.commit()


@router.post("/applications", response_model=BankingApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: BankingApplicationCreate,
    background_tasks: BackgroundTasks,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> BankingApplicationResponse:
    """Create a new banking application with all KYB data and submit to Synctera."""
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

        # Submit to Synctera in background (non-blocking)
        # Note: For production, consider using a proper task queue (Celery, etc.)
        synctera = get_synctera_client()
        if synctera.is_configured:
            # For now, do it inline since background tasks with DB sessions are tricky
            await _submit_to_synctera(app, db)

        # Reload after Synctera submission
        await db.refresh(app)

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


@router.delete("/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
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

