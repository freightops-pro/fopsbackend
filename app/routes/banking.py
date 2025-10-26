from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from uuid import UUID

from app.config.db import get_db
# ⛔ removed: from app.routes.user import verify_token, get_tenant_id
from app.schema.bankingSchema import (
    BankingCustomerCreate, BankingCustomerOut, BankingCustomerUpdate,
    BankingAccountCreate, BankingAccountOut, BankingAccountUpdate,
    BankingCardCreate, BankingCardOut, BankingCardUpdate,
    BankingTransactionOut, BankingTransferCreate, BankingTransferOut,
    BankingStatusOut, BankingCustomerListOut, BankingAccountListOut,
    BankingCardListOut, BankingTransactionListOut, BankingTransferListOut
)
from app.services.banking_service import banking_service

router = APIRouter(prefix="/api/banking", tags=["Banking"])

# -------------------------
# Customer Management
# -------------------------
@router.post("/customers", response_model=BankingCustomerOut, status_code=201)
async def create_customer(
    customer_data: BankingCustomerCreate,
    db: Session = Depends(get_db),
):
    try:
        customer = await banking_service.create_customer(db, customer_data)
        return customer
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/customers/{customer_id}", response_model=BankingCustomerOut)
async def get_customer(
    customer_id: UUID = Path(...),
    db: Session = Depends(get_db),
):
    customer = await banking_service.get_customer_by_id(db, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@router.get("/customers/company/{company_id}", response_model=BankingCustomerOut)
async def get_customer_by_company(
    company_id: UUID = Path(...),
    db: Session = Depends(get_db),
):
    customer = await banking_service.get_customer_by_company(db, company_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@router.put("/customers/{customer_id}", response_model=BankingCustomerOut)
async def update_customer(
    customer_id: UUID = Path(...),
    customer_data: BankingCustomerUpdate = None,
    db: Session = Depends(get_db),
):
    customer = await banking_service.update_customer(db, customer_id, customer_data)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

# -------------------------
# KYB Management
# -------------------------
@router.post("/customers/{customer_id}/kyb/submit")
async def submit_kyb_application(
    customer_id: UUID = Path(...),
    db: Session = Depends(get_db),
):
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"KYB submission requested for customer_id: {customer_id}")
    
    try:
        # First check if customer exists
        customer = await banking_service.get_customer_by_id(db, customer_id)
        if not customer:
            logger.error(f"Customer not found: {customer_id}")
            raise HTTPException(status_code=404, detail="Customer not found")
        
        logger.info(f"Customer found: {customer.legal_name}")
        
        # Submit KYB application
        success = await banking_service.submit_kyb_application(db, customer_id)
        if not success:
            logger.error(f"KYB submission failed for customer: {customer_id}")
            raise HTTPException(status_code=404, detail="Customer not found")
        
        logger.info(f"KYB application submitted successfully for customer: {customer_id}")
        return {"message": "KYB application submitted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting KYB application: {str(e)}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/customers/{customer_id}/kyb/status")
async def check_kyb_status(
    customer_id: UUID = Path(...),
    db: Session = Depends(get_db),
):
    try:
        status = await banking_service.check_kyb_status(db, customer_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# -------------------------
# Account Management
# -------------------------
@router.post("/accounts", response_model=BankingAccountOut, status_code=201)
async def create_account(
    account_data: BankingAccountCreate,
    db: Session = Depends(get_db),
):
    try:
        account = await banking_service.create_account(db, account_data)
        return account
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/accounts/{account_id}", response_model=BankingAccountOut)
async def get_account(
    account_id: UUID = Path(...),
    db: Session = Depends(get_db),
):
    account = await banking_service.get_account_by_id(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account

@router.get("/customers/{customer_id}/accounts", response_model=BankingAccountListOut)
async def get_customer_accounts(
    customer_id: UUID = Path(...),
    db: Session = Depends(get_db),
):
    accounts = await banking_service.get_accounts_by_customer(db, customer_id)
    return {"accounts": accounts, "total": len(accounts)}

@router.post("/accounts/{account_id}/balance/refresh")
async def refresh_account_balance(
    account_id: UUID = Path(...),
    db: Session = Depends(get_db),
):
    try:
        success = await banking_service.update_account_balance(db, account_id)
        if not success:
            raise HTTPException(status_code=404, detail="Account not found")
        return {"message": "Account balance updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# -------------------------
# Card Management
# -------------------------
@router.post("/cards", response_model=BankingCardOut, status_code=201)
async def create_card(
    card_data: BankingCardCreate,
    db: Session = Depends(get_db),
):
    try:
        card = await banking_service.create_card(db, card_data)
        return card
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/cards/{card_id}", response_model=BankingCardOut)
async def get_card(
    card_id: UUID = Path(...),
    db: Session = Depends(get_db),
):
    card = await banking_service.get_card_by_id(db, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card

@router.get("/accounts/{account_id}/cards", response_model=BankingCardListOut)
async def get_account_cards(
    account_id: UUID = Path(...),
    db: Session = Depends(get_db),
):
    cards = await banking_service.get_cards_by_account(db, account_id)
    return {"cards": cards, "total": len(cards)}

@router.put("/cards/{card_id}/status")
async def update_card_status(
    card_id: UUID = Path(...),
    status: str = Query(..., pattern="^(active|locked|expired|cancelled)$"),
    db: Session = Depends(get_db),
):
    try:
        success = await banking_service.update_card_status(db, card_id, status)
        if not success:
            raise HTTPException(status_code=404, detail="Card not found")
        return {"message": f"Card status updated to {status}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# -------------------------
# Banking Status
# -------------------------
@router.get("/status/{company_id}", response_model=BankingStatusOut)
async def get_banking_status(
    company_id: UUID = Path(...),
    db: Session = Depends(get_db),
):
    try:
        status = await banking_service.get_banking_status(db, company_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# -------------------------
# Activate Banking (combined)
# -------------------------
@router.post("/activate")
async def activate_banking(
    customer_data: BankingCustomerCreate,
    db: Session = Depends(get_db),
):
    try:
        customer = await banking_service.create_customer(db, customer_data)
        await banking_service.submit_kyb_application(db, customer.id)
        return {
            "message": "Banking activation initiated successfully",
            "customer_id": customer.id,
            "kyb_status": "submitted",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# -------------------------
# Application Status
# -------------------------
@router.get("/application-status/{company_id}")
async def get_application_status(
    company_id: UUID = Path(...),
    db: Session = Depends(get_db),
):
    try:
        customer = await banking_service.get_customer_by_company(db, company_id)
        if not customer:
            return {"hasApplication": False, "status": "not_started"}
        return {
            "hasApplication": True,
            "status": customer.kyb_status,
            "customer_id": customer.id,
            "submitted_at": customer.kyb_submitted_at,
            "approved_at": customer.kyb_approved_at,
            "rejection_reason": customer.kyb_rejection_reason,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/submit-application")
async def submit_application(
    customer_data: BankingCustomerCreate,
    db: Session = Depends(get_db),
):
    try:
        customer = await banking_service.create_customer(db, customer_data)
        await banking_service.submit_kyb_application(db, customer.id)
        return {
            "success": True,
            "message": "Application submitted successfully",
            "customer_id": customer.id,
            "kyb_status": "submitted",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# -------------------------
# Test Connection
# -------------------------
@router.get("/test-connection")
async def test_synctera_connection():
    """Test connection to Synctera API"""
    try:
        from app.services.synctera_service import synctera_service
        import httpx
        import logging
        
        logger = logging.getLogger(__name__)
        
        # First, let's check the API key format
        api_key = synctera_service.api_key
        base_url = synctera_service.base_url
        
        logger.info(f"API Key: {api_key[:8]}... (length: {len(api_key) if api_key else 0})")
        logger.info(f"Base URL: {base_url}")
        
        # Try to make a simple request to test connection
        test_url = f"{base_url}/persons"
        logger.info(f"Testing connection to: {test_url}")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(test_url, headers=headers, timeout=10.0)
            return {
                "success": True,
                "message": "Connection successful",
                "status_code": response.status_code,
                "url": test_url,
                "api_key_length": len(api_key) if api_key else 0,
                "api_key_prefix": api_key[:8] if api_key else "None"
            }
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
        return {
            "success": False,
            "message": f"Connection failed: {str(e)}",
            "error": str(e),
            "url": test_url if 'test_url' in locals() else "unknown",
            "api_key_length": len(api_key) if api_key else 0,
            "api_key_prefix": api_key[:8] if api_key else "None"
        }
