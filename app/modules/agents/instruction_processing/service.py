"""
Instruction Processing Service - Loads field instructions and applies context-aware interpretation.
"""

from typing import Dict, List
from app.core.retry import retry_on_ai_errors
from .models import InstructionProcessingRequest, InstructionProcessingResponse
from .prompts import USER_PROMPT_TEMPLATE
from ..registry import agent_registry, AgentType


class InstructionProcessingService:
    """Service for processing field instructions in query context."""
    
    def __init__(self):
        # Get shared configurations from registry
        self.available_fields = agent_registry.get_available_fields()
        self.unavailable_fields = agent_registry.get_unavailable_fields()
        self.field_instructions = self._filter_field_instructions()
        self.categorical_values = agent_registry.get_categorical_values()
        # Get or create the AI agent
        self.ai_agent = agent_registry.get_ai_agent(AgentType.INSTRUCTION_PROCESSING)
    
    def _filter_field_instructions(self) -> Dict[str, str]:
        """Filter field instructions to only include available fields."""
        all_instructions = agent_registry.get_field_instructions()
        
        # Filter instructions to only include fields that exist in database
        # and exclude unavailable fields
        if self.available_fields:
            filtered_instructions = {
                field: instruction 
                for field, instruction in all_instructions.items() 
                if field in self.available_fields and field not in self.unavailable_fields
            }
            return filtered_instructions
        else:
            # If no available fields loaded, return all instructions
            return all_instructions
    
    @retry_on_ai_errors(max_retries=3)
    async def process_instructions(self, request: InstructionProcessingRequest) -> InstructionProcessingResponse:
        """Process field instructions in the context of user query."""
        
        # Filter to only process fields that exist in our available fields
        # and are not in unavailable fields
        valid_fields = [
            field for field in request.relevant_fields 
            if field in self.available_fields and field not in self.unavailable_fields
        ]
        
        # Get instructions for relevant fields
        relevant_instructions = {
            field: self.field_instructions.get(field, f"No specific instruction available for {field}")
            for field in valid_fields
        }
        
        # Get categorical values for relevant fields
        relevant_categorical = {
            field: self.categorical_values.get(field, {})
            for field in valid_fields
            if field in self.categorical_values
        }
        
        # Create the prompt for the agent
        prompt = USER_PROMPT_TEMPLATE.format(
            query=request.query,
            field_instructions=self._format_instructions(relevant_instructions),
            categorical_values=self._format_categorical_values(relevant_categorical)
        )
        
        # Run the agent
        result = await self.ai_agent.run(prompt)
        
        return InstructionProcessingResponse(
            field_interpretations=result.data.field_interpretations,
            processing_notes=result.data.processing_notes
        )
    
    def _format_instructions(self, instructions: Dict[str, str]) -> str:
        """Format instructions for the prompt."""
        formatted = []
        for field, instruction in instructions.items():
            formatted.append(f"{field}: {instruction}")
        return "\n".join(formatted)
    
    def _format_categorical_values(self, categorical: Dict[str, Dict]) -> str:
        """Format categorical values for the prompt."""
        if not categorical:
            return "No categorical fields in this query."
        
        formatted = []
        for field, cat_info in categorical.items():
            values = cat_info.get('values', [])
            if values:
                formatted.append(f"{field}: {', '.join(values)}")
        
        return "\n".join(formatted) if formatted else "No categorical fields in this query."
    
    async def process_query_instructions(self, query: str, relevant_fields: List[str]) -> InstructionProcessingResponse:
        """Convenience method to process instructions for a query."""
        request = InstructionProcessingRequest(
            query=query,
            relevant_fields=relevant_fields,
            field_instructions=self.field_instructions
        )
        return await self.process_instructions(request)


# Service instance
instruction_processing_service = InstructionProcessingService()


# Step function for pipeline integration
async def process_instructions_step(context: dict, results: dict) -> InstructionProcessingResponse:
    """Pipeline step function for instruction processing."""
    from loguru import logger
    query = context['request'].query
    field_extraction_result = results['extract_fields'].result
    
    logger.info("Processing field instructions")
    result = await instruction_processing_service.process_query_instructions(
        query,
        field_extraction_result.relevant_fields
    )
    
    logger.info(f"Processed instructions for {len(result.field_interpretations)} fields")
    return result