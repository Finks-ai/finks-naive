"""
Synthesis Service - Combines field interpretations and resolves conflicts.
"""

from typing import Dict, List
from app.core.constants import US_EXCHANGES
from app.core.retry import retry_on_ai_errors
from .models import SynthesisRequest, SynthesisResponse, FieldInterpretation, FieldPriority
from .prompts import USER_PROMPT_TEMPLATE, REFINEMENT_PROMPT_TEMPLATE
from ..registry import agent_registry, AgentType


class SynthesisService:
    """Service for synthesizing field interpretations into unified query strategy."""
    
    def __init__(self):
        # Get or create the AI agent
        self.synthesis_agent = agent_registry.get_ai_agent(AgentType.SYNTHESIS)
    
    @retry_on_ai_errors(max_retries=3)
    async def synthesize_interpretations(self, request: SynthesisRequest) -> SynthesisResponse:
        """Synthesize field interpretations into a unified strategy."""
        
        # Create the prompt for the agent
        prompt = USER_PROMPT_TEMPLATE.format(
            query=request.query,
            field_interpretations=self._format_interpretations(request.field_interpretations),
            us_exchanges=', '.join(US_EXCHANGES)
        )
        
        # Run the agent
        result = await self.synthesis_agent.run(prompt)
        
        return SynthesisResponse(
            unified_interpretation=result.data.unified_interpretation,
            field_priorities=result.data.field_priorities,
            conflicts_resolved=result.data.conflicts_resolved
        )
    
    def _format_interpretations(self, interpretations: List) -> str:
        """Format field interpretations for the prompt."""
        formatted = []
        for interpretation in interpretations:
            if hasattr(interpretation, 'field_name'):
                formatted.append(f"{interpretation.field_name}: {interpretation.interpretation}")
            else:
                # Handle dict format for backward compatibility
                formatted.append(f"{interpretation['field_name']}: {interpretation['interpretation']}")
        return "\n".join(formatted)
    
    def _convert_dict_to_interpretations(self, field_interpretations: Dict[str, str]) -> List[FieldInterpretation]:
        """Convert dict format to list of FieldInterpretation objects."""
        return [
            FieldInterpretation(field_name=field, interpretation=interpretation)
            for field, interpretation in field_interpretations.items()
        ]
    
    def _convert_priorities_to_dict(self, field_priorities: List[FieldPriority]) -> Dict[str, int]:
        """Convert list of FieldPriority objects to dict format."""
        return {fp.field_name: fp.priority for fp in field_priorities}
    
    def _convert_dict_to_priorities(self, field_priorities: Dict[str, int]) -> List[FieldPriority]:
        """Convert dict format to list of FieldPriority objects."""
        return [
            FieldPriority(field_name=field, priority=priority)
            for field, priority in field_priorities.items()
        ]
    
    async def synthesize_query(self, query: str, field_interpretations: Dict[str, str], previous_context=None) -> SynthesisResponse:
        """Convenience method to synthesize a query."""
        # Convert dict to list format
        interpretations_list = self._convert_dict_to_interpretations(field_interpretations)
        
        request = SynthesisRequest(
            query=query,
            field_interpretations=interpretations_list
        )
        
        # If this is a refinement, update the request with context
        if previous_context:
            # This is a refinement query - need to handle context
            return await self.synthesize_refinement(request, previous_context)
        else:
            return await self.synthesize_interpretations(request)
    
    @retry_on_ai_errors(max_retries=3)
    async def synthesize_refinement(self, request: SynthesisRequest, previous_context) -> SynthesisResponse:
        """Synthesize a refinement query based on previous context."""
        
        # Create enhanced prompt for refinement
        prompt = REFINEMENT_PROMPT_TEMPLATE.format(
            previous_query=previous_context.query,
            previous_interpretation=previous_context.unified_interpretation,
            previous_priorities=previous_context.field_priorities,
            current_query=request.query,
            field_interpretations=request.field_interpretations,
            us_exchanges=', '.join(US_EXCHANGES)
        )
        
        # Run the synthesis agent with refinement context
        result = await self.synthesis_agent.run(prompt)
        
        # Combine previous and new field priorities
        previous_priorities_dict = self._convert_priorities_to_dict(previous_context.field_priorities)
        new_priorities_dict = self._convert_priorities_to_dict(result.data.field_priorities)
        
        combined_priorities = dict(previous_priorities_dict)
        for field, priority in new_priorities_dict.items():
            # Add new fields with adjusted priorities
            combined_priorities[field] = priority + len(previous_priorities_dict)
        
        combined_priorities_list = self._convert_dict_to_priorities(combined_priorities)
        
        return SynthesisResponse(
            unified_interpretation=result.data.unified_interpretation,
            field_priorities=combined_priorities_list,
            conflicts_resolved=result.data.conflicts_resolved
        )


# Service instance
synthesis_service = SynthesisService()


# Step function for pipeline integration
async def synthesize_interpretations_step(context: dict, results: dict) -> SynthesisResponse:
    """Pipeline step function for synthesis."""
    from loguru import logger
    request = context['request']
    instruction_result = results['process_instructions'].result
    
    logger.info("Synthesizing field interpretations")
    
    # Convert to dict format for synthesis
    field_interpretations_dict = {
        fi.field_name: fi.interpretation 
        for fi in instruction_result.field_interpretations
    }
    
    result = await synthesis_service.synthesize_query(
        request.query,
        field_interpretations_dict,
        request.previous_context
    )
    
    logger.info(f"Synthesized query with {len(result.field_priorities)} prioritized fields")
    return result