"""
Models for the Field Extraction Agent.
"""

from typing import List
from pydantic import BaseModel, Field


class FieldExtractionRequest(BaseModel):
    """Request for field extraction agent."""
    query: str = Field(..., description="Natural language query from user")
    available_fields: List[str] = Field(..., description="List of available database fields")


class FieldExtractionResponse(BaseModel):
    """Response from field extraction agent."""
    relevant_fields: List[str] = Field(..., description="Fields identified as relevant to the query")
    confidence: float = Field(..., description="Confidence score for field extraction")
    reasoning: str = Field(..., description="Explanation of field selection")