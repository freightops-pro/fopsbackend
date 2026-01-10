"""
Compliance Engine Loader

Auto-loads and registers all regional compliance engines at startup.
"""

from .registry import ComplianceEngineRegistry
from .usa import USAComplianceEngine
from .brazil import BrazilComplianceEngine
from .mexico import MexicoComplianceEngine
from .canada import CanadaComplianceEngine
from .eu import EUComplianceEngine

# Import other engines as they're implemented
# from .india import IndiaComplianceEngine
# from .china import ChinaComplianceEngine
# from .japan import JapanComplianceEngine


def load_compliance_engines():
    """
    Register all available compliance engines.

    Called at application startup to make engines available via registry.
    """
    # North America
    ComplianceEngineRegistry.register("usa", USAComplianceEngine)
    ComplianceEngineRegistry.register("canada", CanadaComplianceEngine)
    ComplianceEngineRegistry.register("mexico", MexicoComplianceEngine)

    # South America
    ComplianceEngineRegistry.register("brazil", BrazilComplianceEngine)

    # Europe
    ComplianceEngineRegistry.register("eu", EUComplianceEngine)

    # Register other engines as implemented
    # ComplianceEngineRegistry.register("india", IndiaComplianceEngine)
    # ComplianceEngineRegistry.register("china", ChinaComplianceEngine)
    # ComplianceEngineRegistry.register("japan", JapanComplianceEngine)

    print(f"Loaded {len(ComplianceEngineRegistry.get_all_regions())} compliance engines")
