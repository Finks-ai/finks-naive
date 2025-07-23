"""
Sorting Extraction Service - Identifies sorting requirements from natural language queries.
"""

import json
from typing import Any

from loguru import logger

from app.core.retry import retry_on_ai_errors

from ..registry import AgentType, agent_registry
from .guidelines import DEFAULT_FIELD_MAPPINGS
from .models import SortingIntent
from .prompts import USER_PROMPT_TEMPLATE


class SortingExtractionService:
    """Service for extracting sorting requirements from queries."""

    def __init__(self) -> None:
        # Get or create the AI agent
        self.agent = agent_registry.get_ai_agent(AgentType.SORTING_EXTRACTION)

        # Use default field mappings for sorting
        self.field_mappings = DEFAULT_FIELD_MAPPINGS

    @retry_on_ai_errors(max_retries=3)
    async def extract_sorting_intent(self, query: str) -> SortingIntent:
        """Extract sorting intent from a natural language query."""
        try:
            logger.info(f"Extracting sorting intent from query: {query}")

            # Prepare prompt
            prompt = USER_PROMPT_TEMPLATE.format(
                query=query,
                available_fields=", ".join(set(self.field_mappings.values())),
                field_mappings=json.dumps(self.field_mappings, indent=2),
            )

            if not self.agent:
                raise ValueError("Sorting extraction agent not initialized")

            result = await self.agent.run(prompt)

            logger.info(
                f"Sorting intent extracted: has_sorting={result.data.has_sorting}, "  # type: ignore[attr-defined]
                f"field={result.data.sort_field}, direction={result.data.sort_direction}"  # type: ignore[attr-defined]
            )

            return result.data  # type: ignore[return-value]

        except Exception as e:
            logger.error(f"Error in sorting extraction: {e!s}")
            # Return no sorting on error
            return SortingIntent(
                has_sorting=False,
                sort_field=None,
                sorting_phrase=None,
                confidence=0.0,
                reasoning=f"Error during extraction: {e!s}",
            )

    def infer_sort_field_from_context(self, query: str, extracted_fields: list[str]) -> str | None:
        """Infer the sort field based on query context and extracted fields."""
        # If only one numeric field is extracted, it's likely the sort field
        numeric_fields = [
            f
            for f in extracted_fields
            if any(term in f for term in ["cap", "revenue", "income", "ratio", "yield", "price", "debt", "assets"])
        ]

        if len(numeric_fields) == 1:
            return numeric_fields[0]

        # Check for context clues
        query_lower = query.lower()

        # Default sorting contexts
        if "companies" in query_lower and "billion" in query_lower:
            return "market_cap"
        elif "profitable" in query_lower:
            return "ttm_net_income"
        elif "revenue" in query_lower or "sales" in query_lower:
            return "ttm_revenue"

        return None


# Singleton instance
sorting_extraction_service = SortingExtractionService()


# Step function for pipeline integration
async def extract_sorting_step(context: dict[str, Any]) -> SortingIntent:
    """Pipeline step function for sorting extraction."""
    query = context["request"].query
    logger.info("Extracting sorting intent")

    result = await sorting_extraction_service.extract_sorting_intent(query)

    logger.info(f"Sorting intent: has_sorting={result.has_sorting}, field={result.sort_field}")
    return result
