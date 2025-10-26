from typing import Dict, Any, Optional
from app.adapters.base_port_adapter import BasePortAdapter
from app.adapters.mock_port_adapter import MockPortAdapter
from app.adapters.port_of_los_angeles_adapter import PortOfLosAngelesAdapter
from app.adapters.port_of_long_beach_adapter import PortOfLongBeachAdapter
from app.adapters.port_of_new_york_adapter import PortOfNewYorkAdapter
from app.adapters.port_of_savannah_adapter import PortOfSavannahAdapter
from app.adapters.port_of_houston_adapter import PortOfHoustonAdapter
from app.models.port import Port, PortAuthType

class PortAdapterFactory:
    """
    Factory for creating port-specific adapters
    
    FUNCTION: Creates appropriate adapter instance based on port configuration
    
    HOW IT WORKS:
    1. Determines port type and capabilities
    2. Selects appropriate adapter implementation
    3. Configures adapter with port-specific settings
    4. Returns configured adapter instance
    
    SCALABILITY:
    - Easy to add new port implementations
    - Centralized adapter selection logic
    - Consistent interface across all ports
    """
    
    _adapter_registry = {
        # Mock adapter for development/testing
        "mock": MockPortAdapter,
        
        # Real port adapters
        "uslax": PortOfLosAngelesAdapter,
        "uslgb": PortOfLongBeachAdapter,
        "usnyc": PortOfNewYorkAdapter,
        "ussav": PortOfSavannahAdapter,
        "ushou": PortOfHoustonAdapter,
        
        # TODO: Add more port adapters as they're implemented
        # "usnor": PortOfNorfolkAdapter,
        # "uscha": PortOfCharlestonAdapter,
        # etc.
    }
    
    @classmethod
    def create_adapter(
        self,
        port: Port,
        credentials: Dict[str, Any],
        use_mock: bool = False
    ) -> BasePortAdapter:
        """
        Create port adapter instance
        
        Args:
            port: Port configuration from database
            credentials: Decrypted credentials for the port
            use_mock: Force use of mock adapter (for testing)
            
        Returns:
            Configured port adapter instance
            
        Raises:
            ValueError: If port type not supported
            AuthenticationError: If credentials invalid
        """
        
        # Use mock adapter if requested or in development
        if use_mock or port.port_code == "MOCK":
            return MockPortAdapter(
                credentials=credentials,
                api_endpoint=port.api_endpoint,
                auth_type=port.auth_type
            )
        
        # Get adapter class from registry
        adapter_class = self._adapter_registry.get(port.port_code.lower())
        
        if not adapter_class:
            # Default to mock adapter if specific adapter not available
            return MockPortAdapter(
                credentials=credentials,
                api_endpoint=port.api_endpoint,
                auth_type=port.auth_type
            )
        
        # Create and return adapter instance
        return adapter_class(
            credentials=credentials,
            api_endpoint=port.api_endpoint,
            auth_type=port.auth_type
        )
    
    @classmethod
    def register_adapter(cls, port_code: str, adapter_class: type):
        """
        Register new port adapter
        
        Args:
            port_code: Port code (e.g., "USLAX")
            adapter_class: Adapter class implementing BasePortAdapter
        """
        cls._adapter_registry[port_code.lower()] = adapter_class
    
    @classmethod
    def get_supported_ports(cls) -> list:
        """
        Get list of ports with custom adapters (not mock)
        
        Returns:
            List of port codes with dedicated adapters
        """
        return [code.upper() for code in cls._adapter_registry.keys() if code != "mock"]
    
    @classmethod
    def is_port_supported(cls, port_code: str) -> bool:
        """
        Check if port has dedicated adapter
        
        Args:
            port_code: Port code to check
            
        Returns:
            True if dedicated adapter available, False if using mock
        """
        return port_code.lower() in cls._adapter_registry and port_code.lower() != "mock"
