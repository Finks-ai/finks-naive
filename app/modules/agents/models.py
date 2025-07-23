"""
Agent models for the multi-agent query processing system.
Central location for all agent models.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field

# Import models from individual agents
from app.modules.agents.field_extraction.models import FieldExtractionRequest, FieldExtractionResponse
from app.modules.agents.instruction_processing.models import (
    FieldInterpretation,
    InstructionProcessingRequest,
    InstructionProcessingResponse,
)
from app.modules.agents.query_generation.models import QueryGenerationRequest, QueryGenerationResponse
from app.modules.agents.sorting_extraction.models import SortingIntent, SortingIntentRequest, SortingIntentResponse
from app.modules.agents.synthesis.models import FieldPriority, SynthesisRequest, SynthesisResponse


class PreviousQueryContext(BaseModel):
    """Context from a previous query for refinements."""

    query: str = Field(..., description="Previous query text")
    mongodb_query: dict[str, Any] = Field(..., description="Previous MongoDB query")
    field_priorities: list[FieldPriority] = Field(..., description="Previous field priorities")
    unified_interpretation: str = Field(..., description="Previous unified interpretation")
    sorting_intent: Optional["SortingIntentResponse"] = Field(None, description="Previous sorting intent")


class AgentPipelineRequest(BaseModel):
    """Complete pipeline request."""

    query: str = Field(
        ...,
        description="Natural language query from user",
        min_length=1,
        max_length=500,
        examples=[
            "Find cheap profitable stocks",
            "Show me large cap technology companies",
            "Find dividend paying stocks with low PE ratios",
            "Companies with high return on equity",
            "Undervalued stocks in the healthcare sector",
        ],
    )
    max_results: int = Field(default=10, description="Maximum number of results to return", ge=1, le=100)
    previous_context: PreviousQueryContext | None = Field(
        None, description="Previous query context for refinements (used for follow-up queries)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"query": "Find cheap profitable stocks", "max_results": 5},
                {"query": "Show me technology companies with high growth", "max_results": 10},
            ]
        }
    }


class AgentPipelineResponse(BaseModel):
    """Complete pipeline response."""

    results: list[dict[str, Any]] = Field(..., description="Query results from database")
    query_used: dict[str, Any] = Field(..., description="MongoDB query that was executed")
    processing_chain: dict[str, Any] = Field(..., description="Details of agent processing steps")
    total_results: int = Field(..., description="Total number of results found")
    processing_time_ms: float = Field(..., description="Total processing time in milliseconds")
    query_context: PreviousQueryContext = Field(..., description="Context for potential query refinements")


# Re-export all models for backward compatibility
__all__ = [
    "AgentPipelineRequest",
    "AgentPipelineResponse",
    "FieldExtractionRequest",
    "FieldExtractionResponse",
    "FieldInterpretation",
    "FieldPriority",
    "InstructionProcessingRequest",
    "InstructionProcessingResponse",
    "PreviousQueryContext",
    "QueryGenerationRequest",
    "QueryGenerationResponse",
    "SortingIntent",
    "SortingIntentRequest",
    "SortingIntentResponse",
    "SynthesisRequest",
    "SynthesisResponse",
]
