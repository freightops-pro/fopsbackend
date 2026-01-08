"""Search router for global search functionality."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.search import SearchResponse
from app.services.search_service import SearchService

router = APIRouter()


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    """Dependency to get company ID."""
    return current_user["company_id"]


async def _service(db: AsyncSession = Depends(get_db)) -> SearchService:
    """Dependency to get search service."""
    return SearchService(db)


@router.get("/", response_model=SearchResponse)
async def global_search(
    q: Annotated[str, Query(min_length=1, max_length=100, description="Search query")],
    limit: Annotated[int, Query(ge=1, le=50, description="Max results")] = 20,
    company_id: str = Depends(_company_id),
    service: SearchService = Depends(_service),
) -> SearchResponse:
    """
    Global search across loads, drivers, equipment, customers.

    Searches multiple entity types and returns combined results sorted by relevance.

    **Query Parameters:**
    - **q**: Search query (min 1 char, max 100 chars)
    - **limit**: Maximum results to return (default 20, max 50)

    **Returns:**
    Combined search results with entity type, title, subtitle, and navigation link.
    """
    results, took_ms = await service.search(company_id, q, limit)

    return SearchResponse(
        query=q,
        results=results,
        total=len(results),
        took_ms=took_ms,
    )
