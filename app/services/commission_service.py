from sqlalchemy.orm import Session
from decimal import Decimal
from typing import List, Optional
from app.models.broker_commission import BrokerCommission
from app.models.load_board import LoadBoard
from app.models.simple_load import SimpleLoad
from app.schema.broker_commission import BrokerCommissionCreate, BrokerCommissionResponse
import logging

logger = logging.getLogger(__name__)

class CommissionService:
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_commission(self, load_value: Decimal, commission_percentage: Decimal) -> Decimal:
        """Calculate commission amount based on load value and percentage"""
        return load_value * (commission_percentage / Decimal('100'))
    
    def create_commission_record(
        self,
        load_id: str,
        broker_company_id: str,
        carrier_company_id: str,
        total_load_value: Decimal,
        commission_percentage: Decimal,
        notes: Optional[str] = None
    ) -> BrokerCommission:
        """Create a new commission record"""
        try:
            commission_amount = self.calculate_commission(total_load_value, commission_percentage)
            
            commission = BrokerCommission(
                load_id=load_id,
                broker_company_id=broker_company_id,
                carrier_company_id=carrier_company_id,
                total_load_value=total_load_value,
                commission_percentage=commission_percentage,
                commission_amount=commission_amount,
                notes=notes
            )
            
            self.db.add(commission)
            self.db.commit()
            self.db.refresh(commission)
            
            logger.info(f"Created commission record {commission.id} for load {load_id}")
            return commission
            
        except Exception as e:
            logger.error(f"Failed to create commission record: {str(e)}")
            self.db.rollback()
            raise
    
    def get_broker_commissions(
        self,
        broker_company_id: str,
        payment_status: Optional[str] = None
    ) -> List[BrokerCommission]:
        """Get all commissions for a broker company"""
        try:
            query = self.db.query(BrokerCommission).filter(
                BrokerCommission.broker_company_id == broker_company_id
            )
            
            if payment_status:
                query = query.filter(BrokerCommission.payment_status == payment_status)
            
            return query.all()
        except Exception as e:
            logger.error(f"Failed to fetch broker commissions: {str(e)}")
            raise
    
    def get_carrier_commissions(
        self,
        carrier_company_id: str,
        payment_status: Optional[str] = None
    ) -> List[BrokerCommission]:
        """Get all commissions for a carrier company (what they pay to brokers)"""
        try:
            query = self.db.query(BrokerCommission).filter(
                BrokerCommission.carrier_company_id == carrier_company_id
            )
            
            if payment_status:
                query = query.filter(BrokerCommission.payment_status == payment_status)
            
            return query.all()
        except Exception as e:
            logger.error(f"Failed to fetch carrier commissions: {str(e)}")
            raise
    
    def update_commission_payment_status(
        self,
        commission_id: str,
        payment_status: str,
        settlement_id: Optional[str] = None
    ) -> BrokerCommission:
        """Update commission payment status"""
        try:
            commission = self.db.query(BrokerCommission).filter(
                BrokerCommission.id == commission_id
            ).first()
            
            if not commission:
                raise ValueError("Commission not found")
            
            commission.payment_status = payment_status
            if settlement_id:
                commission.settlement_id = settlement_id
            
            if payment_status == "paid":
                from datetime import datetime
                commission.payment_date = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(commission)
            
            logger.info(f"Updated commission {commission_id} payment status to {payment_status}")
            return commission
            
        except Exception as e:
            logger.error(f"Failed to update commission payment status: {str(e)}")
            self.db.rollback()
            raise
    
    def process_load_completion_commission(
        self,
        load_board_id: str,
        final_load_value: Optional[Decimal] = None
    ) -> BrokerCommission:
        """Process commission when a load is completed"""
        try:
            # Get load board entry
            load_board = self.db.query(LoadBoard).filter(
                LoadBoard.id == load_board_id
            ).first()
            
            if not load_board:
                raise ValueError("Load board entry not found")
            
            # Get load details
            load = self.db.query(SimpleLoad).filter(
                SimpleLoad.id == load_board.load_id
            ).first()
            
            if not load:
                raise ValueError("Load not found")
            
            # Use final load value if provided, otherwise use posted rate
            total_value = final_load_value or load_board.posted_rate
            
            # Check if commission already exists
            existing_commission = self.db.query(BrokerCommission).filter(
                BrokerCommission.load_id == load_board.load_id
            ).first()
            
            if existing_commission:
                logger.info(f"Commission already exists for load {load_board.load_id}")
                return existing_commission
            
            # Create commission record
            commission = self.create_commission_record(
                load_id=load_board.load_id,
                broker_company_id=load_board.broker_company_id,
                carrier_company_id=load_board.carrier_company_id,
                total_load_value=total_value,
                commission_percentage=load_board.commission_percentage,
                notes=f"Commission for completed load {load.loadNumber}"
            )
            
            return commission
            
        except Exception as e:
            logger.error(f"Failed to process load completion commission: {str(e)}")
            raise
    
    def get_commission_summary(
        self,
        company_id: str,
        is_broker: bool = True
    ) -> dict:
        """Get commission summary for a company"""
        try:
            if is_broker:
                commissions = self.get_broker_commissions(company_id)
                total_earned = sum(c.commission_amount for c in commissions if c.payment_status == "paid")
                pending_amount = sum(c.commission_amount for c in commissions if c.payment_status == "pending")
            else:
                commissions = self.get_carrier_commissions(company_id)
                total_earned = sum(c.commission_amount for c in commissions if c.payment_status == "paid")
                pending_amount = sum(c.commission_amount for c in commissions if c.payment_status == "pending")
            
            return {
                "total_commissions": len(commissions),
                "total_earned": total_earned,
                "pending_amount": pending_amount,
                "paid_commissions": len([c for c in commissions if c.payment_status == "paid"]),
                "pending_commissions": len([c for c in commissions if c.payment_status == "pending"])
            }
            
        except Exception as e:
            logger.error(f"Failed to get commission summary: {str(e)}")
            raise
