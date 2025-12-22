import logging
import uuid
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy import select, text
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


# =============================================================================
# Card Management Endpoints (Activate, Suspend, Terminate)
# =============================================================================


@router.post("/cards/{card_id}/activate")
async def activate_card(
    card_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Activate a card."""
    from app.models.banking import BankingCard, BankingAccount

    # Find the card
    result = await db.execute(
        select(BankingCard).where(BankingCard.id == card_id)
    )
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")

    # Verify ownership via account
    acc_result = await db.execute(
        select(BankingAccount).where(
            BankingAccount.id == card.account_id,
            BankingAccount.company_id == company_id,
        )
    )
    if not acc_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Call Synctera if card has synctera_id
    synctera = get_synctera_client()
    if synctera.is_configured and card.synctera_id:
        try:
            await synctera.activate_card(card.synctera_id)
        except SyncteraError as e:
            logger.error(f"Failed to activate card in Synctera: {e.message}")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Synctera error: {e.message}")

    # Update local status
    card.status = "active"
    await db.commit()

    return {"message": "Card activated successfully", "status": "active"}


@router.post("/cards/{card_id}/suspend")
async def suspend_card(
    card_id: str,
    payload: Optional[Dict[str, Any]] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Suspend a card (can be reactivated later)."""
    from app.models.banking import BankingCard, BankingAccount

    reason = (payload or {}).get("reason", "CUSTOMER_REQUEST")

    result = await db.execute(
        select(BankingCard).where(BankingCard.id == card_id)
    )
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")

    # Verify ownership
    acc_result = await db.execute(
        select(BankingAccount).where(
            BankingAccount.id == card.account_id,
            BankingAccount.company_id == company_id,
        )
    )
    if not acc_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Call Synctera
    synctera = get_synctera_client()
    if synctera.is_configured and card.synctera_id:
        try:
            await synctera.suspend_card(card.synctera_id, reason)
        except SyncteraError as e:
            logger.error(f"Failed to suspend card in Synctera: {e.message}")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Synctera error: {e.message}")

    card.status = "suspended"
    await db.commit()

    return {"message": "Card suspended successfully", "status": "suspended"}


@router.post("/cards/{card_id}/terminate")
async def terminate_card(
    card_id: str,
    payload: Optional[Dict[str, Any]] = None,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Terminate a card permanently."""
    from app.models.banking import BankingCard, BankingAccount

    reason = (payload or {}).get("reason", "CUSTOMER_REQUEST")

    result = await db.execute(
        select(BankingCard).where(BankingCard.id == card_id)
    )
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")

    # Verify ownership
    acc_result = await db.execute(
        select(BankingAccount).where(
            BankingAccount.id == card.account_id,
            BankingAccount.company_id == company_id,
        )
    )
    if not acc_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Call Synctera
    synctera = get_synctera_client()
    if synctera.is_configured and card.synctera_id:
        try:
            await synctera.terminate_card(card.synctera_id, reason)
        except SyncteraError as e:
            logger.error(f"Failed to terminate card in Synctera: {e.message}")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Synctera error: {e.message}")

    card.status = "terminated"
    await db.commit()

    return {"message": "Card terminated successfully", "status": "terminated"}


@router.get("/cards/{card_id}")
async def get_card(
    card_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get card details."""
    from app.models.banking import BankingCard, BankingAccount

    result = await db.execute(
        select(BankingCard).where(BankingCard.id == card_id)
    )
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")

    # Verify ownership
    acc_result = await db.execute(
        select(BankingAccount).where(
            BankingAccount.id == card.account_id,
            BankingAccount.company_id == company_id,
        )
    )
    if not acc_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return BankingCardResponse.model_validate(card).model_dump()


@router.get("/accounts/{account_id}/transactions", response_model=List[BankingTransactionResponse])
async def list_transactions(
    account_id: str,
    service: BankingService = Depends(_service),
) -> List[BankingTransactionResponse]:
    return await service.list_transactions(account_id)


@router.post("/accounts/{account_id}/balance/refresh")
async def refresh_account_balance(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
) -> Dict[str, Any]:
    """Refresh balance for a specific account from Synctera."""
    from app.models.banking import BankingAccount

    # Find the account
    result = await db.execute(
        select(BankingAccount).where(BankingAccount.id == account_id)
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    # If we have a Synctera account ID, fetch latest balance
    synctera = get_synctera_client()
    if synctera.is_configured and account.synctera_id:
        try:
            synctera_account = await synctera.get_account(account.synctera_id)
            account.current_balance = synctera_account.get("balance", {}).get("current_balance", 0)
            account.available_balance = synctera_account.get("balance", {}).get("available_balance", 0)
            account.pending_balance = synctera_account.get("balance", {}).get("pending_balance", 0)
            await db.commit()
            logger.info(f"Refreshed balance for account {account_id}")
        except SyncteraError as e:
            logger.error(f"Failed to refresh balance from Synctera: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to refresh from Synctera: {e.message}",
            )

    return {
        "message": "Balance refreshed",
        "current_balance": account.current_balance,
        "available_balance": account.available_balance,
    }


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


# =============================================================================
# Banking Statement Endpoints (Synctera Integration)
# =============================================================================


@router.get("/statements")
async def list_all_statements(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List all statements for the company."""
    from app.models.banking import BankingStatement, BankingAccount

    result = await db.execute(
        select(BankingStatement)
        .where(BankingStatement.company_id == company_id)
        .order_by(BankingStatement.statement_date.desc())
    )
    statements = result.scalars().all()

    # Get account names
    account_ids = list(set(s.account_id for s in statements))
    if account_ids:
        acc_result = await db.execute(
            select(BankingAccount).where(BankingAccount.id.in_(account_ids))
        )
        accounts = {a.id: a.nickname or a.account_type for a in acc_result.scalars().all()}
    else:
        accounts = {}

    return {
        "statements": [
            {
                "id": s.id,
                "account_id": s.account_id,
                "account_name": accounts.get(s.account_id, "Unknown"),
                "statement_date": s.statement_date.isoformat() if s.statement_date else None,
                "period_start": s.period_start.isoformat() if s.period_start else None,
                "period_end": s.period_end.isoformat() if s.period_end else None,
                "opening_balance": float(s.opening_balance or 0),
                "closing_balance": float(s.closing_balance or 0),
                "total_credits": float(s.total_credits or 0),
                "total_debits": float(s.total_debits or 0),
                "transaction_count": s.transaction_count or 0,
                "pdf_url": s.pdf_url,
                "status": s.status,
                "synctera_id": s.synctera_id,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in statements
        ],
        "total": len(statements),
    }


@router.get("/accounts/{account_id}/statements")
async def list_account_statements(
    account_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List statements for a specific account."""
    from app.models.banking import BankingStatement, BankingAccount

    # Verify account ownership
    acc_result = await db.execute(
        select(BankingAccount).where(
            BankingAccount.id == account_id,
            BankingAccount.company_id == company_id,
        )
    )
    account = acc_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    # Get statements
    result = await db.execute(
        select(BankingStatement)
        .where(
            BankingStatement.account_id == account_id,
            BankingStatement.company_id == company_id,
        )
        .order_by(BankingStatement.statement_date.desc())
    )
    statements = result.scalars().all()

    return {
        "statements": [
            {
                "id": s.id,
                "account_id": s.account_id,
                "account_name": account.nickname or account.account_type,
                "statement_date": s.statement_date.isoformat() if s.statement_date else None,
                "period_start": s.period_start.isoformat() if s.period_start else None,
                "period_end": s.period_end.isoformat() if s.period_end else None,
                "opening_balance": float(s.opening_balance or 0),
                "closing_balance": float(s.closing_balance or 0),
                "total_credits": float(s.total_credits or 0),
                "total_debits": float(s.total_debits or 0),
                "transaction_count": s.transaction_count or 0,
                "pdf_url": s.pdf_url,
                "status": s.status,
                "synctera_id": s.synctera_id,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in statements
        ],
        "total": len(statements),
    }


@router.get("/statements/{statement_id}")
async def get_statement(
    statement_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get a specific statement."""
    from app.models.banking import BankingStatement, BankingAccount

    result = await db.execute(
        select(BankingStatement).where(
            BankingStatement.id == statement_id,
            BankingStatement.company_id == company_id,
        )
    )
    statement = result.scalar_one_or_none()

    if not statement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found")

    # Get account name
    acc_result = await db.execute(
        select(BankingAccount).where(BankingAccount.id == statement.account_id)
    )
    account = acc_result.scalar_one_or_none()

    return {
        "id": statement.id,
        "account_id": statement.account_id,
        "account_name": account.nickname or account.account_type if account else "Unknown",
        "statement_date": statement.statement_date.isoformat() if statement.statement_date else None,
        "period_start": statement.period_start.isoformat() if statement.period_start else None,
        "period_end": statement.period_end.isoformat() if statement.period_end else None,
        "opening_balance": float(statement.opening_balance or 0),
        "closing_balance": float(statement.closing_balance or 0),
        "total_credits": float(statement.total_credits or 0),
        "total_debits": float(statement.total_debits or 0),
        "transaction_count": statement.transaction_count or 0,
        "pdf_url": statement.pdf_url,
        "status": statement.status,
        "synctera_id": statement.synctera_id,
        "created_at": statement.created_at.isoformat() if statement.created_at else None,
    }


@router.get("/statements/{statement_id}/download")
async def download_statement(
    statement_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get download URL for a statement PDF."""
    from app.models.banking import BankingStatement

    result = await db.execute(
        select(BankingStatement).where(
            BankingStatement.id == statement_id,
            BankingStatement.company_id == company_id,
        )
    )
    statement = result.scalar_one_or_none()

    if not statement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found")

    if not statement.pdf_url:
        # In a real implementation, we would generate the PDF here
        # For now, return a placeholder indicating PDF generation is needed
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Statement PDF not yet available. PDF generation is pending.",
        )

    return {"download_url": statement.pdf_url}


# =============================================================================
# Banking Document Endpoints (Synctera Integration)
# =============================================================================


@router.get("/documents")
async def list_all_documents(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List all banking documents for the company."""
    from app.models.banking import BankingDocument

    result = await db.execute(
        select(BankingDocument)
        .where(BankingDocument.company_id == company_id)
        .order_by(BankingDocument.created_at.desc())
    )
    documents = result.scalars().all()

    return {
        "documents": [
            {
                "id": d.id,
                "customer_id": d.customer_id,
                "account_id": d.account_id,
                "document_type": d.document_type,
                "title": d.title,
                "description": d.description,
                "file_url": d.file_url,
                "file_name": d.file_name,
                "file_size": d.file_size,
                "year": d.year,
                "status": d.status,
                "expires_at": d.expires_at.isoformat() if d.expires_at else None,
                "synctera_id": d.synctera_id,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
            for d in documents
        ],
        "total": len(documents),
    }


@router.get("/customers/{customer_id}/documents")
async def list_customer_documents(
    customer_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List documents for a specific customer."""
    from app.models.banking import BankingDocument, BankingCustomer

    # Verify customer ownership
    cust_result = await db.execute(
        select(BankingCustomer).where(
            BankingCustomer.id == customer_id,
            BankingCustomer.company_id == company_id,
        )
    )
    customer = cust_result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    # Get documents
    result = await db.execute(
        select(BankingDocument)
        .where(
            BankingDocument.customer_id == customer_id,
            BankingDocument.company_id == company_id,
        )
        .order_by(BankingDocument.created_at.desc())
    )
    documents = result.scalars().all()

    return {
        "documents": [
            {
                "id": d.id,
                "customer_id": d.customer_id,
                "account_id": d.account_id,
                "document_type": d.document_type,
                "title": d.title,
                "description": d.description,
                "file_url": d.file_url,
                "file_name": d.file_name,
                "file_size": d.file_size,
                "year": d.year,
                "status": d.status,
                "expires_at": d.expires_at.isoformat() if d.expires_at else None,
                "synctera_id": d.synctera_id,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
            for d in documents
        ],
        "total": len(documents),
    }


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get a specific document."""
    from app.models.banking import BankingDocument

    result = await db.execute(
        select(BankingDocument).where(
            BankingDocument.id == document_id,
            BankingDocument.company_id == company_id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return {
        "id": document.id,
        "customer_id": document.customer_id,
        "account_id": document.account_id,
        "document_type": document.document_type,
        "title": document.title,
        "description": document.description,
        "file_url": document.file_url,
        "file_name": document.file_name,
        "file_size": document.file_size,
        "year": document.year,
        "status": document.status,
        "expires_at": document.expires_at.isoformat() if document.expires_at else None,
        "synctera_id": document.synctera_id,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
    }


@router.get("/documents/{document_id}/download")
async def download_document(
    document_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get download URL for a document."""
    from app.models.banking import BankingDocument

    result = await db.execute(
        select(BankingDocument).where(
            BankingDocument.id == document_id,
            BankingDocument.company_id == company_id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if not document.file_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not available",
        )

    return {"download_url": document.file_url}


@router.post("/documents/request", status_code=status.HTTP_201_CREATED)
async def request_document(
    payload: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Request generation of a document (e.g., tax form, account verification)."""
    from app.models.banking import BankingDocument, BankingCustomer

    customer_id = payload.get("customer_id")
    document_type = payload.get("document_type")
    account_id = payload.get("account_id")
    year = payload.get("year")

    if not customer_id or not document_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="customer_id and document_type are required",
        )

    # Verify customer ownership
    cust_result = await db.execute(
        select(BankingCustomer).where(
            BankingCustomer.id == customer_id,
            BankingCustomer.company_id == company_id,
        )
    )
    customer = cust_result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    # Create document record (pending generation)
    doc_id = str(uuid.uuid4())
    title_map = {
        "account_agreement": "Account Agreement",
        "fee_schedule": "Fee Schedule",
        "privacy_policy": "Privacy Policy",
        "terms_of_service": "Terms of Service",
        "tax_1099": f"1099-INT Tax Form ({year})" if year else "1099-INT Tax Form",
        "tax_1099_int": f"1099-INT Tax Form ({year})" if year else "1099-INT Tax Form",
        "account_verification": "Account Verification Letter",
        "wire_instructions": "Wire Instructions",
        "ach_authorization": "ACH Authorization Form",
    }

    document = BankingDocument(
        id=doc_id,
        company_id=company_id,
        customer_id=customer_id,
        account_id=account_id,
        document_type=document_type,
        title=title_map.get(document_type, document_type.replace("_", " ").title()),
        year=year,
        status="generating",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # In a real implementation, we would trigger document generation here
    # (either via Synctera API or internal PDF generation)

    return {
        "id": document.id,
        "customer_id": document.customer_id,
        "account_id": document.account_id,
        "document_type": document.document_type,
        "title": document.title,
        "description": document.description,
        "file_url": document.file_url,
        "file_name": document.file_name,
        "file_size": document.file_size,
        "year": document.year,
        "status": document.status,
        "expires_at": document.expires_at.isoformat() if document.expires_at else None,
        "synctera_id": document.synctera_id,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
    }


# =============================================================================
# Banking Dispute Endpoints (Synctera Integration)
# =============================================================================


@router.get("/disputes")
async def list_all_disputes(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List all disputes for the company."""
    from app.models.banking import BankingDispute

    result = await db.execute(
        select(BankingDispute)
        .where(BankingDispute.company_id == company_id)
        .order_by(BankingDispute.created_at.desc())
    )
    disputes = result.scalars().all()

    return {
        "disputes": [
            {
                "id": d.id,
                "account_id": d.account_id,
                "transaction_id": d.transaction_id,
                "transaction_date": d.transaction_date.isoformat() if d.transaction_date else None,
                "transaction_amount": float(d.transaction_amount) if d.transaction_amount else None,
                "transaction_description": d.transaction_description,
                "merchant_name": d.merchant_name,
                "reason": d.reason,
                "reason_details": d.reason_details,
                "disputed_amount": float(d.disputed_amount),
                "status": d.status,
                "lifecycle_state": d.lifecycle_state,
                "decision": d.decision,
                "credit_status": d.credit_status,
                "provisional_credit": float(d.provisional_credit) if d.provisional_credit else None,
                "provisional_credit_date": d.provisional_credit_date.isoformat() if d.provisional_credit_date else None,
                "resolution_date": d.resolution_date.isoformat() if d.resolution_date else None,
                "resolution_notes": d.resolution_notes,
                "documents": d.documents,
                "synctera_id": d.synctera_id,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
            for d in disputes
        ],
        "total": len(disputes),
    }


@router.get("/accounts/{account_id}/disputes")
async def list_account_disputes(
    account_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List disputes for a specific account."""
    from app.models.banking import BankingDispute, BankingAccount

    # Verify account ownership
    acc_result = await db.execute(
        select(BankingAccount).where(
            BankingAccount.id == account_id,
            BankingAccount.company_id == company_id,
        )
    )
    account = acc_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    # Get disputes
    result = await db.execute(
        select(BankingDispute)
        .where(
            BankingDispute.account_id == account_id,
            BankingDispute.company_id == company_id,
        )
        .order_by(BankingDispute.created_at.desc())
    )
    disputes = result.scalars().all()

    return {
        "disputes": [
            {
                "id": d.id,
                "account_id": d.account_id,
                "transaction_id": d.transaction_id,
                "transaction_date": d.transaction_date.isoformat() if d.transaction_date else None,
                "transaction_amount": float(d.transaction_amount) if d.transaction_amount else None,
                "transaction_description": d.transaction_description,
                "merchant_name": d.merchant_name,
                "reason": d.reason,
                "reason_details": d.reason_details,
                "disputed_amount": float(d.disputed_amount),
                "status": d.status,
                "lifecycle_state": d.lifecycle_state,
                "decision": d.decision,
                "credit_status": d.credit_status,
                "provisional_credit": float(d.provisional_credit) if d.provisional_credit else None,
                "provisional_credit_date": d.provisional_credit_date.isoformat() if d.provisional_credit_date else None,
                "resolution_date": d.resolution_date.isoformat() if d.resolution_date else None,
                "resolution_notes": d.resolution_notes,
                "documents": d.documents,
                "synctera_id": d.synctera_id,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
            for d in disputes
        ],
        "total": len(disputes),
    }


@router.get("/disputes/{dispute_id}")
async def get_dispute(
    dispute_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get a specific dispute."""
    from app.models.banking import BankingDispute

    result = await db.execute(
        select(BankingDispute).where(
            BankingDispute.id == dispute_id,
            BankingDispute.company_id == company_id,
        )
    )
    dispute = result.scalar_one_or_none()

    if not dispute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")

    return {
        "id": dispute.id,
        "account_id": dispute.account_id,
        "transaction_id": dispute.transaction_id,
        "transaction_date": dispute.transaction_date.isoformat() if dispute.transaction_date else None,
        "transaction_amount": float(dispute.transaction_amount) if dispute.transaction_amount else None,
        "transaction_description": dispute.transaction_description,
        "merchant_name": dispute.merchant_name,
        "reason": dispute.reason,
        "reason_details": dispute.reason_details,
        "disputed_amount": float(dispute.disputed_amount),
        "status": dispute.status,
        "lifecycle_state": dispute.lifecycle_state,
        "decision": dispute.decision,
        "credit_status": dispute.credit_status,
        "provisional_credit": float(dispute.provisional_credit) if dispute.provisional_credit else None,
        "provisional_credit_date": dispute.provisional_credit_date.isoformat() if dispute.provisional_credit_date else None,
        "resolution_date": dispute.resolution_date.isoformat() if dispute.resolution_date else None,
        "resolution_notes": dispute.resolution_notes,
        "documents": dispute.documents,
        "synctera_id": dispute.synctera_id,
        "created_at": dispute.created_at.isoformat() if dispute.created_at else None,
        "updated_at": dispute.updated_at.isoformat() if dispute.updated_at else None,
    }


@router.post("/disputes", status_code=status.HTTP_201_CREATED)
async def create_dispute(
    payload: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new dispute for a transaction."""
    from app.models.banking import BankingDispute, BankingAccount, BankingTransaction

    account_id = payload.get("account_id")
    transaction_id = payload.get("transaction_id")
    reason = payload.get("reason")
    reason_details = payload.get("reason_details")
    disputed_amount = payload.get("disputed_amount")
    documents = payload.get("documents", [])

    if not all([account_id, transaction_id, reason, disputed_amount]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="account_id, transaction_id, reason, and disputed_amount are required",
        )

    # Verify account ownership
    acc_result = await db.execute(
        select(BankingAccount).where(
            BankingAccount.id == account_id,
            BankingAccount.company_id == company_id,
        )
    )
    account = acc_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    # Get transaction details (if exists in our DB)
    txn_result = await db.execute(
        select(BankingTransaction).where(BankingTransaction.id == transaction_id)
    )
    transaction = txn_result.scalar_one_or_none()

    # Create dispute
    dispute_id = str(uuid.uuid4())
    dispute = BankingDispute(
        id=dispute_id,
        company_id=company_id,
        account_id=account_id,
        transaction_id=transaction_id,
        transaction_date=transaction.posted_at if transaction else None,
        transaction_amount=transaction.amount if transaction else None,
        transaction_description=transaction.description if transaction else None,
        reason=reason,
        reason_details=reason_details,
        disputed_amount=disputed_amount,
        status="submitted",
        lifecycle_state="PENDING_ACTION",
        credit_status="NONE",
        documents=documents,
        date_customer_reported=datetime.utcnow(),
    )
    db.add(dispute)
    await db.commit()
    await db.refresh(dispute)

    # In a real implementation, we would submit to Synctera here:
    # synctera = get_synctera_client()
    # if synctera.is_configured and account.synctera_id:
    #     try:
    #         result = await synctera.create_dispute(...)
    #         dispute.synctera_id = result.get("id")
    #         await db.commit()
    #     except SyncteraError as e:
    #         logger.error(f"Failed to create dispute in Synctera: {e.message}")

    return {
        "id": dispute.id,
        "account_id": dispute.account_id,
        "transaction_id": dispute.transaction_id,
        "transaction_date": dispute.transaction_date.isoformat() if dispute.transaction_date else None,
        "transaction_amount": float(dispute.transaction_amount) if dispute.transaction_amount else None,
        "transaction_description": dispute.transaction_description,
        "merchant_name": dispute.merchant_name,
        "reason": dispute.reason,
        "reason_details": dispute.reason_details,
        "disputed_amount": float(dispute.disputed_amount),
        "status": dispute.status,
        "lifecycle_state": dispute.lifecycle_state,
        "decision": dispute.decision,
        "credit_status": dispute.credit_status,
        "provisional_credit": float(dispute.provisional_credit) if dispute.provisional_credit else None,
        "provisional_credit_date": dispute.provisional_credit_date.isoformat() if dispute.provisional_credit_date else None,
        "resolution_date": dispute.resolution_date.isoformat() if dispute.resolution_date else None,
        "resolution_notes": dispute.resolution_notes,
        "documents": dispute.documents,
        "synctera_id": dispute.synctera_id,
        "created_at": dispute.created_at.isoformat() if dispute.created_at else None,
        "updated_at": dispute.updated_at.isoformat() if dispute.updated_at else None,
    }


@router.patch("/disputes/{dispute_id}")
async def update_dispute(
    dispute_id: str,
    payload: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Update a dispute (add documents, update status)."""
    from app.models.banking import BankingDispute

    result = await db.execute(
        select(BankingDispute).where(
            BankingDispute.id == dispute_id,
            BankingDispute.company_id == company_id,
        )
    )
    dispute = result.scalar_one_or_none()

    if not dispute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")

    # Update allowed fields
    if "documents" in payload:
        current_docs = dispute.documents or []
        new_docs = payload["documents"] or []
        dispute.documents = list(set(current_docs + new_docs))

    if "reason_details" in payload:
        dispute.reason_details = payload["reason_details"]

    if "status" in payload:
        dispute.status = payload["status"]

    await db.commit()
    await db.refresh(dispute)

    return {
        "id": dispute.id,
        "account_id": dispute.account_id,
        "transaction_id": dispute.transaction_id,
        "transaction_date": dispute.transaction_date.isoformat() if dispute.transaction_date else None,
        "transaction_amount": float(dispute.transaction_amount) if dispute.transaction_amount else None,
        "transaction_description": dispute.transaction_description,
        "merchant_name": dispute.merchant_name,
        "reason": dispute.reason,
        "reason_details": dispute.reason_details,
        "disputed_amount": float(dispute.disputed_amount),
        "status": dispute.status,
        "lifecycle_state": dispute.lifecycle_state,
        "decision": dispute.decision,
        "credit_status": dispute.credit_status,
        "provisional_credit": float(dispute.provisional_credit) if dispute.provisional_credit else None,
        "provisional_credit_date": dispute.provisional_credit_date.isoformat() if dispute.provisional_credit_date else None,
        "resolution_date": dispute.resolution_date.isoformat() if dispute.resolution_date else None,
        "resolution_notes": dispute.resolution_notes,
        "documents": dispute.documents,
        "synctera_id": dispute.synctera_id,
        "created_at": dispute.created_at.isoformat() if dispute.created_at else None,
        "updated_at": dispute.updated_at.isoformat() if dispute.updated_at else None,
    }


@router.post("/disputes/{dispute_id}/withdraw")
async def withdraw_dispute(
    dispute_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Withdraw a dispute."""
    from app.models.banking import BankingDispute

    result = await db.execute(
        select(BankingDispute).where(
            BankingDispute.id == dispute_id,
            BankingDispute.company_id == company_id,
        )
    )
    dispute = result.scalar_one_or_none()

    if not dispute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")

    # Can only withdraw disputes that are still open
    if dispute.status in ("resolved_in_favor", "resolved_against", "withdrawn", "closed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot withdraw dispute with status: {dispute.status}",
        )

    dispute.status = "withdrawn"
    dispute.resolution_date = datetime.utcnow()
    dispute.resolution_notes = "Withdrawn by customer"

    await db.commit()
    await db.refresh(dispute)

    # In a real implementation, we would notify Synctera here

    return {
        "id": dispute.id,
        "account_id": dispute.account_id,
        "transaction_id": dispute.transaction_id,
        "transaction_date": dispute.transaction_date.isoformat() if dispute.transaction_date else None,
        "transaction_amount": float(dispute.transaction_amount) if dispute.transaction_amount else None,
        "transaction_description": dispute.transaction_description,
        "merchant_name": dispute.merchant_name,
        "reason": dispute.reason,
        "reason_details": dispute.reason_details,
        "disputed_amount": float(dispute.disputed_amount),
        "status": dispute.status,
        "lifecycle_state": dispute.lifecycle_state,
        "decision": dispute.decision,
        "credit_status": dispute.credit_status,
        "provisional_credit": float(dispute.provisional_credit) if dispute.provisional_credit else None,
        "provisional_credit_date": dispute.provisional_credit_date.isoformat() if dispute.provisional_credit_date else None,
        "resolution_date": dispute.resolution_date.isoformat() if dispute.resolution_date else None,
        "resolution_notes": dispute.resolution_notes,
        "documents": dispute.documents,
        "synctera_id": dispute.synctera_id,
        "created_at": dispute.created_at.isoformat() if dispute.created_at else None,
        "updated_at": dispute.updated_at.isoformat() if dispute.updated_at else None,
    }


# =============================================================================
# Transfer Endpoints (Internal, ACH, Wire)
# =============================================================================


@router.post("/transfers/internal", status_code=status.HTTP_201_CREATED)
async def create_internal_transfer(
    payload: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
) -> Dict[str, Any]:
    """Create an internal transfer between two accounts."""
    from app.services.transfer_service import TransferService

    from_account_id = payload.get("from_account_id")
    to_account_id = payload.get("to_account_id")
    amount = payload.get("amount")
    description = payload.get("description", "")
    scheduled_date = payload.get("scheduled_date")

    if not all([from_account_id, to_account_id, amount]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_account_id, to_account_id, and amount are required",
        )

    try:
        transfer_service = TransferService(db)
        result = await transfer_service.create_internal_transfer(
            company_id=company_id,
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            amount=float(amount),
            description=description,
            user_id=current_user.id,
            scheduled_date=datetime.fromisoformat(scheduled_date) if scheduled_date else None,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Internal transfer failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/transfers/ach", status_code=status.HTTP_201_CREATED)
async def create_ach_transfer(
    payload: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
) -> Dict[str, Any]:
    """Create an ACH transfer to an external bank account."""
    from app.services.transfer_service import TransferService

    from_account_id = payload.get("from_account_id")
    recipient_name = payload.get("recipient_name")
    recipient_routing_number = payload.get("recipient_routing_number")
    recipient_account_number = payload.get("recipient_account_number")
    recipient_account_type = payload.get("recipient_account_type", "checking")
    amount = payload.get("amount")
    description = payload.get("description", "")
    save_recipient = payload.get("save_recipient", False)
    recipient_id = payload.get("recipient_id")

    if not all([from_account_id, amount]) or (not recipient_id and not all([recipient_name, recipient_routing_number, recipient_account_number])):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_account_id, amount, and recipient details are required",
        )

    try:
        transfer_service = TransferService(db)
        result = await transfer_service.create_ach_transfer(
            company_id=company_id,
            from_account_id=from_account_id,
            recipient_name=recipient_name or "",
            recipient_routing_number=recipient_routing_number or "",
            recipient_account_number=recipient_account_number or "",
            recipient_account_type=recipient_account_type,
            amount=float(amount),
            description=description,
            user_id=current_user.id,
            save_recipient=save_recipient,
            recipient_id=recipient_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"ACH transfer failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/transfers/wire", status_code=status.HTTP_201_CREATED)
async def create_wire_transfer(
    payload: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
) -> Dict[str, Any]:
    """Create a wire transfer (domestic or international)."""
    from app.services.transfer_service import TransferService

    from_account_id = payload.get("from_account_id")
    recipient_name = payload.get("recipient_name")
    recipient_routing_number = payload.get("recipient_routing_number")
    recipient_account_number = payload.get("recipient_account_number")
    recipient_bank_name = payload.get("recipient_bank_name")
    amount = payload.get("amount")
    description = payload.get("description", "")
    wire_type = payload.get("wire_type", "domestic")
    recipient_swift_code = payload.get("recipient_swift_code")
    recipient_address = payload.get("recipient_address")

    if not all([from_account_id, recipient_name, recipient_routing_number, recipient_account_number, recipient_bank_name, amount]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All required wire transfer fields must be provided",
        )

    try:
        transfer_service = TransferService(db)
        result = await transfer_service.create_wire_transfer(
            company_id=company_id,
            from_account_id=from_account_id,
            recipient_name=recipient_name,
            recipient_routing_number=recipient_routing_number,
            recipient_account_number=recipient_account_number,
            recipient_bank_name=recipient_bank_name,
            amount=float(amount),
            description=description,
            user_id=current_user.id,
            wire_type=wire_type,
            recipient_swift_code=recipient_swift_code,
            recipient_address=recipient_address,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Wire transfer failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/transfers/history")
async def get_transfer_history(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Get transfer history for the company."""
    from app.services.transfer_service import TransferService

    transfer_service = TransferService(db)
    return await transfer_service.get_transfer_history(company_id, limit)


@router.get("/transfers/{transfer_id}")
async def get_transfer(
    transfer_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get details of a specific transfer."""
    result = await db.execute(
        text("""
        SELECT id, company_id, transfer_type, status, amount, fee_amount,
               description, recipient_name, from_account_id, to_account_id,
               created_at, processed_at, estimated_completion_date
        FROM banking_transfer
        WHERE id = :id AND company_id = :company_id
        """),
        {"id": transfer_id, "company_id": company_id}
    )
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer not found")

    return {
        "id": row[0],
        "company_id": row[1],
        "transfer_type": row[2],
        "status": row[3],
        "amount": float(row[4]) if row[4] else 0,
        "fee_amount": float(row[5]) if row[5] else 0,
        "description": row[6],
        "recipient_name": row[7],
        "from_account_id": row[8],
        "to_account_id": row[9],
        "created_at": row[10].isoformat() if row[10] else None,
        "processed_at": row[11].isoformat() if row[11] else None,
        "estimated_completion": row[12].isoformat() if row[12] else None,
    }


# =============================================================================
# Transaction Endpoints
# =============================================================================


@router.get("/transactions/{transaction_id}")
async def get_transaction(
    transaction_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get details of a specific transaction."""
    from app.models.banking import BankingTransaction, BankingAccount

    result = await db.execute(
        select(BankingTransaction).where(BankingTransaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    # Verify ownership
    acc_result = await db.execute(
        select(BankingAccount).where(
            BankingAccount.id == transaction.account_id,
            BankingAccount.company_id == company_id,
        )
    )
    if not acc_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return BankingTransactionResponse.model_validate(transaction).model_dump()


@router.get("/transactions")
async def list_all_transactions(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
    limit: int = 100,
    offset: int = 0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """List all transactions for the company across all accounts."""
    from app.models.banking import BankingTransaction, BankingAccount

    # Get all accounts for this company
    acc_result = await db.execute(
        select(BankingAccount.id).where(BankingAccount.company_id == company_id)
    )
    account_ids = [row[0] for row in acc_result.fetchall()]

    if not account_ids:
        return {"transactions": [], "total": 0}

    # Build query
    query = select(BankingTransaction).where(
        BankingTransaction.account_id.in_(account_ids)
    )

    if start_date:
        query = query.where(BankingTransaction.posted_at >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.where(BankingTransaction.posted_at <= datetime.fromisoformat(end_date))

    query = query.order_by(BankingTransaction.posted_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    transactions = result.scalars().all()

    # Get account names
    acc_name_result = await db.execute(
        select(BankingAccount).where(BankingAccount.id.in_(account_ids))
    )
    accounts_map = {a.id: a.nickname or a.account_type for a in acc_name_result.scalars().all()}

    return {
        "transactions": [
            {
                **BankingTransactionResponse.model_validate(t).model_dump(),
                "account_name": accounts_map.get(t.account_id, "Unknown"),
            }
            for t in transactions
        ],
        "total": len(transactions),
    }


# =============================================================================
# Check Deposit Endpoints
# =============================================================================


@router.post("/deposits/check", status_code=status.HTTP_201_CREATED)
async def create_check_deposit(
    payload: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
) -> Dict[str, Any]:
    """
    Create a mobile check deposit.

    Accepts front and back images of the check for processing.
    """
    from app.models.banking import BankingAccount

    account_id = payload.get("account_id")
    amount = payload.get("amount")
    check_number = payload.get("check_number")
    front_image_url = payload.get("front_image_url")
    back_image_url = payload.get("back_image_url")
    memo = payload.get("memo", "")

    if not all([account_id, amount, front_image_url, back_image_url]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="account_id, amount, front_image_url, and back_image_url are required",
        )

    # Verify account ownership
    acc_result = await db.execute(
        select(BankingAccount).where(
            BankingAccount.id == account_id,
            BankingAccount.company_id == company_id,
        )
    )
    account = acc_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    # Create check deposit record
    deposit_id = str(uuid.uuid4())
    now = datetime.utcnow()

    await db.execute(
        text("""
        INSERT INTO banking_check_deposit (
            id, company_id, account_id, amount, check_number,
            front_image_url, back_image_url, memo,
            status, initiated_by, created_at, updated_at
        ) VALUES (
            :id, :company_id, :account_id, :amount, :check_number,
            :front_image_url, :back_image_url, :memo,
            :status, :initiated_by, :now, :now
        )
        """),
        {
            "id": deposit_id,
            "company_id": company_id,
            "account_id": account_id,
            "amount": float(amount),
            "check_number": check_number,
            "front_image_url": front_image_url,
            "back_image_url": back_image_url,
            "memo": memo,
            "status": "pending",
            "initiated_by": current_user.id,
            "now": now,
        }
    )

    # Call Synctera to create check deposit (if configured)
    synctera = get_synctera_client()
    if synctera.is_configured and account.synctera_id:
        try:
            # Note: Synctera check deposit API would be called here
            # For now, we mark as pending review
            logger.info(f"Check deposit {deposit_id} created, pending Synctera processing")
        except SyncteraError as e:
            logger.error(f"Synctera check deposit failed: {e.message}")

    await db.commit()

    return {
        "deposit_id": deposit_id,
        "account_id": account_id,
        "amount": float(amount),
        "status": "pending",
        "message": "Check deposit submitted for review. Funds will be available within 1-3 business days.",
        "created_at": now.isoformat(),
    }


@router.get("/deposits/check")
async def list_check_deposits(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """List all check deposits for the company."""
    query = """
        SELECT id, account_id, amount, check_number, status,
               created_at, processed_at, rejection_reason
        FROM banking_check_deposit
        WHERE company_id = :company_id
    """
    params = {"company_id": company_id}

    if status_filter:
        query += " AND status = :status"
        params["status"] = status_filter

    query += " ORDER BY created_at DESC"

    result = await db.execute(text(query), params)
    deposits = []
    for row in result.fetchall():
        deposits.append({
            "id": row[0],
            "account_id": row[1],
            "amount": float(row[2]) if row[2] else 0,
            "check_number": row[3],
            "status": row[4],
            "created_at": row[5].isoformat() if row[5] else None,
            "processed_at": row[6].isoformat() if row[6] else None,
            "rejection_reason": row[7],
        })

    return {"deposits": deposits, "total": len(deposits)}


@router.get("/deposits/check/{deposit_id}")
async def get_check_deposit(
    deposit_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get details of a specific check deposit."""
    result = await db.execute(
        text("""
        SELECT id, account_id, amount, check_number, front_image_url,
               back_image_url, memo, status, processed_at, rejection_reason,
               created_at, updated_at
        FROM banking_check_deposit
        WHERE id = :id AND company_id = :company_id
        """),
        {"id": deposit_id, "company_id": company_id}
    )
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check deposit not found")

    return {
        "id": row[0],
        "account_id": row[1],
        "amount": float(row[2]) if row[2] else 0,
        "check_number": row[3],
        "front_image_url": row[4],
        "back_image_url": row[5],
        "memo": row[6],
        "status": row[7],
        "processed_at": row[8].isoformat() if row[8] else None,
        "rejection_reason": row[9],
        "created_at": row[10].isoformat() if row[10] else None,
        "updated_at": row[11].isoformat() if row[11] else None,
    }


# =============================================================================
# Fraud Detection & Reporting Endpoints
# =============================================================================


@router.post("/fraud/report", status_code=status.HTTP_201_CREATED)
async def report_fraud(
    payload: Dict[str, Any],
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
) -> Dict[str, Any]:
    """
    Report suspected fraudulent activity.

    This creates a fraud report and may trigger card suspension.
    """
    from app.models.banking import BankingAccount, BankingCard

    account_id = payload.get("account_id")
    card_id = payload.get("card_id")
    transaction_ids = payload.get("transaction_ids", [])
    fraud_type = payload.get("fraud_type")  # unauthorized, lost_card, stolen_card, counterfeit, other
    description = payload.get("description")
    suspend_card = payload.get("suspend_card", True)

    if not all([account_id, fraud_type]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="account_id and fraud_type are required",
        )

    # Verify account ownership
    acc_result = await db.execute(
        select(BankingAccount).where(
            BankingAccount.id == account_id,
            BankingAccount.company_id == company_id,
        )
    )
    account = acc_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    # Create fraud report
    report_id = str(uuid.uuid4())
    now = datetime.utcnow()

    await db.execute(
        text("""
        INSERT INTO banking_fraud_report (
            id, company_id, account_id, card_id, transaction_ids,
            fraud_type, description, status, reported_by,
            created_at, updated_at
        ) VALUES (
            :id, :company_id, :account_id, :card_id, :transaction_ids,
            :fraud_type, :description, :status, :reported_by,
            :now, :now
        )
        """),
        {
            "id": report_id,
            "company_id": company_id,
            "account_id": account_id,
            "card_id": card_id,
            "transaction_ids": str(transaction_ids),
            "fraud_type": fraud_type,
            "description": description,
            "status": "submitted",
            "reported_by": current_user.id,
            "now": now,
        }
    )

    # Suspend card if requested
    card_suspended = False
    if suspend_card and card_id:
        card_result = await db.execute(
            select(BankingCard).where(BankingCard.id == card_id)
        )
        card = card_result.scalar_one_or_none()
        if card:
            synctera = get_synctera_client()
            if synctera.is_configured and card.synctera_id:
                try:
                    await synctera.suspend_card(card.synctera_id, "FRAUD_REPORT")
                    card.status = "suspended"
                    card_suspended = True
                except SyncteraError as e:
                    logger.error(f"Failed to suspend card: {e.message}")
            else:
                card.status = "suspended"
                card_suspended = True

    await db.commit()

    return {
        "report_id": report_id,
        "account_id": account_id,
        "card_id": card_id,
        "fraud_type": fraud_type,
        "status": "submitted",
        "card_suspended": card_suspended,
        "message": "Fraud report submitted. Our team will review and contact you within 24 hours.",
        "created_at": now.isoformat(),
    }


@router.get("/fraud/reports")
async def list_fraud_reports(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """List all fraud reports for the company."""
    query = """
        SELECT id, account_id, card_id, fraud_type, status,
               created_at, resolved_at, resolution_notes
        FROM banking_fraud_report
        WHERE company_id = :company_id
    """
    params = {"company_id": company_id}

    if status_filter:
        query += " AND status = :status"
        params["status"] = status_filter

    query += " ORDER BY created_at DESC"

    result = await db.execute(text(query), params)
    reports = []
    for row in result.fetchall():
        reports.append({
            "id": row[0],
            "account_id": row[1],
            "card_id": row[2],
            "fraud_type": row[3],
            "status": row[4],
            "created_at": row[5].isoformat() if row[5] else None,
            "resolved_at": row[6].isoformat() if row[6] else None,
            "resolution_notes": row[7],
        })

    return {"reports": reports, "total": len(reports)}


@router.get("/fraud/reports/{report_id}")
async def get_fraud_report(
    report_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get details of a specific fraud report."""
    result = await db.execute(
        text("""
        SELECT id, account_id, card_id, transaction_ids, fraud_type,
               description, status, resolved_at, resolution_notes,
               created_at, updated_at
        FROM banking_fraud_report
        WHERE id = :id AND company_id = :company_id
        """),
        {"id": report_id, "company_id": company_id}
    )
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fraud report not found")

    return {
        "id": row[0],
        "account_id": row[1],
        "card_id": row[2],
        "transaction_ids": row[3],
        "fraud_type": row[4],
        "description": row[5],
        "status": row[6],
        "resolved_at": row[7].isoformat() if row[7] else None,
        "resolution_notes": row[8],
        "created_at": row[9].isoformat() if row[9] else None,
        "updated_at": row[10].isoformat() if row[10] else None,
    }


# =============================================================================
# KYB Verification Status Endpoint
# =============================================================================


@router.get("/kyb/status")
async def get_kyb_status(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get KYB verification status for the company."""
    from app.models.banking import BankingCustomer

    # Check for customer with KYB status
    result = await db.execute(
        select(BankingCustomer).where(BankingCustomer.company_id == company_id)
    )
    customer = result.scalar_one_or_none()

    # Also check applications
    app_result = await db.execute(
        select(BankingApplication)
        .where(BankingApplication.company_id == company_id)
        .order_by(BankingApplication.created_at.desc())
    )
    applications = app_result.scalars().all()
    latest_app = applications[0] if applications else None

    # Get Synctera verification status if configured
    synctera_status = None
    if customer and customer.synctera_business_id:
        synctera = get_synctera_client()
        if synctera.is_configured:
            try:
                synctera_status = await synctera.get_business_verification(customer.synctera_business_id)
            except SyncteraError as e:
                logger.error(f"Failed to get Synctera KYB status: {e.message}")

    return {
        "has_customer": customer is not None,
        "customer_id": customer.id if customer else None,
        "kyb_status": customer.kyb_status if customer else None,
        "synctera_business_id": customer.synctera_business_id if customer else None,
        "has_application": latest_app is not None,
        "application_id": latest_app.id if latest_app else None,
        "application_status": latest_app.status if latest_app else None,
        "kyc_status": latest_app.kyc_status if latest_app else None,
        "synctera_verification": synctera_status,
    }
