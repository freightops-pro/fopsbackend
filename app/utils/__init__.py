"""
Utility modules for FreightOps Pro backend.

This package contains reusable helper functions and utilities.
"""
from .tenant_helpers import (
    get_company_id_from_token,
    get_tenant_filtered_query,
    verify_resource_ownership,
    verify_multi_resource_ownership,
    get_user_id_from_token,
    validate_same_company
)
from .serializers import (
    serialize_load,
    serialize_load_list,
    serialize_load_billing,
    serialize_load_accessorial,
    serialize_load_accessorial_list,
    serialize_paginated_response,
    format_datetime
)

__all__ = [
    # Tenant helpers
    "get_company_id_from_token",
    "get_tenant_filtered_query",
    "verify_resource_ownership",
    "verify_multi_resource_ownership",
    "get_user_id_from_token",
    "validate_same_company",
    # Serializers
    "serialize_load",
    "serialize_load_list",
    "serialize_load_billing",
    "serialize_load_accessorial",
    "serialize_load_accessorial_list",
    "serialize_paginated_response",
    "format_datetime"
]

