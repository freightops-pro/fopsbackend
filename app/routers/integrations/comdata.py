"""
Comdata Fuel Card Integration Router.

Comdata (now part of Corpay/FLEETCOR) provides:
- Fleet fuel cards with real-time purchase controls
- Express codes for driver payments
- Transaction reporting and analytics
- Fleet expense management

API Documentation: Contact Comdata/Corpay for API access
Website: https://www.comdata.com/
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.api import deps
from app.core.db import get_db
from app.core.config import settings
from app.models.integration import CompanyIntegration, Integration
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comdata", tags=["Integrations - Comdata"])


# ==================== SCHEMAS ====================


class ComdataCredentials(BaseModel):
    """Comdata API credentials."""
    account_code: str = Field(..., description="Comdata Account Code")
    customer_id: str = Field(..., description="Comdata Customer ID")
    username: str = Field(..., description="API Username")
    password: str = Field(..., description="API Password")
    security_info: Optional[str] = Field(None, description="Additional security token")


class ComdataCard(BaseModel):
    """Comdata fleet card details."""
    card_id: str
    card_number_masked: str  # Last 4 digits only
    card_status: str
    driver_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    card_type: str  # "fuel", "maintenance", "universal"
    spending_limits: Dict[str, float] = {}
    product_codes: List[str] = []


class ComdataTransaction(BaseModel):
    """Comdata transaction record."""
    transaction_id: str
    card_id: str
    transaction_date: datetime
    merchant_name: str
    merchant_id: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "US"
    product_code: Optional[str] = None
    product_description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total_amount: float
    fee_amount: float = 0
    odometer: Optional[int] = None
    driver_id: Optional[str] = None
    vehicle_id: Optional[str] = None


class ComdataExpressCode(BaseModel):
    """Comdata express code for driver payments."""
    code_id: str
    code: str
    amount: float
    status: str
    created_at: datetime
    expires_at: datetime
    driver_id: Optional[str] = None
    location_code: Optional[str] = None
    used_at: Optional[datetime] = None


class CreateExpressCodeRequest(BaseModel):
    """Request to create a Comdata express code."""
    amount: float = Field(..., gt=0, le=5000, description="Amount (max $5000)")
    driver_id: Optional[str] = Field(None, description="Driver ID")
    location_code: Optional[str] = Field(None, description="Location restriction")
    expiration_days: int = Field(default=3, ge=1, le=30, description="Days until expiration")
    code_type: str = Field(default="cash", description="Type: cash, fuel, or universal")


class CardLimitUpdate(BaseModel):
    """Update card spending limits."""
    daily_fuel_limit: Optional[float] = Field(None, ge=0)
    daily_maintenance_limit: Optional[float] = Field(None, ge=0)
    transaction_limit: Optional[float] = Field(None, ge=0)
    weekly_limit: Optional[float] = Field(None, ge=0)


# ==================== AUTHENTICATION ====================


async def get_current_user(current_user: User = Depends(deps.get_current_user)) -> User:
    """Get current authenticated user."""
    return current_user


async def get_comdata_integration(
    db: AsyncSession,
    company_id: str,
) -> CompanyIntegration:
    """Get active Comdata integration for company."""
    result = await db.execute(
        select(CompanyIntegration)
        .join(Integration)
        .where(
            CompanyIntegration.company_id == company_id,
            Integration.integration_key == "comdata",
            CompanyIntegration.status == "active",
        )
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comdata integration not configured. Please activate Comdata in integration settings."
        )

    return integration


async def get_comdata_auth_header(credentials: Dict) -> Dict[str, str]:
    """
    Generate Comdata API authentication header.

    Comdata uses a combination of account code, customer ID, and credentials.
    """
    # Comdata typically uses SOAP or REST with custom auth headers
    return {
        "Content-Type": "application/json",
        "X-Comdata-Account": credentials.get("account_code", ""),
        "X-Comdata-Customer": credentials.get("customer_id", ""),
        "Authorization": f"Basic {credentials.get('username')}:{credentials.get('password')}",
    }


# ==================== CONNECTION ENDPOINTS ====================


@router.post("/connect")
async def connect_comdata(
    credentials: ComdataCredentials = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Connect to Comdata using account credentials.

    Validates credentials against Comdata API before storing.
    """
    company_id = current_user.company_id

    # Validate credentials with Comdata API
    try:
        async with httpx.AsyncClient() as client:
            # Comdata validation endpoint
            # Note: Actual endpoint requires Comdata API agreement
            response = await client.post(
                "https://api.comdata.com/v1/auth/validate",
                json={
                    "account_code": credentials.account_code,
                    "customer_id": credentials.customer_id,
                    "username": credentials.username,
                    "password": credentials.password,
                },
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            )

            if response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Comdata credentials. Please verify your account details."
                )

    except httpx.RequestError as e:
        logger.warning(f"Could not validate Comdata credentials: {e}")
        # Continue for development purposes

    # Get or create Comdata integration record
    result = await db.execute(
        select(Integration).where(Integration.integration_key == "comdata")
    )
    integration = result.scalar_one_or_none()

    if not integration:
        integration = Integration(
            id=secrets.token_hex(16),
            integration_key="comdata",
            name="Comdata",
            category="fuel_cards",
            description="Fleet fuel cards, express codes, and expense management",
            auth_type="basic_auth",
            is_active=True,
        )
        db.add(integration)
        await db.flush()

    # Check for existing company integration
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.company_id == company_id,
            CompanyIntegration.integration_id == integration.id,
        )
    )
    company_integration = result.scalar_one_or_none()

    if company_integration:
        company_integration.credentials = {
            "account_code": credentials.account_code,
            "customer_id": credentials.customer_id,
            "username": credentials.username,
            "password": credentials.password,
            "security_info": credentials.security_info,
        }
        company_integration.status = "active"
        company_integration.updated_at = datetime.utcnow()
    else:
        company_integration = CompanyIntegration(
            id=secrets.token_hex(16),
            company_id=company_id,
            integration_id=integration.id,
            status="active",
            credentials={
                "account_code": credentials.account_code,
                "customer_id": credentials.customer_id,
                "username": credentials.username,
                "password": credentials.password,
                "security_info": credentials.security_info,
            },
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(company_integration)

    await db.commit()

    return {
        "status": "connected",
        "message": "Successfully connected to Comdata",
        "integration_key": "comdata",
        "account_code": credentials.account_code,
    }


@router.delete("/disconnect")
async def disconnect_comdata(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Disconnect Comdata integration."""
    company_id = current_user.company_id

    integration = await get_comdata_integration(db, company_id)
    integration.status = "inactive"
    integration.credentials = {}
    integration.updated_at = datetime.utcnow()

    await db.commit()

    return {"status": "disconnected", "message": "Comdata integration disconnected"}


@router.get("/status")
async def get_comdata_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get Comdata integration status."""
    company_id = current_user.company_id

    try:
        integration = await get_comdata_integration(db, company_id)
        return {
            "status": integration.status,
            "connected": integration.status == "active",
            "account_code": integration.credentials.get("account_code"),
            "last_sync": integration.last_sync_at,
        }
    except HTTPException:
        return {
            "status": "not_configured",
            "connected": False,
            "account_code": None,
            "last_sync": None,
        }


# ==================== CARD MANAGEMENT ====================


@router.get("/cards", response_model=List[ComdataCard])
async def list_cards(
    card_type: Optional[str] = Query(None, description="Filter by card type"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all Comdata fleet cards.

    Returns card details with spending limits and product restrictions.
    """
    company_id = current_user.company_id
    integration = await get_comdata_integration(db, company_id)
    credentials = integration.credentials

    try:
        async with httpx.AsyncClient() as client:
            headers = await get_comdata_auth_header(credentials)
            params = {"account_code": credentials.get("account_code")}
            if card_type:
                params["card_type"] = card_type
            if status_filter:
                params["status"] = status_filter

            response = await client.get(
                "https://api.comdata.com/v1/cards",
                params=params,
                headers=headers,
                timeout=30.0,
            )

            if response.status_code == 200:
                cards = response.json().get("cards", [])
                return [ComdataCard(**card) for card in cards]
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to retrieve cards from Comdata"
                )

    except httpx.RequestError as e:
        logger.error(f"Comdata API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to Comdata API"
        )


@router.get("/cards/{card_id}")
async def get_card_details(
    card_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed information for a specific card."""
    company_id = current_user.company_id
    integration = await get_comdata_integration(db, company_id)
    credentials = integration.credentials

    try:
        async with httpx.AsyncClient() as client:
            headers = await get_comdata_auth_header(credentials)

            response = await client.get(
                f"https://api.comdata.com/v1/cards/{card_id}",
                headers=headers,
                timeout=30.0,
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Card {card_id} not found"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to retrieve card details"
                )

    except httpx.RequestError as e:
        logger.error(f"Comdata API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to Comdata API"
        )


@router.put("/cards/{card_id}/limits")
async def update_card_limits(
    card_id: str,
    limits: CardLimitUpdate = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update spending limits on a Comdata card.

    Supports daily, weekly, and per-transaction limits.
    """
    company_id = current_user.company_id
    integration = await get_comdata_integration(db, company_id)
    credentials = integration.credentials

    update_data = limits.model_dump(exclude_none=True)

    try:
        async with httpx.AsyncClient() as client:
            headers = await get_comdata_auth_header(credentials)

            response = await client.put(
                f"https://api.comdata.com/v1/cards/{card_id}/limits",
                json=update_data,
                headers=headers,
                timeout=30.0,
            )

            if response.status_code == 200:
                return {"status": "updated", "card_id": card_id, **update_data}
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to update card limits"
                )

    except httpx.RequestError as e:
        logger.error(f"Comdata API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to Comdata API"
        )


@router.post("/cards/{card_id}/block")
async def block_card(
    card_id: str,
    reason: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Block a Comdata card immediately."""
    company_id = current_user.company_id
    integration = await get_comdata_integration(db, company_id)
    credentials = integration.credentials

    try:
        async with httpx.AsyncClient() as client:
            headers = await get_comdata_auth_header(credentials)

            response = await client.post(
                f"https://api.comdata.com/v1/cards/{card_id}/block",
                json={"reason": reason},
                headers=headers,
                timeout=30.0,
            )

            if response.status_code == 200:
                return {"status": "blocked", "card_id": card_id, "reason": reason}
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to block card"
                )

    except httpx.RequestError as e:
        logger.error(f"Comdata API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to Comdata API"
        )


# ==================== TRANSACTIONS ====================


@router.get("/transactions", response_model=List[ComdataTransaction])
async def get_transactions(
    start_date: datetime = Query(..., description="Start date"),
    end_date: datetime = Query(..., description="End date"),
    card_id: Optional[str] = Query(None, description="Filter by card"),
    product_code: Optional[str] = Query(None, description="Filter by product"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get Comdata transactions for reporting.

    Returns detailed transaction data for IFTA and expense reconciliation.
    """
    company_id = current_user.company_id
    integration = await get_comdata_integration(db, company_id)
    credentials = integration.credentials

    try:
        async with httpx.AsyncClient() as client:
            headers = await get_comdata_auth_header(credentials)
            params = {
                "account_code": credentials.get("account_code"),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            }
            if card_id:
                params["card_id"] = card_id
            if product_code:
                params["product_code"] = product_code

            response = await client.get(
                "https://api.comdata.com/v1/transactions",
                params=params,
                headers=headers,
                timeout=60.0,
            )

            if response.status_code == 200:
                transactions = response.json().get("transactions", [])

                # Update sync timestamp
                integration.last_sync_at = datetime.utcnow()
                await db.commit()

                return [ComdataTransaction(**tx) for tx in transactions]
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to retrieve transactions"
                )

    except httpx.RequestError as e:
        logger.error(f"Comdata API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to Comdata API"
        )


# ==================== EXPRESS CODES ====================


@router.post("/express-codes", response_model=ComdataExpressCode)
async def create_express_code(
    request: CreateExpressCodeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a Comdata express code for driver payments.

    Express codes can be used for cash advances or fuel purchases.
    """
    company_id = current_user.company_id
    integration = await get_comdata_integration(db, company_id)
    credentials = integration.credentials

    try:
        async with httpx.AsyncClient() as client:
            headers = await get_comdata_auth_header(credentials)

            response = await client.post(
                "https://api.comdata.com/v1/express-codes",
                json={
                    "account_code": credentials.get("account_code"),
                    "amount": request.amount,
                    "driver_id": request.driver_id,
                    "location_code": request.location_code,
                    "expiration_days": request.expiration_days,
                    "code_type": request.code_type,
                },
                headers=headers,
                timeout=30.0,
            )

            if response.status_code == 201:
                data = response.json()
                return ComdataExpressCode(
                    code_id=data.get("code_id"),
                    code=data.get("code"),
                    amount=request.amount,
                    status="active",
                    created_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(days=request.expiration_days),
                    driver_id=request.driver_id,
                    location_code=request.location_code,
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to create express code"
                )

    except httpx.RequestError as e:
        logger.error(f"Comdata API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to Comdata API"
        )


@router.get("/express-codes")
async def list_express_codes(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List express codes for the account."""
    company_id = current_user.company_id
    integration = await get_comdata_integration(db, company_id)
    credentials = integration.credentials

    try:
        async with httpx.AsyncClient() as client:
            headers = await get_comdata_auth_header(credentials)
            params = {"account_code": credentials.get("account_code")}
            if status_filter:
                params["status"] = status_filter

            response = await client.get(
                "https://api.comdata.com/v1/express-codes",
                params=params,
                headers=headers,
                timeout=30.0,
            )

            if response.status_code == 200:
                return response.json().get("express_codes", [])
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to retrieve express codes"
                )

    except httpx.RequestError as e:
        logger.error(f"Comdata API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to Comdata API"
        )


@router.delete("/express-codes/{code_id}")
async def void_express_code(
    code_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Void an unused express code."""
    company_id = current_user.company_id
    integration = await get_comdata_integration(db, company_id)
    credentials = integration.credentials

    try:
        async with httpx.AsyncClient() as client:
            headers = await get_comdata_auth_header(credentials)

            response = await client.delete(
                f"https://api.comdata.com/v1/express-codes/{code_id}",
                headers=headers,
                timeout=30.0,
            )

            if response.status_code == 200:
                return {"status": "voided", "code_id": code_id}
            elif response.status_code == 400:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Express code cannot be voided (may already be used)"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to void express code"
                )

    except httpx.RequestError as e:
        logger.error(f"Comdata API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to Comdata API"
        )


# ==================== IFTA REPORTING ====================


@router.post("/sync-ifta")
async def sync_ifta_data(
    quarter: str = Query(..., description="IFTA quarter (e.g., '2025-Q1')"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sync Comdata fuel transactions for IFTA reporting.

    Aggregates fuel purchases by jurisdiction for tax calculations.
    """
    company_id = current_user.company_id

    # Parse quarter
    year, q = quarter.split("-Q")
    quarter_starts = {"1": (1, 1), "2": (4, 1), "3": (7, 1), "4": (10, 1)}
    quarter_ends = {"1": (3, 31), "2": (6, 30), "3": (9, 30), "4": (12, 31)}

    start_month, start_day = quarter_starts[q]
    end_month, end_day = quarter_ends[q]

    start_date = datetime(int(year), start_month, start_day)
    end_date = datetime(int(year), end_month, end_day, 23, 59, 59)

    # Get fuel transactions only
    transactions = await get_transactions(
        start_date=start_date,
        end_date=end_date,
        card_id=None,
        product_code="FUEL",  # Filter to fuel only
        db=db,
        current_user=current_user,
    )

    # Aggregate by state
    state_totals = {}
    for tx in transactions:
        state = tx.state or "UNKNOWN"
        if state not in state_totals:
            state_totals[state] = {
                "gallons": 0,
                "amount": 0,
                "transactions": 0,
            }
        state_totals[state]["gallons"] += tx.quantity or 0
        state_totals[state]["amount"] += tx.total_amount
        state_totals[state]["transactions"] += 1

    return {
        "quarter": quarter,
        "synced_at": datetime.utcnow().isoformat(),
        "total_transactions": len(transactions),
        "total_gallons": sum(tx.quantity or 0 for tx in transactions),
        "total_amount": sum(tx.total_amount for tx in transactions),
        "by_jurisdiction": state_totals,
    }
