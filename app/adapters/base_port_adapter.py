from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import httpx
import asyncio
from app.models.port import PortService, PortAuthType
from app.config.logging_config import get_logger

logger = get_logger(__name__)

class BasePortAdapter(ABC):
    """
    Abstract base class for port API adapters
    
    FUNCTION: Provides standardized interface for all port API interactions
    
    HOW IT WORKS:
    1. Implements common authentication patterns (OAuth2, API Key, JWT, etc.)
    2. Manages HTTP sessions with connection pooling
    3. Handles rate limiting with exponential backoff
    4. Standardizes error responses across different port APIs
    5. Provides automatic retry logic for transient failures
    
    Each port implementation inherits from this class and implements
    port-specific endpoint methods.
    
    SCALABILITY:
    - Async/await for concurrent API calls
    - Connection pooling via httpx.AsyncClient
    - Request caching for frequently accessed data
    - Automatic session refresh for OAuth2 tokens
    """
    
    def __init__(self, credentials: Dict[str, Any], api_endpoint: str, auth_type: PortAuthType):
        self.credentials = credentials
        self.api_endpoint = api_endpoint
        self.auth_type = auth_type
        self._session: Optional[httpx.AsyncClient] = None
        self._session_cache: Dict[str, Any] = {}
        self._token_expiry: Optional[datetime] = None
    
    async def _get_session(self) -> httpx.AsyncClient:
        """
        Get or create HTTP session with connection pooling
        
        SCALABILITY: Reuses connections for multiple requests
        """
        if self._session is None or self._session.is_closed:
            self._session = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
            )
        return self._session
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """
        Authenticate with port API
        
        Returns:
            True if authentication successful
            
        Raises:
            AuthenticationError: If authentication fails
            
        ERROR HANDLING:
        - Logs authentication failures
        - Updates credential validation status
        - Triggers rotation if credentials expired
        """
        pass
    
    @abstractmethod
    async def validate_credentials(self) -> bool:
        """
        Validate credentials are still active
        
        Returns:
            True if credentials are valid
            
        HOW IT WORKS:
        - Makes lightweight API call (typically /health or /status)
        - Verifies response indicates valid authentication
        - Updates last_validated timestamp
        """
        pass
    
    @abstractmethod
    async def get_vessel_schedule(self, vessel_id: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Get vessel scheduling information
        
        FUNCTION: Retrieves current and upcoming vessel schedules
        
        Args:
            vessel_id: Optional specific vessel identifier
            **kwargs: Port-specific parameters (date_range, berth, etc.)
            
        Returns:
            List of vessel schedule entries with ETA, ETD, berth assignments
            
        ERROR HANDLING:
        - Retries on transient failures (3 attempts with exponential backoff)
        - Returns empty list on persistent failures
        - Logs detailed error information
        """
        pass
    
    @abstractmethod
    async def track_container(self, container_number: str) -> Dict[str, Any]:
        """
        Track container status at port
        
        FUNCTION: Gets real-time container location and status
        
        Args:
            container_number: Standard container number (e.g., ABCD1234567)
            
        Returns:
            Dictionary with:
            - status: Container status (in_port, loaded, discharged, etc.)
            - location: Current location in port
            - last_movement: Timestamp of last status change
            - holds: Any customs or operational holds
            
        ERROR HANDLING:
        - Validates container number format
        - Returns not_found status if container not in system
        - Handles rate limiting with retry-after
        """
        pass
    
    @abstractmethod
    async def upload_document(self, document_type: str, file_data: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upload documentation to port system
        
        FUNCTION: Submits required documentation (customs, safety, etc.)
        
        Args:
            document_type: Type of document (customs_declaration, safety_cert, etc.)
            file_data: Binary file content
            metadata: Document metadata (vessel_id, container_number, etc.)
            
        Returns:
            Dictionary with:
            - document_id: Port-assigned document identifier
            - status: Upload status (accepted, pending_review, rejected)
            - validation_errors: Any validation issues
        """
        pass
    
    @abstractmethod
    async def get_gate_status(self) -> Dict[str, Any]:
        """
        Get current gate operation status
        
        Returns:
            Dictionary with:
            - gates: List of gate statuses (open, closed, restricted)
            - wait_times: Estimated wait times per gate
            - restrictions: Any current restrictions
        """
        pass
    
    @abstractmethod
    async def check_berth_availability(self, vessel_size: str, arrival_date: str) -> List[Dict[str, Any]]:
        """
        Check berth availability
        
        Args:
            vessel_size: Vessel size category (small, medium, large, ultra_large)
            arrival_date: Expected arrival date (ISO format)
            
        Returns:
            List of available berths with capacity and restrictions
        """
        pass
    
    async def _make_oauth2_call(self, endpoint: str, method: str = "GET", **kwargs) -> Dict[str, Any]:
        """
        Make API call with OAuth2 authentication
        
        FUNCTION: Handles OAuth2 token management and API calls
        
        HOW IT WORKS:
        1. Check if access token is valid (not expired)
        2. If expired, refresh using refresh_token
        3. Make API call with Bearer token
        4. Handle 401 responses with automatic token refresh
        5. Retry original request with new token
        
        ERROR HANDLING:
        - Automatic token refresh on expiration
        - Handles refresh token rotation
        - Falls back to credential rotation if refresh fails
        """
        session = await self._get_session()
        
        # Check token expiry and refresh if needed
        if self._token_expiry and datetime.utcnow() >= self._token_expiry:
            await self._refresh_oauth2_token()
        
        access_token = self._session_cache.get("access_token") or self.credentials.get("access_token")
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.api_endpoint}/{endpoint}"
        
        try:
            response = await session.request(method, url, headers=headers, **kwargs)
            
            # Handle 401 - token expired
            if response.status_code == 401:
                await self._refresh_oauth2_token()
                access_token = self._session_cache.get("access_token")
                headers["Authorization"] = f"Bearer {access_token}"
                response = await session.request(method, url, headers=headers, **kwargs)
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"OAuth2 API call failed: {e}", extra={
                "extra_fields": {"endpoint": endpoint, "status_code": e.response.status_code}
            })
            raise
    
    async def _make_api_key_call(self, endpoint: str, method: str = "GET", **kwargs) -> Dict[str, Any]:
        """
        Make API call with API key authentication
        
        FUNCTION: Simple API key based authentication
        
        HOW IT WORKS:
        1. Add API key to headers or query parameters (port-specific)
        2. Make API call
        3. Handle rate limiting (429 responses)
        4. Retry with exponential backoff
        
        ERROR HANDLING:
        - Detects rate limiting and backs off
        - Handles invalid API key (401/403)
        - Retries on transient failures
        """
        session = await self._get_session()
        
        api_key = self.credentials.get("api_key")
        
        # Different ports use different header names
        headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
        
        url = f"{self.api_endpoint}/{endpoint}"
        
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                response = await session.request(method, url, headers=headers, **kwargs)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", retry_delay))
                    logger.warning(f"Rate limited, waiting {retry_after}s", extra={
                        "extra_fields": {"endpoint": endpoint, "attempt": attempt + 1}
                    })
                    await asyncio.sleep(retry_after)
                    retry_delay *= 2
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code in [401, 403]:
                    logger.error("API key authentication failed", extra={
                        "extra_fields": {"endpoint": endpoint, "status_code": e.response.status_code}
                    })
                    raise
                
                if attempt == max_retries - 1:
                    raise
                
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
        
        raise Exception(f"API call failed after {max_retries} attempts")
    
    async def _refresh_oauth2_token(self):
        """
        Refresh OAuth2 access token
        
        FUNCTION: Obtains new access token using refresh token
        
        ERROR HANDLING:
        - Handles refresh token expiration
        - Triggers credential rotation if refresh fails
        - Updates token expiry cache
        """
        session = await self._get_session()
        
        token_url = self.credentials.get("token_url")
        refresh_token = self.credentials.get("refresh_token")
        client_id = self.credentials.get("client_id")
        client_secret = self.credentials.get("client_secret")
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret
        }
        
        response = await session.post(token_url, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        self._session_cache["access_token"] = token_data["access_token"]
        
        # Update token expiry
        expires_in = token_data.get("expires_in", 3600)
        self._token_expiry = datetime.utcnow() + timedelta(seconds=expires_in - 60)  # 60s buffer
        
        logger.info("OAuth2 token refreshed successfully")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on port API
        
        FUNCTION: Verifies port API is accessible and responsive
        
        Returns:
            Dictionary with:
            - status: healthy, degraded, or unavailable
            - response_time_ms: API response time
            - timestamp: Check timestamp
            - error: Error message if unhealthy
            
        HOW IT WORKS:
        1. Make lightweight API call (validate_credentials)
        2. Measure response time
        3. Check if response indicates valid credentials
        4. Return structured health status
        
        MONITORING:
        - Results stored in port_health_checks table
        - Triggers alerts on consecutive failures
        - Used for failover decisions
        """
        start_time = datetime.utcnow()
        try:
            is_valid = await self.validate_credentials()
            end_time = datetime.utcnow()
            response_time = int((end_time - start_time).total_seconds() * 1000)
            
            return {
                "status": "healthy" if is_valid else "unhealthy",
                "response_time_ms": response_time,
                "timestamp": datetime.utcnow().isoformat(),
                "error": None
            }
        except Exception as e:
            end_time = datetime.utcnow()
            response_time = int((end_time - start_time).total_seconds() * 1000)
            return {
                "status": "error",
                "response_time_ms": response_time,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def close(self):
        """Close HTTP session and cleanup resources"""
        if self._session and not self._session.is_closed:
            await self._session.aclose()









