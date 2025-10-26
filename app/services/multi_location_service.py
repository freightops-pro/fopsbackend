from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import logging

from app.models.multi_location import (
    Location, LocationUser, LocationEquipment, 
    LocationFinancials, InterLocationTransfer
)
from app.models.userModels import Users
from app.models.userModels import Truck
from app.schema.multi_location import (
    LocationCreate, LocationUpdate, LocationResponse,
    LocationUserCreate, LocationUserResponse,
    LocationEquipmentCreate, LocationEquipmentResponse,
    LocationFinancialsResponse, InterLocationTransferCreate,
    InterLocationTransferResponse
)
import logging
logger = logging.getLogger(__name__)


class MultiLocationService:
    """Service for managing multi-location operations"""
    
    def __init__(self, db: Session):
        self.db = db

    # Location Management
    
    async def create_location(
        self, 
        company_id: int, 
        location_data: LocationCreate
    ) -> Location:
        """Create a new location for the company"""
        
        # If this is the first location, make it primary
        existing_locations = self.db.query(Location).filter(
            Location.company_id == company_id,
            Location.is_active == True
        ).count()
        
        is_primary = existing_locations == 0 or location_data.is_primary
        
        # If setting as primary, unset other primary locations
        if is_primary:
            self.db.query(Location).filter(
                Location.company_id == company_id,
                Location.is_primary == True
            ).update({"is_primary": False})
        
        location = Location(
            company_id=company_id,
            name=location_data.name,
            location_type=location_data.location_type,
            address=location_data.address,
            city=location_data.city,
            state=location_data.state,
            zip_code=location_data.zip_code,
            country=location_data.country,
            phone=location_data.phone,
            email=location_data.email,
            contact_person=location_data.contact_person,
            is_primary=is_primary,
            timezone=location_data.timezone,
            capacity_trucks=location_data.capacity_trucks,
            capacity_trailers=location_data.capacity_trailers,
            has_fuel_island=location_data.has_fuel_island,
            has_scale=location_data.has_scale,
            has_shop=location_data.has_shop,
            has_office=location_data.has_office,
            latitude=location_data.latitude,
            longitude=location_data.longitude,
            notes=location_data.notes,
            operating_hours=location_data.operating_hours,
            facilities=location_data.facilities
        )
        
        self.db.add(location)
        self.db.commit()
        self.db.refresh(location)
        
        logger.info(f"Location '{location.name}' created for company {company_id}")
        return location

    async def get_locations(
        self, 
        company_id: int, 
        include_inactive: bool = False
    ) -> List[Location]:
        """Get all locations for a company"""
        
        query = self.db.query(Location).filter(Location.company_id == company_id)
        
        if not include_inactive:
            query = query.filter(Location.is_active == True)
        
        return query.order_by(Location.is_primary.desc(), Location.name).all()

    async def get_location(
        self, 
        location_id: int, 
        company_id: int
    ) -> Optional[Location]:
        """Get a specific location"""
        
        return self.db.query(Location).filter(
            and_(
                Location.id == location_id,
                Location.company_id == company_id
            )
        ).first()

    async def update_location(
        self, 
        location_id: int, 
        company_id: int, 
        location_data: LocationUpdate
    ) -> Location:
        """Update a location"""
        
        location = await self.get_location(location_id, company_id)
        if not location:
            raise ValueError("Location not found")
        
        # Handle primary location change
        if location_data.is_primary and not location.is_primary:
            # Unset other primary locations
            self.db.query(Location).filter(
                Location.company_id == company_id,
                Location.is_primary == True
            ).update({"is_primary": False})
        
        # Update location fields
        for field, value in location_data.dict(exclude_unset=True).items():
            setattr(location, field, value)
        
        location.updated_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(location)
        
        logger.info(f"Location '{location.name}' updated")
        return location

    async def delete_location(
        self, 
        location_id: int, 
        company_id: int
    ) -> bool:
        """Soft delete a location"""
        
        location = await self.get_location(location_id, company_id)
        if not location:
            raise ValueError("Location not found")
        
        # Check if location has active equipment or loads
        active_equipment = self.db.query(LocationEquipment).filter(
            LocationEquipment.location_id == location_id,
            LocationEquipment.is_active == True
        ).count()
        
        if active_equipment > 0:
            raise ValueError("Cannot delete location with active equipment assignments")
        
        # Soft delete
        location.is_active = False
        location.updated_at = datetime.now(timezone.utc)
        
        self.db.commit()
        
        logger.info(f"Location '{location.name}' deleted")
        return True

    # Location Users Management
    
    async def assign_user_to_location(
        self, 
        location_id: int, 
        user_id: int, 
        company_id: int,
        permissions: LocationUsersCreate
    ) -> LocationUsers:
        """Assign a user to a location with specific permissions"""
        
        # Verify location belongs to company
        location = await self.get_location(location_id, company_id)
        if not location:
            raise ValueError("Location not found")
        
        # Check for existing assignment
        existing = self.db.query(LocationUsers).filter(
            and_(
                LocationUsers.location_id == location_id,
                LocationUsers.user_id == user_id
            )
        ).first()
        
        if existing:
            # Update existing assignment
            for field, value in permissions.dict(exclude_unset=True).items():
                setattr(existing, field, value)
            existing.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        # Create new assignment
        location_user = LocationUsers(
            location_id=location_id,
            user_id=user_id,
            can_view=permissions.can_view,
            can_edit=permissions.can_edit,
            can_manage=permissions.can_manage,
            can_dispatch=permissions.can_dispatch,
            can_view_financials=permissions.can_view_financials,
            is_primary_location=permissions.is_primary_location
        )
        
        # If setting as primary, unset other primary locations for this user
        if permissions.is_primary_location:
            self.db.query(LocationUsers).filter(
                LocationUsers.user_id == user_id,
                LocationUsers.is_primary_location == True
            ).update({"is_primary_location": False})
        
        self.db.add(location_user)
        self.db.commit()
        self.db.refresh(location_user)
        
        logger.info(f"Users {user_id} assigned to location {location_id}")
        return location_user

    async def get_user_locations(
        self, 
        user_id: int, 
        company_id: int
    ) -> List[LocationUsers]:
        """Get all locations accessible by a user"""
        
        return self.db.query(LocationUsers).join(Location).filter(
            and_(
                LocationUsers.user_id == user_id,
                Location.company_id == company_id,
                Location.is_active == True
            )
        ).all()

    async def remove_user_from_location(
        self, 
        location_id: int, 
        user_id: int, 
        company_id: int
    ) -> bool:
        """Remove user access to a location"""
        
        location_user = self.db.query(LocationUsers).join(Location).filter(
            and_(
                LocationUsers.location_id == location_id,
                LocationUsers.user_id == user_id,
                Location.company_id == company_id
            )
        ).first()
        
        if not location_user:
            return False
        
        self.db.delete(location_user)
        self.db.commit()
        
        logger.info(f"Users {user_id} removed from location {location_id}")
        return True

    # Location Equipment Management
    
    async def assign_equipment_to_location(
        self, 
        location_id: int, 
        vehicle_id: int, 
        company_id: int,
        assignment_data: LocationEquipmentCreate
    ) -> LocationEquipment:
        """Assign equipment to a location"""
        
        # Verify location belongs to company
        location = await self.get_location(location_id, company_id)
        if not location:
            raise ValueError("Location not found")
        
        # Verify vehicle belongs to company
        vehicle = self.db.query(Truck).filter(
            and_(
                Truck.id == vehicle_id,
                Truck.company_id == company_id
            )
        ).first()
        
        if not vehicle:
            raise ValueError("Truck not found")
        
        # Check for existing active assignment
        existing = self.db.query(LocationEquipment).filter(
            and_(
                LocationEquipment.vehicle_id == vehicle_id,
                LocationEquipment.is_active == True
            )
        ).first()
        
        if existing:
            # Update existing assignment
            existing.location_id = location_id
            existing.assigned_at = datetime.now(timezone.utc)
            existing.status = assignment_data.status
            existing.notes = assignment_data.notes
            existing.updated_at = datetime.now(timezone.utc)
            
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        # Create new assignment
        equipment = LocationEquipment(
            location_id=location_id,
            vehicle_id=vehicle_id,
            assigned_by_id=assignment_data.assigned_by_id,
            status=assignment_data.status,
            notes=assignment_data.notes
        )
        
        self.db.add(equipment)
        self.db.commit()
        self.db.refresh(equipment)
        
        logger.info(f"Truck {vehicle_id} assigned to location {location_id}")
        return equipment

    async def get_location_equipment(
        self, 
        location_id: int, 
        company_id: int,
        include_inactive: bool = False
    ) -> List[LocationEquipment]:
        """Get all equipment assigned to a location"""
        
        query = self.db.query(LocationEquipment).join(Location).filter(
            and_(
                LocationEquipment.location_id == location_id,
                Location.company_id == company_id
            )
        )
        
        if not include_inactive:
            query = query.filter(LocationEquipment.is_active == True)
        
        return query.all()

    async def remove_equipment_from_location(
        self, 
        location_id: int, 
        vehicle_id: int, 
        company_id: int
    ) -> bool:
        """Remove equipment from location"""
        
        equipment = self.db.query(LocationEquipment).join(Location).filter(
            and_(
                LocationEquipment.location_id == location_id,
                LocationEquipment.vehicle_id == vehicle_id,
                Location.company_id == company_id,
                LocationEquipment.is_active == True
            )
        ).first()
        
        if not equipment:
            return False
        
        equipment.is_active = False
        equipment.updated_at = datetime.now(timezone.utc)
        
        self.db.commit()
        
        logger.info(f"Truck {vehicle_id} removed from location {location_id}")
        return True

    # Inter-Location Transfers
    
    async def create_transfer(
        self, 
        company_id: int, 
        transfer_data: InterLocationTransferCreate
    ) -> InterLocationTransfer:
        """Create an inter-location equipment transfer"""
        
        # Verify locations belong to company
        from_location = await self.get_location(transfer_data.from_location_id, company_id)
        to_location = await self.get_location(transfer_data.to_location_id, company_id)
        
        if not from_location or not to_location:
            raise ValueError("One or both locations not found")
        
        # Verify vehicle belongs to company
        vehicle = self.db.query(Truck).filter(
            and_(
                Truck.id == transfer_data.vehicle_id,
                Truck.company_id == company_id
            )
        ).first()
        
        if not vehicle:
            raise ValueError("Truck not found")
        
        # Create transfer
        transfer = InterLocationTransfer(
            company_id=company_id,
            from_location_id=transfer_data.from_location_id,
            to_location_id=transfer_data.to_location_id,
            vehicle_id=transfer_data.vehicle_id,
            transfer_date=transfer_data.transfer_date,
            scheduled_date=transfer_data.scheduled_date,
            driver_id=transfer_data.driver_id,
            requested_by_id=transfer_data.requested_by_id,
            approved_by_id=transfer_data.approved_by_id,
            reason=transfer_data.reason,
            notes=transfer_data.notes,
            estimated_cost=transfer_data.estimated_cost
        )
        
        self.db.add(transfer)
        self.db.commit()
        self.db.refresh(transfer)
        
        logger.info(f"Transfer created for vehicle {transfer_data.vehicle_id} from location {transfer_data.from_location_id} to {transfer_data.to_location_id}")
        return transfer

    async def get_transfers(
        self, 
        company_id: int,
        location_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[InterLocationTransfer]:
        """Get transfers for a company"""
        
        query = self.db.query(InterLocationTransfer).filter(
            InterLocationTransfer.company_id == company_id
        )
        
        if location_id:
            query = query.filter(
                or_(
                    InterLocationTransfer.from_location_id == location_id,
                    InterLocationTransfer.to_location_id == location_id
                )
            )
        
        if status:
            query = query.filter(InterLocationTransfer.status == status)
        
        return query.order_by(InterLocationTransfer.transfer_date.desc()).all()

    async def update_transfer_status(
        self, 
        transfer_id: int, 
        company_id: int,
        status: str,
        completed_date: Optional[datetime] = None
    ) -> InterLocationTransfer:
        """Update transfer status"""
        
        transfer = self.db.query(InterLocationTransfer).filter(
            and_(
                InterLocationTransfer.id == transfer_id[0],
                InterLocationTransfer.company_id == company_id
            )
        ).first()
        
        if not transfer:
            raise ValueError("Transfer not found")
        
        transfer.status = status
        
        if status == "completed" and completed_date:
            transfer.completed_date = completed_date
            
            # Update equipment location
            await self.assign_equipment_to_location(
                location_id=transfer.to_location_id,
                vehicle_id=transfer.vehicle_id,
                company_id=company_id,
                assignment_data=LocationEquipmentCreate(
                    status="assigned",
                    notes=f"Transferred from {transfer.from_location.name}"
                )
            )
        
        transfer.updated_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(transfer)
        
        logger.info(f"Transfer {transfer_id} status updated to {status}")
        return transfer

    # Location Financials
    
    async def get_location_financials(
        self, 
        location_id: int, 
        company_id: int,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> List[LocationFinancials]:
        """Get financial data for a location"""
        
        query = self.db.query(LocationFinancials).filter(
            LocationFinancials.location_id == location_id
        )
        
        if period_start:
            query = query.filter(LocationFinancials.period_start >= period_start)
        
        if period_end:
            query = query.filter(LocationFinancials.period_end <= period_end)
        
        return query.order_by(LocationFinancials.period_start.desc()).all()

    async def generate_location_financials(
        self, 
        location_id: int, 
        company_id: int,
        period_start: datetime,
        period_end: datetime
    ) -> LocationFinancials:
        """Generate financial metrics for a location period"""
        
        # Verify location belongs to company
        location = await self.get_location(location_id, company_id)
        if not location:
            raise ValueError("Location not found")
        
        # This would typically aggregate data from loads, expenses, etc.
        # For now, create a placeholder financial record
        financials = LocationFinancials(
            location_id=location_id,
            period_start=period_start,
            period_end=period_end,
            period_type="monthly"
        )
        
        self.db.add(financials)
        self.db.commit()
        self.db.refresh(financials)
        
        return financials

    # Analytics and Reporting
    
    async def get_location_analytics(
        self, 
        company_id: int,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Get analytics across all locations"""
        
        period_start = datetime.now(timezone.utc) - timedelta(days=period_days)
        
        # Get location counts
        total_locations = self.db.query(Location).filter(
            Location.company_id == company_id,
            Location.is_active == True
        ).count()
        
        # Get equipment distribution
        equipment_by_location = self.db.query(
            Location.name,
            func.count(LocationEquipment.id).label('equipment_count')
        ).join(LocationEquipment).filter(
            Location.company_id == company_id,
            LocationEquipment.is_active == True
        ).group_by(Location.name).all()
        
        # Get recent transfers
        recent_transfers = self.db.query(InterLocationTransfer).filter(
            InterLocationTransfer.company_id == company_id,
            InterLocationTransfer.transfer_date >= period_start
        ).count()
        
        return {
            "total_locations": total_locations,
            "equipment_by_location": [
                {"location": name, "count": count} 
                for name, count in equipment_by_location
            ],
            "recent_transfers": recent_transfers,
            "period_days": period_days
        }
