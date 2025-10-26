from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
import logging

from app.models.banking import (
    BankingCustomer, BankingAccount, BankingCard, 
    BankingTransaction, BankingTransfer
)
from app.schema.bankingSchema import (
    BankingCustomerCreate, BankingCustomerUpdate,
    BankingAccountCreate, BankingAccountUpdate,
    BankingCardCreate, BankingCardUpdate,
    BankingTransferCreate
)
from app.services.synctera_service import synctera_service

logger = logging.getLogger(__name__)

class BankingService:
    
    # Customer Management
    async def create_customer(self, db: Session, customer_data: BankingCustomerCreate) -> BankingCustomer:
        """Create a new banking customer"""
        try:
            # Create customer in database
            db_customer = BankingCustomer(
                company_id=customer_data.company_id,
                legal_name=customer_data.legal_name,
                ein=customer_data.ein,
                business_address=customer_data.business_address,
                business_city=customer_data.business_city,
                business_state=customer_data.business_state,
                business_zip_code=customer_data.business_zip_code,
                naics_code=customer_data.naics_code,
                website=customer_data.website,
                control_person_name=customer_data.control_person_name
            )
            
            db.add(db_customer)
            db.commit()
            db.refresh(db_customer)
            
            logger.info(f"Created banking customer: {db_customer.id}")
            return db_customer
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating banking customer: {str(e)}")
            raise
    
    async def get_customer_by_company(self, db: Session, company_id: UUID) -> Optional[BankingCustomer]:
        """Get customer by company ID"""
        return db.query(BankingCustomer).filter(
            BankingCustomer.company_id == company_id
        ).first()
    
    async def get_customer_by_id(self, db: Session, customer_id: UUID) -> Optional[BankingCustomer]:
        """Get customer by ID"""
        return db.query(BankingCustomer).filter(
            BankingCustomer.id == customer_id
        ).first()
    
    async def update_customer(self, db: Session, customer_id: UUID, customer_data: BankingCustomerUpdate) -> Optional[BankingCustomer]:
        """Update customer information"""
        try:
            db_customer = await self.get_customer_by_id(db, customer_id)
            if not db_customer:
                return None
            
            update_data = customer_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_customer, field, value)
            
            db_customer.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(db_customer)
            
            return db_customer
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating customer: {str(e)}")
            raise
    
    # KYB Management
    async def submit_kyb_application(self, db: Session, customer_id: UUID) -> bool:
        """Submit KYB application for customer"""
        try:
            logger.info(f"Starting KYB submission for customer: {customer_id}")
            
            db_customer = await self.get_customer_by_id(db, customer_id)
            if not db_customer:
                logger.error(f"Customer not found in database: {customer_id}")
                return False
            
            logger.info(f"Customer found: {db_customer.legal_name}")
            
            # Prepare business data for Synctera
            business_data = {
                "legal_name": db_customer.legal_name,
                "ein": db_customer.ein,
                "business_address": db_customer.business_address,
                "business_city": db_customer.business_city,
                "business_state": db_customer.business_state,
                "business_zip_code": db_customer.business_zip_code,
                "naics_code": db_customer.naics_code,
                "website": db_customer.website,
                "control_person_name": db_customer.control_person_name
            }
            
            logger.info(f"Business data prepared: {business_data}")
            
            # Create person in Synctera
            logger.info("Creating person in Synctera...")
            person_id = await synctera_service.create_person(business_data)
            logger.info(f"Person created with ID: {person_id}")
            
            # Create business in Synctera
            logger.info("Creating business in Synctera...")
            business_id = await synctera_service.create_business(business_data, person_id)
            logger.info(f"Business created with ID: {business_id}")
            
            # Submit KYB application
            logger.info("Submitting KYB application...")
            kyb_id = await synctera_service.submit_kyb_application(business_id, person_id)
            logger.info(f"KYB application submitted with ID: {kyb_id}")
            
            # Update customer with Synctera IDs
            db_customer.synctera_person_id = person_id
            db_customer.synctera_business_id = business_id
            db_customer.kyb_status = "submitted"
            db_customer.kyb_submitted_at = datetime.utcnow()
            
            db.commit()
            db.refresh(db_customer)
            
            logger.info(f"KYB application submitted successfully for customer: {customer_id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error submitting KYB application: {str(e)}")
            logger.error(f"Exception type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    async def check_kyb_status(self, db: Session, customer_id: UUID) -> Dict[str, Any]:
        """Check KYB status from Synctera"""
        try:
            db_customer = await self.get_customer_by_id(db, customer_id)
            if not db_customer or not db_customer.synctera_business_id:
                return {"status": "not_found"}
            
            kyb_status = await synctera_service.get_kyb_status(db_customer.synctera_business_id)
            
            # Update local status based on Synctera response
            if kyb_status.get("status") == "APPROVED":
                db_customer.kyb_status = "approved"
                db_customer.kyb_approved_at = datetime.utcnow()
            elif kyb_status.get("status") == "REJECTED":
                db_customer.kyb_status = "rejected"
                db_customer.kyb_rejection_reason = kyb_status.get("rejection_reason")
            
            db.commit()
            
            return kyb_status
            
        except Exception as e:
            logger.error(f"Error checking KYB status: {str(e)}")
            raise
    
    # Account Management
    async def create_account(self, db: Session, account_data: BankingAccountCreate) -> BankingAccount:
        """Create a new bank account"""
        try:
            # Get customer to ensure they exist and have Synctera business ID
            db_customer = await self.get_customer_by_id(db, account_data.customer_id)
            if not db_customer or not db_customer.synctera_business_id:
                raise Exception("Customer not found or not verified with Synctera")
            
            # Create account in Synctera
            synctera_account_id = await synctera_service.create_account(
                db_customer.synctera_business_id, 
                account_data.account_type
            )
            
            # Create account in database
            db_account = BankingAccount(
                customer_id=account_data.customer_id,
                synctera_account_id=synctera_account_id,
                account_type=account_data.account_type,
                account_name=account_data.account_name
            )
            
            db.add(db_account)
            db.commit()
            db.refresh(db_account)
            
            logger.info(f"Created banking account: {db_account.id}")
            return db_account
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating account: {str(e)}")
            raise
    
    async def get_account_by_id(self, db: Session, account_id: UUID) -> Optional[BankingAccount]:
        """Get account by ID"""
        return db.query(BankingAccount).filter(
            BankingAccount.id == account_id
        ).first()
    
    async def get_accounts_by_customer(self, db: Session, customer_id: UUID) -> List[BankingAccount]:
        """Get all accounts for a customer"""
        return db.query(BankingAccount).filter(
            BankingAccount.customer_id == customer_id
        ).all()
    
    async def update_account_balance(self, db: Session, account_id: UUID) -> bool:
        """Update account balance from Synctera"""
        try:
            db_account = await self.get_account_by_id(db, account_id)
            if not db_account or not db_account.synctera_account_id:
                return False
            
            # Get balance from Synctera
            balance_data = await synctera_service.get_account_balance(db_account.synctera_account_id)
            
            # Update local balance
            db_account.available_balance = balance_data.get("available_balance", 0) / 100
            db_account.current_balance = balance_data.get("current_balance", 0) / 100
            db_account.pending_balance = balance_data.get("pending_balance", 0) / 100
            
            db.commit()
            db.refresh(db_account)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating account balance: {str(e)}")
            raise
    
    # Card Management
    async def create_card(self, db: Session, card_data: BankingCardCreate) -> BankingCard:
        """Create a new card"""
        try:
            # Get account to ensure it exists
            db_account = await self.get_account_by_id(db, card_data.account_id)
            if not db_account or not db_account.synctera_account_id:
                raise Exception("Account not found or not synced with Synctera")
            
            # Create card in Synctera
            synctera_card_id = await synctera_service.create_card(
                db_account.synctera_account_id,
                card_data.card_type
            )
            
            # Get card details from Synctera
            card_details = await synctera_service.get_card_details(synctera_card_id)
            
            # Create card in database
            db_card = BankingCard(
                account_id=card_data.account_id,
                synctera_card_id=synctera_card_id,
                card_type=card_data.card_type,
                card_number=card_details.get("card_number"),  # Will be masked
                last_four=card_details.get("last_four"),
                expiry_date=card_details.get("expiry_date"),
                card_name=card_data.card_name,
                assigned_to=card_data.assigned_to,
                daily_limit=card_data.daily_limit,
                monthly_limit=card_data.monthly_limit,
                restrictions=card_data.restrictions
            )
            
            db.add(db_card)
            db.commit()
            db.refresh(db_card)
            
            logger.info(f"Created banking card: {db_card.id}")
            return db_card
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating card: {str(e)}")
            raise
    
    async def get_card_by_id(self, db: Session, card_id: UUID) -> Optional[BankingCard]:
        """Get card by ID"""
        return db.query(BankingCard).filter(
            BankingCard.id == card_id
        ).first()
    
    async def get_cards_by_account(self, db: Session, account_id: UUID) -> List[BankingCard]:
        """Get all cards for an account"""
        return db.query(BankingCard).filter(
            BankingCard.account_id == account_id
        ).all()
    
    async def update_card_status(self, db: Session, card_id: UUID, status: str) -> bool:
        """Update card status"""
        try:
            db_card = await self.get_card_by_id(db, card_id)
            if not db_card or not db_card.synctera_card_id:
                return False
            
            # Update status in Synctera
            await synctera_service.update_card_status(db_card.synctera_card_id, status)
            
            # Update local status
            db_card.status = status
            db_card.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(db_card)
            
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating card status: {str(e)}")
            raise
    
    # Banking Status
    async def get_banking_status(self, db: Session, company_id: UUID) -> Dict[str, Any]:
        """Get overall banking status for a company"""
        try:
            customer = await self.get_customer_by_company(db, company_id)
            if not customer:
                return {
                    "has_customer": False,
                    "has_kyb": False,
                    "kyb_status": None,
                    "has_accounts": False,
                    "has_cards": False,
                    "total_balance": 0.0,
                    "account_count": 0,
                    "card_count": 0
                }
            
            accounts = await self.get_accounts_by_customer(db, customer.id)
            total_balance = sum(acc.available_balance for acc in accounts)
            
            card_count = 0
            for account in accounts:
                cards = await self.get_cards_by_account(db, account.id)
                card_count += len(cards)
            
            return {
                "has_customer": True,
                "has_kyb": customer.kyb_status in ["approved", "submitted"],
                "kyb_status": customer.kyb_status,
                "has_accounts": len(accounts) > 0,
                "has_cards": card_count > 0,
                "total_balance": total_balance,
                "account_count": len(accounts),
                "card_count": card_count
            }
            
        except Exception as e:
            logger.error(f"Error getting banking status: {str(e)}")
            raise

# Global instance
banking_service = BankingService()

