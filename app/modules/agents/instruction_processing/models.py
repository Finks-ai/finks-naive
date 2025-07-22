"""
Models for the Instruction Processing Agent.
"""

from typing import Dict, List
from pydantic import BaseModel, Field


class InstructionProcessingRequest(BaseModel):
    """Request for instruction processing."""
    query: str = Field(..., description="Original user query")
    relevant_fields: List[str] = Field(..., description="Fields identified by extraction agent")
    field_instructions: Dict[str, str] = Field(..., description="Field-specific instructions")


class FieldInterpretation(BaseModel):
    """Field interpretation pair."""
    field_name: str = Field(..., description="Name of the field")
    interpretation: str = Field(..., description="How the field should be interpreted")


class InstructionProcessingResponse(BaseModel):
    """Response from instruction processing."""
    field_interpretations: List[FieldInterpretation] = Field(..., description="How each field should be interpreted")
    processing_notes: str = Field(..., description="Notes about processing conflicts or decisions")