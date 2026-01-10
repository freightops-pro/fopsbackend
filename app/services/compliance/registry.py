"""
Compliance Engine Registry

Central registry for all regional compliance engines.
Handles loading and retrieving the appropriate engine for a given region.
"""

from typing import Dict, Type, Optional
from .base import BaseComplianceEngine


class ComplianceEngineRegistry:
    """Registry for regional compliance engines."""

    _engines: Dict[str, Type[BaseComplianceEngine]] = {}

    @classmethod
    def register(cls, region_code: str, engine_class: Type[BaseComplianceEngine]):
        """
        Register a compliance engine for a region.

        Args:
            region_code: Region code (e.g., "brazil", "mexico", "eu", "usa")
            engine_class: Compliance engine class
        """
        cls._engines[region_code] = engine_class

    @classmethod
    def get_engine(cls, region_code: str) -> Optional[BaseComplianceEngine]:
        """
        Get compliance engine instance for a region.

        Args:
            region_code: Region code

        Returns:
            Compliance engine instance or None if not found
        """
        engine_class = cls._engines.get(region_code)
        if engine_class:
            return engine_class(region_code)
        return None

    @classmethod
    def get_all_regions(cls) -> list[str]:
        """Get list of all registered region codes."""
        return list(cls._engines.keys())

    @classmethod
    def is_registered(cls, region_code: str) -> bool:
        """Check if a region has a compliance engine registered."""
        return region_code in cls._engines
