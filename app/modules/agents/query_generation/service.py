"""
Query Generation Service - Converts unified interpretation into MongoDB queries.
"""

from typing import Dict, Any, List
from pydantic_ai import Agent
from app.core.constants import US_EXCHANGES, US_EXCHANGE_FILTER
from app.core.config import get_settings
from app.core.retry import retry_on_ai_errors
from loguru import logger
import json
import re
from .models import QueryGenerationRequest, QueryGenerationResponse, FieldPriority
from .prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, REFINEMENT_PROMPT_TEMPLATE
from .guidelines import GUIDELINES

settings = get_settings()

# Initialize the query generation agent
query_generation_agent = Agent(
    model=settings.GEMINI_MODEL,
    result_type=QueryGenerationResponse,
    system_prompt=SYSTEM_PROMPT.format(guidelines=GUIDELINES)
)


class QueryGenerationService:
    """Service for generating MongoDB queries from unified interpretations."""
    
    def _ensure_exchange_filter(self, mongodb_query: Dict[str, Any], request: QueryGenerationRequest) -> Dict[str, Any]:
        """Ensure US exchange filter is applied if no exchange filter exists."""
        # Check if exchange_acronym is mentioned in the unified interpretation
        has_exchange_mention = any(
            term in request.unified_interpretation.lower() 
            for term in ['exchange', 'canadian', 'foreign', 'international', 'global']
        )
        
        # If no exchange mention and no exchange filter in query, add US filter
        if not has_exchange_mention and 'exchange_acronym' not in str(mongodb_query):
            logger.info("No exchange filter found, applying default US exchange filter")
            
            # If query has $and operator, add to it
            if '$and' in mongodb_query and isinstance(mongodb_query['$and'], list):
                mongodb_query['$and'].append(US_EXCHANGE_FILTER)
            # If query has other operators at root level, wrap in $and
            elif any(key.startswith('$') for key in mongodb_query.keys()):
                mongodb_query = {
                    '$and': [mongodb_query, US_EXCHANGE_FILTER]
                }
            # Otherwise, merge the filter
            else:
                mongodb_query.update(US_EXCHANGE_FILTER)
        
        return mongodb_query
    
    def _clean_json_string(self, json_str: str) -> str:
        """Clean up JSON string by converting single quotes to double quotes."""
        # Replace single quotes with double quotes, but be careful with apostrophes in text
        # First, temporarily replace escaped quotes
        json_str = json_str.replace("\\'", "TEMP_ESCAPED_QUOTE")
        json_str = json_str.replace('\\"', "TEMP_ESCAPED_DOUBLE")
        
        # Replace single quotes around keys and values
        # This regex finds single quotes that are likely JSON delimiters
        json_str = re.sub(r"'([^']+)'(?=\s*:)", r'"\1"', json_str)  # Keys
        json_str = re.sub(r":\s*'([^']+)'", r': "\1"', json_str)     # String values
        json_str = re.sub(r"\[\s*'([^']+)'", r'["\1"', json_str)     # Array start
        json_str = re.sub(r"'([^']+)'\s*\]", r'"\1"]', json_str)     # Array end
        json_str = re.sub(r"'([^']+)'\s*,", r'"\1",', json_str)      # Array middle
        
        # Restore escaped quotes
        json_str = json_str.replace("TEMP_ESCAPED_QUOTE", "'")
        json_str = json_str.replace("TEMP_ESCAPED_DOUBLE", '\\"')
        
        return json_str
    
    @retry_on_ai_errors(max_retries=3)
    async def generate_query(self, request: QueryGenerationRequest) -> QueryGenerationResponse:
        """Generate MongoDB query from unified interpretation."""
        
        # Create the prompt for the agent
        prompt = USER_PROMPT_TEMPLATE.format(
            query=request.query,
            unified_interpretation=request.unified_interpretation,
            field_priorities=self._format_priorities(request.field_priorities),
            target_collection=request.target_collection,
            us_exchanges=json.dumps(list(US_EXCHANGES))
        )
        
        # Run the agent
        result = await query_generation_agent.run(prompt)
        
        # Parse the query if it's a string
        mongodb_query = result.data.mongodb_query
        if isinstance(mongodb_query, str):
            try:
                # Try to parse as-is first
                mongodb_query = json.loads(mongodb_query)
            except json.JSONDecodeError:
                # Try cleaning the JSON string
                cleaned_json = self._clean_json_string(mongodb_query)
                try:
                    mongodb_query = json.loads(cleaned_json)
                    logger.warning(f"Had to clean JSON from: {mongodb_query} to: {cleaned_json}")
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse MongoDB query JSON even after cleaning: {mongodb_query}")
                    # Don't return empty query on parse error - raise exception instead
                    raise ValueError(f"Invalid JSON in MongoDB query: {mongodb_query}")
        
        # Ensure US exchange filter is applied if no exchange filter exists
        mongodb_query = self._ensure_exchange_filter(mongodb_query, request)
        
        return QueryGenerationResponse(
            mongodb_query=mongodb_query,
            query_explanation=result.data.query_explanation,
            estimated_results=result.data.estimated_results
        )
    
    def _format_priorities(self, priorities: List[FieldPriority]) -> str:
        """Format field priorities for the prompt."""
        sorted_priorities = sorted(priorities, key=lambda x: x.priority)
        formatted = []
        for field_priority in sorted_priorities:
            formatted.append(f"Priority {field_priority.priority}: {field_priority.field_name}")
        return "\n".join(formatted)
    
    def _convert_priorities_to_dict(self, field_priorities: List[FieldPriority]) -> Dict[str, int]:
        """Convert list of FieldPriority objects to dict format."""
        return {fp.field_name: fp.priority for fp in field_priorities}
    
    def _convert_dict_to_priorities(self, field_priorities: Dict[str, int]) -> List[FieldPriority]:
        """Convert dict format to list of FieldPriority objects."""
        return [
            FieldPriority(field_name=field, priority=priority)
            for field, priority in field_priorities.items()
        ]
    
    async def generate_query_from_synthesis(
        self, 
        query: str, 
        unified_interpretation: str, 
        field_priorities: List[FieldPriority],
        target_collection: str = "master_search",
        previous_context=None
    ) -> QueryGenerationResponse:
        """Convenience method to generate query from synthesis results."""
        request = QueryGenerationRequest(
            query=query,
            unified_interpretation=unified_interpretation,
            field_priorities=field_priorities,
            target_collection=target_collection
        )
        
        # If this is a refinement, handle context
        if previous_context:
            return await self.generate_refinement_query(request, previous_context)
        else:
            return await self.generate_query(request)
    
    @retry_on_ai_errors(max_retries=3)
    async def generate_refinement_query(self, request: QueryGenerationRequest, previous_context) -> QueryGenerationResponse:
        """Generate a refined query that combines previous and new constraints."""
        
        # Create enhanced prompt for refinement
        prompt = REFINEMENT_PROMPT_TEMPLATE.format(
            previous_query=previous_context.query,
            previous_mongodb_query=previous_context.mongodb_query,
            current_query=request.query,
            unified_interpretation=request.unified_interpretation,
            field_priorities=self._format_priorities(request.field_priorities),
            target_collection=request.target_collection
        )
        
        # Run the query generation agent with refinement context
        result = await query_generation_agent.run(prompt)
        
        # Parse the query if it's a string
        mongodb_query = result.data.mongodb_query
        if isinstance(mongodb_query, str):
            try:
                # Try to parse as-is first
                mongodb_query = json.loads(mongodb_query)
            except json.JSONDecodeError:
                # Try cleaning the JSON string
                cleaned_json = self._clean_json_string(mongodb_query)
                try:
                    mongodb_query = json.loads(cleaned_json)
                    logger.warning(f"Had to clean refinement JSON from: {mongodb_query} to: {cleaned_json}")
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse MongoDB refinement query JSON even after cleaning: {mongodb_query}")
                    # Don't return empty query on parse error - raise exception instead
                    raise ValueError(f"Invalid JSON in refinement MongoDB query: {mongodb_query}")
        
        # For refinements, ensure we still have exchange filtering
        # The refinement should preserve the exchange filter from the previous query
        mongodb_query = self._ensure_exchange_filter(mongodb_query, request)
        
        return QueryGenerationResponse(
            mongodb_query=mongodb_query,
            query_explanation=result.data.query_explanation,
            estimated_results=result.data.estimated_results
        )


# Service instance
query_generation_service = QueryGenerationService()


# Step function for pipeline integration
async def generate_query_step(context: dict, results: dict) -> QueryGenerationResponse:
    """Pipeline step function for query generation."""
    request = context['request']
    synthesis_result = results['synthesize_interpretations'].result
    
    logger.info("Generating MongoDB query")
    
    result = await query_generation_service.generate_query_from_synthesis(
        request.query,
        synthesis_result.unified_interpretation,
        synthesis_result.field_priorities,
        "master_search",
        request.previous_context
    )
    
    logger.info("Generated MongoDB query")
    return result