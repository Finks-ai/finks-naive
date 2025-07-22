"""
Instruction Processing Service - Loads field instructions and applies context-aware interpretation.
"""

from typing import Dict, List
from pathlib import Path
from pydantic_ai import Agent
from app.core.config import get_settings
from app.core.config_loader import load_config
from app.core.retry import retry_on_ai_errors
from .models import InstructionProcessingRequest, InstructionProcessingResponse
from .prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .guidelines import GUIDELINES

settings = get_settings()

# Initialize the instruction processing agent
instruction_processing_agent = Agent(
    model=settings.GEMINI_MODEL,
    result_type=InstructionProcessingResponse,
    system_prompt=SYSTEM_PROMPT.format(guidelines=GUIDELINES)
)


class InstructionProcessingService:
    """Service for processing field instructions in query context."""
    
    def __init__(self):
        self.field_instructions = self._load_field_instructions()
        self.available_fields = self._load_available_fields()
        self.unavailable_fields = self._load_unavailable_fields()
    
    def _load_available_fields(self) -> List[str]:
        """Load available fields from field mappings to ensure we only use fields that exist in database."""
        try:
            config = load_config("field_mappings")
            return list(config["field_mappings"].keys())
        except FileNotFoundError:
            return []
    
    def _load_unavailable_fields(self) -> List[str]:
        """Load unavailable fields that should be filtered out."""
        try:
            config = load_config("unavailable_fields")
            return config.get("unavailable_fields", [])
        except FileNotFoundError:
            return []
    
    def _load_field_instructions(self) -> Dict[str, str]:
        """Load field instructions from configuration."""
        try:
            # Load all instructions
            all_instructions = load_config("field_instructions")
            
            # Load available fields from mappings
            try:
                field_mappings = load_config("field_mappings")
                available_fields = set(field_mappings["field_mappings"].keys())
            except FileNotFoundError:
                # If field_mappings doesn't exist, use all instructions
                return all_instructions
            
            # Filter instructions to only include fields that exist in database
            # and exclude unavailable fields
            unavailable = self._load_unavailable_fields()
            filtered_instructions = {
                field: instruction 
                for field, instruction in all_instructions.items() 
                if field in available_fields and field not in unavailable
            }
            
            return filtered_instructions
            
        except FileNotFoundError:
            # Fallback to basic instructions if config not found
            return {
                "ttm_price_to_earnings_ratio": "PE ratio measures price relative to earnings. Lower values indicate cheaper stocks. For 'undervalued', use < 15. For 'fairly valued', use 15-25.",
                "ttm_price_to_book_ratio": "PB ratio shows price relative to book value. Lower values often indicate undervalued stocks. For 'undervalued', use < 1.5.",
                "market_capitalization": "Market cap indicates company size. Large cap > $10B, Mid cap $2-10B, Small cap < $2B."
            }
    
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
        
        # Create the prompt for the agent
        prompt = USER_PROMPT_TEMPLATE.format(
            query=request.query,
            field_instructions=self._format_instructions(relevant_instructions)
        )
        
        # Run the agent
        result = await instruction_processing_agent.run(prompt)
        
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