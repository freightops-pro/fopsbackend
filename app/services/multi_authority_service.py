"""
Multi-Authority Operations Service

Handles business logic for managing multiple operating authorities within a company.
Supports carrier, brokerage, NVOCC, and freight forwarder operations.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timezone
import logging

from app.models.multi_authority import (
    Authority, AuthorityUser, AuthorityFinancials, 
    AuthorityCustomer, AuthorityIntegration, AuthorityAuditLog
)
from app.models.userModels import Users, Companies
from app.schema.multi_authority import (
    AuthorityCreate, AuthorityUpdate, AuthorityResponse,
    AuthorityUserCreate, AuthorityUserUpdate, AuthorityUserResponse,
    AuthorityFinancialsCreate, AuthorityFinancialsResponse,
    AuthorityCustomerCreate, AuthorityCustomerResponse,
    AuthorityIntegrationCreate, AuthorityIntegrationResponse
)

logger = logging.getLogger(__name__)


class MultiAuthorityService:
    """Service for managing multi-authority operations"""
    
    def __init__(self, db: Session):
        self.db = db

    # Authority Management
    async def create_authority(
        self, 
        authority_data: AuthorityCreate, 
        company_id: str, 
        created_by_user_id: str
    ) -> AuthorityResponse:
        """Create a new operating authority"""
        try:
            # Validate company exists
            company = self.db.query(Companies).filter(Companies.id == company_id).first()
            if not company:
                raise ValueError(f"Company with ID {company_id} not found")

            # Check if this is the first authority (will be primary)
            existing_authorities = self.db.query(Authority).filter(
                Authority.company_id == company_id
            ).count()
            is_primary = existing_authorities == 0

            # Create authority
            authority = Authority(
                company_id=company_id,
                name=authority_data.name,
                authority_type=authority_data.authority_type,
                dot_mc_number=authority_data.dot_mc_number,
                fmc_number=authority_data.fmc_number,
                license_number=authority_data.license_number,
                is_active=True,
                is_primary=is_primary,
                effective_date=authority_data.effective_date,
                expiration_date=authority_data.expiration_date,
                contact_name=authority_data.contact_name,
                contact_phone=authority_data.contact_phone,
                contact_email=authority_data.contact_email,
                business_address=authority_data.business_address,
                settings=authority_data.settings,
                insurance_requirements=authority_data.insurance_requirements,
                compliance_requirements=authority_data.compliance_requirements,
                default_payment_terms=authority_data.default_payment_terms,
                default_currency=authority_data.default_currency,
                tax_id=authority_data.tax_id
            )

            self.db.add(authority)
            self.db.commit()
            self.db.refresh(authority)

            # Log the creation
            await self._log_authority_activity(
                authority_id=authority.id,
                user_id=created_by_user_id,
                action="create",
                change_summary=f"Created {authority_data.authority_type} authority: {authority_data.name}"
            )

            return AuthorityResponse.from_orm(authority)

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating authority: {str(e)}")
            raise

    async def get_authorities(self, company_id: int) -> List[AuthorityResponse]:
        """Get all authorities for a company"""
        try:
            authorities = self.db.query(Authority).filter(
                and_(
                    Authority.company_id == company_id,
                    Authority.is_active == True
                )
            ).order_by(Authority.is_primary.desc(), Authority.name).all()

            return [AuthorityResponse.from_orm(auth) for auth in authorities]

        except Exception as e:
            logger.error(f"Error fetching authorities: {str(e)}")
            raise

    async def get_authority(self, authority_id: int, company_id: int) -> Optional[AuthorityResponse]:
        """Get a specific authority"""
        try:
            authority = self.db.query(Authority).filter(
                and_(
                    Authority.id == authority_id,
                    Authority.company_id == company_id,
                    Authority.is_active == True
                )
            ).first()

            return AuthorityResponse.from_orm(authority) if authority else None

        except Exception as e:
            logger.error(f"Error fetching authority: {str(e)}")
            raise

    async def update_authority(
        self, 
        authority_id: int, 
        authority_data: AuthorityUpdate, 
        company_id: int, 
        updated_by_user_id: int
    ) -> Optional[AuthorityResponse]:
        """Update an authority"""
        try:
            authority = self.db.query(Authority).filter(
                and_(
                    Authority.id == authority_id,
                    Authority.company_id == company_id,
                    Authority.is_active == True
                )
            ).first()

            if not authority:
                return None

            # Store old values for audit
            old_values = {
                "name": authority.name,
                "authority_type": authority.authority_type,
                "dot_mc_number": authority.dot_mc_number,
                "is_active": authority.is_active
            }

            # Update fields
            update_data = authority_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(authority, field):
                    setattr(authority, field, value)

            authority.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(authority)

            # Log the update
            await self._log_authority_activity(
                authority_id=authority.id,
                user_id=updated_by_user_id,
                action="update",
                old_values=old_values,
                new_values=update_data,
                change_summary=f"Updated authority: {authority.name}"
            )

            return AuthorityResponse.from_orm(authority)

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating authority: {str(e)}")
            raise

    async def delete_authority(
        self, 
        authority_id: int, 
        company_id: int, 
        deleted_by_user_id: int
    ) -> bool:
        """Soft delete an authority"""
        try:
            authority = self.db.query(Authority).filter(
                and_(
                    Authority.id == authority_id,
                    Authority.company_id == company_id,
                    Authority.is_active == True
                )
            ).first()

            if not authority:
                return False

            # Don't allow deleting primary authority
            if authority.is_primary:
                raise ValueError("Cannot delete primary authority")

            # Soft delete
            authority.is_active = False
            authority.updated_at = datetime.now(timezone.utc)
            self.db.commit()

            # Log the deletion
            await self._log_authority_activity(
                authority_id=authority.id,
                user_id=deleted_by_user_id,
                action="delete",
                change_summary=f"Deleted authority: {authority.name}"
            )

            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting authority: {str(e)}")
            raise

    # Authority User Management
    async def assign_user_to_authority(
        self, 
        authority_id: int, 
        user_data: AuthorityUserCreate, 
        company_id: int, 
        assigned_by_user_id: int
    ) -> AuthorityUserResponse:
        """Assign a user to an authority with specific permissions"""
        try:
            # Validate authority exists and belongs to company
            authority = self.db.query(Authority).filter(
                and_(
                    Authority.id == authority_id,
                    Authority.company_id == company_id,
                    Authority.is_active == True
                )
            ).first()

            if not authority:
                raise ValueError(f"Authority with ID {authority_id} not found")

            # Validate user exists and belongs to company
            user = self.db.query(Users).filter(
                and_(
                    Users.id == user_data.user_id,
                    Users.company_id == company_id,
                    Users.is_active == True
                )
            ).first()

            if not user:
                raise ValueError(f"User with ID {user_data.user_id} not found")

            # Check if assignment already exists
            existing_assignment = self.db.query(AuthorityUser).filter(
                and_(
                    AuthorityUser.authority_id == authority_id,
                    AuthorityUser.user_id == user_data.user_id
                )
            ).first()

            if existing_assignment:
                # Update existing assignment
                existing_assignment.can_view = user_data.can_view
                existing_assignment.can_edit = user_data.can_edit
                existing_assignment.can_manage = user_data.can_manage
                existing_assignment.can_create_loads = user_data.can_create_loads
                existing_assignment.can_view_financials = user_data.can_view_financials
                existing_assignment.can_manage_customers = user_data.can_manage_customers
                existing_assignment.is_primary_authority = user_data.is_primary_authority
                existing_assignment.updated_at = datetime.now(timezone.utc)

                self.db.commit()
                self.db.refresh(existing_assignment)
                return AuthorityUserResponse.from_orm(existing_assignment)
            else:
                # Create new assignment
                authority_user = AuthorityUser(
                    authority_id=authority_id,
                    user_id=user_data.user_id,
                    can_view=user_data.can_view,
                    can_edit=user_data.can_edit,
                    can_manage=user_data.can_manage,
                    can_create_loads=user_data.can_create_loads,
                    can_view_financials=user_data.can_view_financials,
                    can_manage_customers=user_data.can_manage_customers,
                    is_primary_authority=user_data.is_primary_authority,
                    assigned_by_id=assigned_by_user_id
                )

                self.db.add(authority_user)
                self.db.commit()
                self.db.refresh(authority_user)

                return AuthorityUserResponse.from_orm(authority_user)

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error assigning user to authority: {str(e)}")
            raise

    async def get_user_authorities(self, user_id: int, company_id: int) -> List[AuthorityUserResponse]:
        """Get all authorities a user has access to"""
        try:
            authority_users = self.db.query(AuthorityUser).join(Authority).filter(
                and_(
                    AuthorityUser.user_id == user_id,
                    Authority.company_id == company_id,
                    Authority.is_active == True
                )
            ).all()

            return [AuthorityUserResponse.from_orm(au) for au in authority_users]

        except Exception as e:
            logger.error(f"Error fetching user authorities: {str(e)}")
            raise

    async def get_authority_users(self, authority_id: int, company_id: int) -> List[AuthorityUserResponse]:
        """Get all users assigned to an authority"""
        try:
            # Validate authority exists and belongs to company
            authority = self.db.query(Authority).filter(
                and_(
                    Authority.id == authority_id,
                    Authority.company_id == company_id,
                    Authority.is_active == True
                )
            ).first()

            if not authority:
                raise ValueError(f"Authority with ID {authority_id} not found")

            authority_users = self.db.query(AuthorityUser).filter(
                AuthorityUser.authority_id == authority_id
            ).all()

            return [AuthorityUserResponse.from_orm(au) for au in authority_users]

        except Exception as e:
            logger.error(f"Error fetching authority users: {str(e)}")
            raise

    # Authority Financials
    async def create_authority_financials(
        self, 
        authority_id: int, 
        financials_data: AuthorityFinancialsCreate, 
        company_id: int
    ) -> AuthorityFinancialsResponse:
        """Create financial metrics for an authority"""
        try:
            # Validate authority exists and belongs to company
            authority = self.db.query(Authority).filter(
                and_(
                    Authority.id == authority_id,
                    Authority.company_id == company_id,
                    Authority.is_active == True
                )
            ).first()

            if not authority:
                raise ValueError(f"Authority with ID {authority_id} not found")

            # Check if financials already exist for this period
            existing_financials = self.db.query(AuthorityFinancials).filter(
                and_(
                    AuthorityFinancials.authority_id == authority_id,
                    AuthorityFinancials.period_start == financials_data.period_start,
                    AuthorityFinancials.period_end == financials_data.period_end,
                    AuthorityFinancials.period_type == financials_data.period_type
                )
            ).first()

            if existing_financials:
                raise ValueError("Financial metrics already exist for this period")

            # Create financials
            financials = AuthorityFinancials(
                authority_id=authority_id,
                period_start=financials_data.period_start,
                period_end=financials_data.period_end,
                period_type=financials_data.period_type,
                total_revenue=financials_data.total_revenue,
                load_count=financials_data.load_count,
                average_rate=financials_data.average_rate,
                gross_revenue=financials_data.gross_revenue,
                carrier_payments=financials_data.carrier_payments,
                ocean_freight_costs=financials_data.ocean_freight_costs,
                port_charges=financials_data.port_charges,
                fuel_cost=financials_data.fuel_cost,
                maintenance_cost=financials_data.maintenance_cost,
                driver_pay=financials_data.driver_pay,
                overhead_cost=financials_data.overhead_cost,
                total_expenses=financials_data.total_expenses,
                gross_profit=financials_data.gross_profit,
                net_profit=financials_data.net_profit,
                profit_margin=financials_data.profit_margin,
                loads_managed=financials_data.loads_managed,
                customer_count=financials_data.customer_count
            )

            self.db.add(financials)
            self.db.commit()
            self.db.refresh(financials)

            return AuthorityFinancialsResponse.from_orm(financials)

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating authority financials: {str(e)}")
            raise

    async def get_authority_financials(
        self, 
        authority_id: int, 
        company_id: int,
        period_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[AuthorityFinancialsResponse]:
        """Get financial metrics for an authority"""
        try:
            # Validate authority exists and belongs to company
            authority = self.db.query(Authority).filter(
                and_(
                    Authority.id == authority_id,
                    Authority.company_id == company_id,
                    Authority.is_active == True
                )
            ).first()

            if not authority:
                raise ValueError(f"Authority with ID {authority_id} not found")

            # Build query
            query = self.db.query(AuthorityFinancials).filter(
                AuthorityFinancials.authority_id == authority_id
            )

            if period_type:
                query = query.filter(AuthorityFinancials.period_type == period_type)

            if start_date:
                query = query.filter(AuthorityFinancials.period_start >= start_date)

            if end_date:
                query = query.filter(AuthorityFinancials.period_end <= end_date)

            financials = query.order_by(AuthorityFinancials.period_start.desc()).all()

            return [AuthorityFinancialsResponse.from_orm(f) for f in financials]

        except Exception as e:
            logger.error(f"Error fetching authority financials: {str(e)}")
            raise

    # Authority Customer Management
    async def assign_customer_to_authority(
        self, 
        authority_id: int, 
        customer_data: AuthorityCustomerCreate, 
        company_id: int
    ) -> AuthorityCustomerResponse:
        """Assign a customer to an authority"""
        try:
            # Validate authority exists and belongs to company
            authority = self.db.query(Authority).filter(
                and_(
                    Authority.id == authority_id,
                    Authority.company_id == company_id,
                    Authority.is_active == True
                )
            ).first()

            if not authority:
                raise ValueError(f"Authority with ID {authority_id} not found")

            # Check if assignment already exists
            existing_assignment = self.db.query(AuthorityCustomer).filter(
                and_(
                    AuthorityCustomer.authority_id == authority_id,
                    AuthorityCustomer.customer_id == customer_data.customer_id
                )
            ).first()

            if existing_assignment:
                # Update existing assignment
                existing_assignment.is_primary = customer_data.is_primary
                existing_assignment.relationship_type = customer_data.relationship_type
                existing_assignment.payment_terms = customer_data.payment_terms
                existing_assignment.credit_limit = customer_data.credit_limit
                existing_assignment.special_instructions = customer_data.special_instructions
                existing_assignment.contract_start_date = customer_data.contract_start_date
                existing_assignment.contract_end_date = customer_data.contract_end_date
                existing_assignment.contract_terms = customer_data.contract_terms
                existing_assignment.updated_at = datetime.now(timezone.utc)

                self.db.commit()
                self.db.refresh(existing_assignment)
                return AuthorityCustomerResponse.from_orm(existing_assignment)
            else:
                # Create new assignment
                authority_customer = AuthorityCustomer(
                    authority_id=authority_id,
                    customer_id=customer_data.customer_id,
                    is_primary=customer_data.is_primary,
                    relationship_type=customer_data.relationship_type,
                    payment_terms=customer_data.payment_terms,
                    credit_limit=customer_data.credit_limit,
                    special_instructions=customer_data.special_instructions,
                    contract_start_date=customer_data.contract_start_date,
                    contract_end_date=customer_data.contract_end_date,
                    contract_terms=customer_data.contract_terms
                )

                self.db.add(authority_customer)
                self.db.commit()
                self.db.refresh(authority_customer)

                return AuthorityCustomerResponse.from_orm(authority_customer)

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error assigning customer to authority: {str(e)}")
            raise

    # Authority Integration Management
    async def create_authority_integration(
        self, 
        authority_id: int, 
        integration_data: AuthorityIntegrationCreate, 
        company_id: int
    ) -> AuthorityIntegrationResponse:
        """Create an integration for an authority"""
        try:
            # Validate authority exists and belongs to company
            authority = self.db.query(Authority).filter(
                and_(
                    Authority.id == authority_id,
                    Authority.company_id == company_id,
                    Authority.is_active == True
                )
            ).first()

            if not authority:
                raise ValueError(f"Authority with ID {authority_id} not found")

            # Check if integration already exists
            existing_integration = self.db.query(AuthorityIntegration).filter(
                and_(
                    AuthorityIntegration.authority_id == authority_id,
                    AuthorityIntegration.integration_type == integration_data.integration_type,
                    AuthorityIntegration.provider_name == integration_data.provider_name
                )
            ).first()

            if existing_integration:
                raise ValueError("Integration already exists for this authority and provider")

            # Create integration
            integration = AuthorityIntegration(
                authority_id=authority_id,
                integration_type=integration_data.integration_type,
                provider_name=integration_data.provider_name,
                provider_id=integration_data.provider_id,
                is_active=True,
                configuration=integration_data.configuration,
                credentials=integration_data.credentials,
                sync_frequency=integration_data.sync_frequency
            )

            self.db.add(integration)
            self.db.commit()
            self.db.refresh(integration)

            return AuthorityIntegrationResponse.from_orm(integration)

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating authority integration: {str(e)}")
            raise

    async def get_authority_integrations(
        self, 
        authority_id: int, 
        company_id: int
    ) -> List[AuthorityIntegrationResponse]:
        """Get all integrations for an authority"""
        try:
            # Validate authority exists and belongs to company
            authority = self.db.query(Authority).filter(
                and_(
                    Authority.id == authority_id,
                    Authority.company_id == company_id,
                    Authority.is_active == True
                )
            ).first()

            if not authority:
                raise ValueError(f"Authority with ID {authority_id} not found")

            integrations = self.db.query(AuthorityIntegration).filter(
                AuthorityIntegration.authority_id == authority_id
            ).all()

            return [AuthorityIntegrationResponse.from_orm(i) for i in integrations]

        except Exception as e:
            logger.error(f"Error fetching authority integrations: {str(e)}")
            raise

    # Authority Analytics
    async def get_authority_analytics(
        self, 
        authority_id: int, 
        company_id: int,
        period_type: str = "monthly",
        months_back: int = 12
    ) -> Dict[str, Any]:
        """Get comprehensive analytics for an authority"""
        try:
            # Validate authority exists and belongs to company
            authority = self.db.query(Authority).filter(
                and_(
                    Authority.id == authority_id,
                    Authority.company_id == company_id,
                    Authority.is_active == True
                )
            ).first()

            if not authority:
                raise ValueError(f"Authority with ID {authority_id} not found")

            # Get financial metrics
            financials = await self.get_authority_financials(
                authority_id=authority_id,
                company_id=company_id,
                period_type=period_type
            )

            # Get user count
            user_count = self.db.query(AuthorityUser).filter(
                AuthorityUser.authority_id == authority_id
            ).count()

            # Get customer count
            customer_count = self.db.query(AuthorityCustomer).filter(
                AuthorityCustomer.authority_id == authority_id
            ).count()

            # Get integration count
            integration_count = self.db.query(AuthorityIntegration).filter(
                and_(
                    AuthorityIntegration.authority_id == authority_id,
                    AuthorityIntegration.is_active == True
                )
            ).count()

            # Calculate trends
            total_revenue = sum(f.total_revenue for f in financials)
            total_expenses = sum(f.total_expenses for f in financials)
            total_profit = sum(f.net_profit for f in financials)
            total_loads = sum(f.load_count for f in financials)

            analytics = {
                "authority_info": {
                    "id": authority.id,
                    "name": authority.name,
                    "authority_type": authority.authority_type,
                    "is_primary": authority.is_primary
                },
                "metrics": {
                    "total_revenue": total_revenue,
                    "total_expenses": total_expenses,
                    "total_profit": total_profit,
                    "total_loads": total_loads,
                    "user_count": user_count,
                    "customer_count": customer_count,
                    "integration_count": integration_count
                },
                "financials": [f.dict() for f in financials],
                "period_type": period_type,
                "months_analyzed": len(financials)
            }

            return analytics

        except Exception as e:
            logger.error(f"Error generating authority analytics: {str(e)}")
            raise

    # Helper Methods
    async def _log_authority_activity(
        self,
        authority_id: int,
        user_id: int,
        action: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        change_summary: Optional[str] = None
    ):
        """Log authority-related activities"""
        try:
            audit_log = AuthorityAuditLog(
                authority_id=authority_id,
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                old_values=old_values,
                new_values=new_values,
                change_summary=change_summary
            )

            self.db.add(audit_log)
            self.db.commit()

        except Exception as e:
            logger.error(f"Error logging authority activity: {str(e)}")
            # Don't raise here as this is a helper method

    async def switch_user_authority(
        self, 
        user_id: int, 
        new_authority_id: int, 
        company_id: int
    ) -> bool:
        """Switch a user's primary authority"""
        try:
            # Validate new authority exists and belongs to company
            authority = self.db.query(Authority).filter(
                and_(
                    Authority.id == new_authority_id,
                    Authority.company_id == company_id,
                    Authority.is_active == True
                )
            ).first()

            if not authority:
                raise ValueError(f"Authority with ID {new_authority_id} not found")

            # Check if user has access to this authority
            authority_user = self.db.query(AuthorityUser).filter(
                and_(
                    AuthorityUser.user_id == user_id,
                    AuthorityUser.authority_id == new_authority_id
                )
            ).first()

            if not authority_user:
                raise ValueError("User does not have access to this authority")

            # Update all user's authorities to not be primary
            self.db.query(AuthorityUser).filter(
                AuthorityUser.user_id == user_id
            ).update({"is_primary_authority": False})

            # Set new primary authority
            authority_user.is_primary_authority = True
            authority_user.updated_at = datetime.now(timezone.utc)

            self.db.commit()

            # Log the switch
            await self._log_authority_activity(
                authority_id=new_authority_id,
                user_id=user_id,
                action="switch_primary_authority",
                change_summary=f"Switched primary authority to {authority.name}"
            )

            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error switching user authority: {str(e)}")
            raise
