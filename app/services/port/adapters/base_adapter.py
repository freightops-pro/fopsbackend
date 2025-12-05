from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from app.schemas.port import (
    ContainerCharges,
    ContainerDates,
    ContainerDetails,
    ContainerLocation,
    ContainerTrackingResponse,
    VesselInfo,
)


class PortAdapter(ABC):
    """Abstract base class for port adapters."""

    def __init__(self, credentials: Optional[dict] = None, config: Optional[dict] = None):
        """
        Initialize adapter with credentials and configuration.
        
        Args:
            credentials: Port API credentials (API keys, tokens, etc.)
            config: Adapter-specific configuration
        """
        self.credentials = credentials or {}
        self.config = config or {}

    @abstractmethod
    async def track_container(self, container_number: str, port_code: str) -> ContainerTrackingResponse:
        """
        Track a container and return current status.
        
        Args:
            container_number: Container number to track
            port_code: Port code (UN/LOCODE format)
            
        Returns:
            ContainerTrackingResponse with current container status
            
        Raises:
            PortAdapterError: If tracking fails
        """
        pass

    @abstractmethod
    async def get_container_events(
        self, container_number: str, port_code: str, since: Optional[datetime] = None
    ) -> list[dict]:
        """
        Get container event history.
        
        Args:
            container_number: Container number
            port_code: Port code
            since: Optional datetime to get events since
            
        Returns:
            List of event dictionaries with event_type, timestamp, location, etc.
        """
        pass

    @abstractmethod
    async def get_vessel_schedule(self, vessel_name: Optional[str] = None, port_code: Optional[str] = None) -> list[dict]:
        """
        Get vessel schedule information.
        
        Args:
            vessel_name: Optional vessel name filter
            port_code: Optional port code filter
            
        Returns:
            List of vessel schedule dictionaries
        """
        pass

    def normalize_tracking_response(
        self,
        container_number: str,
        port_code: str,
        status: str,
        location: Optional[ContainerLocation] = None,
        vessel: Optional[VesselInfo] = None,
        dates: Optional[ContainerDates] = None,
        container_details: Optional[ContainerDetails] = None,
        holds: Optional[list[str]] = None,
        charges: Optional[ContainerCharges] = None,
        terminal: Optional[str] = None,
        raw_data: Optional[dict] = None,
    ) -> ContainerTrackingResponse:
        """
        Normalize adapter-specific data to unified ContainerTrackingResponse format.
        
        This is a helper method that adapters can use to create standardized responses.
        """
        return ContainerTrackingResponse(
            container_number=container_number,
            port_code=port_code,
            terminal=terminal,
            status=status,
            location=location,
            vessel=vessel,
            dates=dates,
            container_details=container_details,
            holds=holds or [],
            charges=charges,
            last_updated_at=datetime.utcnow(),
        )

    async def test_connection(self) -> bool:
        """
        Test adapter connection and credentials.
        
        Returns:
            True if connection is successful, False otherwise
        """
        # Default implementation - override in subclasses
        return True


class PortAdapterError(Exception):
    """Base exception for port adapter errors."""

    pass


class PortAuthenticationError(PortAdapterError):
    """Raised when authentication fails."""

    pass


class PortRateLimitError(PortAdapterError):
    """Raised when rate limit is exceeded."""

    pass


class PortNotFoundError(PortAdapterError):
    """Raised when container or resource is not found."""

    pass

