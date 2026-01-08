"""Search schemas for global search functionality."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Individual search result."""

    id: str = Field(..., description="Entity ID")
    type: Literal["load", "driver", "equipment", "customer", "invoice"] = Field(
        ..., description="Type of entity"
    )
    title: str = Field(..., description="Main display text")
    subtitle: Optional[str] = Field(None, description="Secondary display text")
    link: str = Field(..., description="Frontend route to navigate to")
    score: float = Field(default=0.0, description="Relevance score")


class SearchResponse(BaseModel):
    """Search API response."""

    query: str = Field(..., description="Original search query")
    results: List[SearchResult] = Field(default_factory=list)
    total: int = Field(..., description="Total number of results")
    took_ms: int = Field(..., description="Time taken in milliseconds")
