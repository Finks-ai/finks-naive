"""
Models for the Synthesis Agent.
"""

from pydantic import BaseModel, Field


class FieldInterpretation(BaseModel):
    """Field interpretation pair."""

    field_name: str = Field(..., description="Name of the field")
    interpretation: str = Field(..., description="How the field should be interpreted")


class SynthesisRequest(BaseModel):
    """Request for synthesis agent."""

    query: str = Field(..., description="Original user query")
    field_interpretations: list[FieldInterpretation] = Field(
        ..., description="Field interpretations from instruction processing"
    )


class FieldPriority(BaseModel):
    """Field priority pair."""

    field_name: str = Field(..., description="Name of the field")
    priority: int = Field(..., description="Priority ranking (1=highest)")


class SynthesisResponse(BaseModel):
    """Response from synthesis agent."""

    unified_interpretation: str = Field(..., description="Unified interpretation of all fields")
    field_priorities: list[FieldPriority] = Field(..., description="Priority ranking of fields (1=highest)")
    conflicts_resolved: list[str] = Field(..., description="Description of any conflicts resolved")
