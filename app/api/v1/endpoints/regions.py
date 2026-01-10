"""
Regional Configuration Endpoints

Provides endpoints for retrieving region-specific requirements and configurations.
"""

from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.region_config import (
    OperatingRegion,
    RegionConfigService,
    RegionalField,
    RegionalRequirement,
)

router = APIRouter()


class RegionalFieldResponse(BaseModel):
    """Response model for regional field."""

    field_name: str
    label: str
    required: bool
    field_type: str
    description: str | None = None
    validation_pattern: str | None = None


class RegionalRequirementResponse(BaseModel):
    """Response model for regional requirement."""

    requirement_id: str
    name: str
    description: str
    category: str
    mandatory: bool


class RegionResponse(BaseModel):
    """Response model for region summary."""

    code: str
    name: str


class RegionConfigResponse(BaseModel):
    """Response model for full region configuration."""

    code: str
    name: str
    fields: List[RegionalFieldResponse]
    requirements: List[RegionalRequirementResponse]
    documents: List[str]
    currency: str
    distance_unit: str
    weight_unit: str


@router.get("/", response_model=List[RegionResponse])
async def get_all_regions() -> List[Dict[str, str]]:
    """
    Get list of all supported operating regions.

    Returns list of regions with code and name.
    """
    return RegionConfigService.get_all_regions()


@router.get("/{region_code}", response_model=RegionConfigResponse)
async def get_region_config(region_code: str) -> Dict[str, Any]:
    """
    Get full configuration for a specific region.

    Includes required fields, compliance requirements, document types,
    and regional settings (currency, units).
    """
    try:
        region = OperatingRegion(region_code)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Region '{region_code}' not found. Use /regions to see available regions."
        )

    config = RegionConfigService.get_config(region)

    if not config:
        raise HTTPException(
            status_code=404,
            detail=f"Configuration not found for region '{region_code}'"
        )

    # Convert RegionalField objects to dicts
    fields = []
    for field in config.get("fields", []):
        fields.append({
            "field_name": field.field_name,
            "label": field.label,
            "required": field.required,
            "field_type": field.field_type,
            "description": field.description,
            "validation_pattern": field.validation_pattern,
        })

    # Convert RegionalRequirement objects to dicts
    requirements = []
    for req in config.get("requirements", []):
        requirements.append({
            "requirement_id": req.requirement_id,
            "name": req.name,
            "description": req.description,
            "category": req.category,
            "mandatory": req.mandatory,
        })

    return {
        "code": region_code,
        "name": config.get("name", region_code),
        "fields": fields,
        "requirements": requirements,
        "documents": config.get("documents", []),
        "currency": config.get("currency", "USD"),
        "distance_unit": config.get("distance_unit", "miles"),
        "weight_unit": config.get("weight_unit", "lbs"),
    }


@router.get("/{region_code}/fields", response_model=List[RegionalFieldResponse])
async def get_region_fields(region_code: str) -> List[Dict[str, Any]]:
    """
    Get all fields for a specific region.

    Returns all region-specific fields (both required and optional).
    """
    try:
        region = OperatingRegion(region_code)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Region '{region_code}' not found"
        )

    fields = RegionConfigService.get_all_fields(region)

    return [
        {
            "field_name": field.field_name,
            "label": field.label,
            "required": field.required,
            "field_type": field.field_type,
            "description": field.description,
            "validation_pattern": field.validation_pattern,
        }
        for field in fields
    ]


@router.get("/{region_code}/requirements", response_model=List[RegionalRequirementResponse])
async def get_region_requirements(region_code: str) -> List[Dict[str, Any]]:
    """
    Get compliance requirements for a specific region.

    Returns mandatory and optional compliance requirements.
    """
    try:
        region = OperatingRegion(region_code)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Region '{region_code}' not found"
        )

    requirements = RegionConfigService.get_requirements(region)

    return [
        {
            "requirement_id": req.requirement_id,
            "name": req.name,
            "description": req.description,
            "category": req.category,
            "mandatory": req.mandatory,
        }
        for req in requirements
    ]
