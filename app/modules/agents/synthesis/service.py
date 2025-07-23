"""
Synthesis Service - Combines field interpretations and resolves conflicts.
"""

from typing import Any

from loguru import logger

from app.core.constants import US_EXCHANGES
from app.core.retry import retry_on_ai_errors

from ..registry import AgentType, agent_registry
from .models import FieldInterpretation, FieldPriority, SynthesisRequest, SynthesisResponse
from .prompts import REFINEMENT_PROMPT_TEMPLATE, USER_PROMPT_TEMPLATE


class SynthesisService:
    """Service for synthesizing field interpretations into unified query strategy."""

    def __init__(self) -> None:
        # Get or create the AI agent
        self.synthesis_agent = agent_registry.get_ai_agent(AgentType.SYNTHESIS)
        # Cache categorical values
        self._categorical_values: dict[str, dict[str, Any]] | None = None

    def _get_categorical_values(self) -> dict[str, dict[str, Any]]:
        """Get categorical values from registry with caching."""
        if self._categorical_values is None:
            self._categorical_values = agent_registry.get_categorical_values()
        return self._categorical_values

    def _validate_categorical_value(self, field_name: str, user_value: str) -> bool:
        """Validate if a categorical value is in the valid list."""
        categorical_values = self._get_categorical_values()

        if field_name not in categorical_values:
            return True  # Not a categorical field, so it's valid

        valid_values = categorical_values[field_name].get("values", [])
        if not valid_values:
            return True  # No valid values defined, so accept it

        # Handle format "field_name: value" by extracting just the value part
        actual_value = user_value.split(":", 1)[1].strip() if ":" in user_value else user_value

        # Check if the value is in the valid list (case-sensitive match)
        if isinstance(valid_values, list):
            return actual_value in valid_values
        return True  # If not a list, accept it

    def _validate_and_normalize_interpretations(
        self, interpretations: list[FieldInterpretation]
    ) -> tuple[list[FieldInterpretation], list[str]]:
        """Validate interpretations against categorical values."""
        validation_notes = []

        for interpretation in interpretations:
            field_name = interpretation.field_name
            field_value = interpretation.interpretation

            # Validate categorical fields
            if not self._validate_categorical_value(field_name, field_value):
                # Get valid values for error message
                categorical_values = self._get_categorical_values()
                valid_values = categorical_values[field_name].get("values", [])

                validation_notes.append(
                    f"Warning: {field_name}='{field_value}' is not a valid categorical value. "
                    f"Valid values: {', '.join(valid_values)}"
                )
                logger.warning(f"Invalid categorical value: {field_name}='{field_value}'")

        # Return original interpretations - let the AI agent's choice stand
        # but with validation warnings
        return interpretations, validation_notes

    @retry_on_ai_errors(max_retries=3)
    async def synthesize_interpretations(self, request: SynthesisRequest) -> SynthesisResponse:
        """Synthesize field interpretations into a unified strategy."""

        # Validate and normalize interpretations
        normalized_interpretations, validation_notes = self._validate_and_normalize_interpretations(
            request.field_interpretations
        )

        # Log validation notes
        for note in validation_notes:
            logger.info(f"Categorical validation: {note}")

        prompt = USER_PROMPT_TEMPLATE.format(
            query=request.query,
            field_interpretations=self._format_interpretations(normalized_interpretations),
            us_exchanges=", ".join(US_EXCHANGES),
        )

        # Run the agent
        if not self.synthesis_agent:
            raise ValueError("Synthesis agent not initialized")
        result = await self.synthesis_agent.run(prompt)

        # Add validation notes to conflicts resolved
        conflicts_resolved = result.data.conflicts_resolved  # type: ignore[attr-defined]
        if validation_notes:
            conflicts_resolved.extend(validation_notes)

        return SynthesisResponse(
            unified_interpretation=result.data.unified_interpretation,  # type: ignore[attr-defined]
            field_priorities=result.data.field_priorities,  # type: ignore[attr-defined]
            conflicts_resolved=conflicts_resolved,
        )

    def _format_interpretations(self, interpretations: list[Any]) -> str:
        """Format field interpretations for the prompt."""
        formatted = []
        for interpretation in interpretations:
            if hasattr(interpretation, "field_name"):
                formatted.append(f"{interpretation.field_name}: {interpretation.interpretation}")
            else:
                # Handle dict format for backward compatibility
                formatted.append(f"{interpretation['field_name']}: {interpretation['interpretation']}")
        return "\n".join(formatted)

    def _convert_dict_to_interpretations(self, field_interpretations: dict[str, str]) -> list[FieldInterpretation]:
        """Convert dict format to list of FieldInterpretation objects."""
        return [
            FieldInterpretation(field_name=field, interpretation=interpretation)
            for field, interpretation in field_interpretations.items()
        ]

    def _convert_priorities_to_dict(self, field_priorities: list[FieldPriority]) -> dict[str, int]:
        """Convert list of FieldPriority objects to dict format."""
        return {fp.field_name: fp.priority for fp in field_priorities}

    def _convert_dict_to_priorities(self, field_priorities: dict[str, int]) -> list[FieldPriority]:
        """Convert dict format to list of FieldPriority objects."""
        return [FieldPriority(field_name=field, priority=priority) for field, priority in field_priorities.items()]

    async def synthesize_query(
        self, query: str, field_interpretations: dict[str, str], previous_context: Any = None
    ) -> SynthesisResponse:
        """Convenience method to synthesize a query."""
        # Convert dict to list format
        interpretations_list = self._convert_dict_to_interpretations(field_interpretations)

        request = SynthesisRequest(query=query, field_interpretations=interpretations_list)

        # If this is a refinement, update the request with context
        if previous_context:
            # This is a refinement query - need to handle context
            return await self.synthesize_refinement(request, previous_context)
        else:
            return await self.synthesize_interpretations(request)

    @retry_on_ai_errors(max_retries=3)
    async def synthesize_refinement(self, request: SynthesisRequest, previous_context: Any) -> SynthesisResponse:
        """Synthesize a refinement query based on previous context."""

        # Validate and normalize interpretations
        normalized_interpretations, validation_notes = self._validate_and_normalize_interpretations(
            request.field_interpretations
        )

        # Log validation notes
        for note in validation_notes:
            logger.info(f"Categorical validation (refinement): {note}")

        # Create enhanced prompt for refinement
        prompt = REFINEMENT_PROMPT_TEMPLATE.format(
            previous_query=previous_context.query,
            previous_interpretation=previous_context.unified_interpretation,
            previous_priorities=previous_context.field_priorities,
            current_query=request.query,
            field_interpretations=self._format_interpretations(normalized_interpretations),
            us_exchanges=", ".join(US_EXCHANGES),
        )

        # Run the synthesis agent with refinement context
        if not self.synthesis_agent:
            raise ValueError("Synthesis agent not initialized")
        result = await self.synthesis_agent.run(prompt)

        # Combine previous and new field priorities
        previous_priorities_dict = self._convert_priorities_to_dict(previous_context.field_priorities)
        new_priorities_dict = self._convert_priorities_to_dict(result.data.field_priorities)  # type: ignore[attr-defined]

        combined_priorities = dict(previous_priorities_dict)
        for field, priority in new_priorities_dict.items():
            # Add new fields with adjusted priorities
            combined_priorities[field] = priority + len(previous_priorities_dict)

        combined_priorities_list = self._convert_dict_to_priorities(combined_priorities)

        # Add validation notes to conflicts resolved
        conflicts_resolved = result.data.conflicts_resolved  # type: ignore[attr-defined]
        if validation_notes:
            conflicts_resolved.extend(validation_notes)

        return SynthesisResponse(
            unified_interpretation=result.data.unified_interpretation,  # type: ignore[attr-defined]
            field_priorities=combined_priorities_list,
            conflicts_resolved=conflicts_resolved,
        )


# Service instance
synthesis_service = SynthesisService()


# Step function for pipeline integration
async def synthesize_interpretations_step(context: dict[str, Any], results: dict[str, Any]) -> SynthesisResponse:
    """Pipeline step function for synthesis."""
    from loguru import logger

    request = context["request"]
    instruction_result = results["process_instructions"].result

    logger.info("Synthesizing field interpretations")

    # Convert to dict format for synthesis
    field_interpretations_dict = {fi.field_name: fi.interpretation for fi in instruction_result.field_interpretations}

    result = await synthesis_service.synthesize_query(
        request.query, field_interpretations_dict, request.previous_context
    )

    logger.info(f"Synthesized query with {len(result.field_priorities)} prioritized fields")
    return result
