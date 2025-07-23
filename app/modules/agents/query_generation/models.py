"""
Models for the Query Generation Agent.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.modules.agents.synthesis.models import FieldPriority


class QueryGenerationRequest(BaseModel):
    """Request for query generation agent."""

    query: str = Field(..., description="Original user query")
    unified_interpretation: str = Field(..., description="Unified interpretation from synthesis")
    field_priorities: list[FieldPriority] = Field(..., description="Field priority rankings")
    target_collection: str = Field(default="master_search", description="Target MongoDB collection")


class QueryGenerationResponse(BaseModel):
    """Response from query generation agent."""

    mongodb_query: Any = Field(..., description="Generated MongoDB query")
    query_explanation: str = Field(..., description="Human-readable explanation of the query")
    estimated_results: int | None = Field(None, description="Estimated number of results")
