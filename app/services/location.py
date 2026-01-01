import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import Location
from app.schemas.location import LocationCreate, LocationUpdate


class LocationService:
    """Service for managing location address book entries."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_locations(
        self,
        company_id: str,
        location_type: Optional[str] = None
    ) -> List[Location]:
        """List all locations for a company, optionally filtered by type."""
        query = select(Location).where(Location.company_id == company_id)
        if location_type:
            query = query.where(Location.location_type == location_type)
        query = query.order_by(Location.business_name.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_location(self, company_id: str, location_id: str) -> Location:
        """Get a single location by ID."""
        result = await self.db.execute(
            select(Location).where(
                Location.company_id == company_id,
                Location.id == location_id
            )
        )
        location = result.scalar_one_or_none()
        if not location:
            raise ValueError("Location not found")
        return location

    async def create_location(self, company_id: str, payload: LocationCreate) -> Location:
        """Create a new location in the address book."""
        location = Location(
            id=str(uuid.uuid4()),
            company_id=company_id,
            business_name=payload.business_name,
            location_type=payload.location_type,
            address=payload.address,
            city=payload.city,
            state=payload.state,
            postal_code=payload.postal_code,
            country=payload.country,
            lat=payload.lat,
            lng=payload.lng,
            contact_name=payload.contact_name,
            contact_phone=payload.contact_phone,
            contact_email=payload.contact_email,
            special_instructions=payload.special_instructions,
            operating_hours=payload.operating_hours,
        )

        self.db.add(location)
        await self.db.commit()
        await self.db.refresh(location)
        return location

    async def update_location(
        self,
        company_id: str,
        location_id: str,
        payload: LocationUpdate
    ) -> Location:
        """Update an existing location."""
        location = await self.get_location(company_id, location_id)

        # Update fields if provided
        if payload.business_name is not None:
            location.business_name = payload.business_name
        if payload.location_type is not None:
            location.location_type = payload.location_type
        if payload.address is not None:
            location.address = payload.address
        if payload.city is not None:
            location.city = payload.city
        if payload.state is not None:
            location.state = payload.state
        if payload.postal_code is not None:
            location.postal_code = payload.postal_code
        if payload.country is not None:
            location.country = payload.country
        if payload.lat is not None:
            location.lat = payload.lat
        if payload.lng is not None:
            location.lng = payload.lng
        if payload.contact_name is not None:
            location.contact_name = payload.contact_name
        if payload.contact_phone is not None:
            location.contact_phone = payload.contact_phone
        if payload.contact_email is not None:
            location.contact_email = payload.contact_email
        if payload.special_instructions is not None:
            location.special_instructions = payload.special_instructions
        if payload.operating_hours is not None:
            location.operating_hours = payload.operating_hours

        await self.db.commit()
        await self.db.refresh(location)
        return location

    async def delete_location(self, company_id: str, location_id: str) -> None:
        """Delete a location from the address book."""
        location = await self.get_location(company_id, location_id)
        await self.db.delete(location)
        await self.db.commit()
