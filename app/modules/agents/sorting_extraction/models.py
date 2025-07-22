"""
Models for the Sorting Extraction Agent.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class SortingIntent(BaseModel):
    """Model for sorting intent extraction results."""
    has_sorting: bool = Field(..., description="Whether sorting is requested in the query")
    sort_field: Optional[str] = Field(None, description="Database field to sort by")
    sort_direction: str = Field(default="desc", description="Sort direction: 'asc' or 'desc'")
    confidence: float = Field(..., description="Confidence in the sorting extraction")
    reasoning: str = Field(..., description="Explanation of the sorting decision")
    sorting_phrase: Optional[str] = Field(None, description="The phrase that indicates sorting")


class SortingIntentRequest(BaseModel):
    """Request for sorting intent extraction."""
    query: str = Field(..., description="Natural language query from user")
    extracted_fields: List[str] = Field(default_factory=list, description="Fields already extracted from query")


class SortingIntentResponse(BaseModel):
    """Response from sorting intent extraction."""
    has_sorting: bool = Field(..., description="Whether sorting is requested in the query")
    sort_field: Optional[str] = Field(None, description="Database field to sort by")
    sort_direction: str = Field(default="desc", description="Sort direction: 'asc' or 'desc'")
    confidence: float = Field(..., description="Confidence in the sorting extraction")
    reasoning: str = Field(..., description="Explanation of the sorting decision")
    sorting_phrase: Optional[str] = Field(None, description="The phrase that indicates sorting")