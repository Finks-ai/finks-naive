"""
Query Generation Service - Converts unified interpretation into MongoDB queries.
"""

from typing import Dict, Any, List
from app.core.constants import US_EXCHANGES, US_EXCHANGE_FILTER, VALUATION_RATIO_FIELDS
from app.core.retry import retry_on_ai_errors
from loguru import logger
import json
import re
from .models import QueryGenerationRequest, QueryGenerationResponse, FieldPriority
from .prompts import USER_PROMPT_TEMPLATE, REFINEMENT_PROMPT_TEMPLATE
from ..registry import agent_registry, AgentType


class QueryGenerationService:
    """Service for generating MongoDB queries from unified interpretations."""
    
    def __init__(self):
        # Get or create the AI agent
        self.query_generation_agent = agent_registry.get_ai_agent(AgentType.QUERY_GENERATION)
        # Get categorical values for validation and prompt enhancement
        self.categorical_values = agent_registry.get_categorical_values()
    
    def _ensure_exchange_filter(self, mongodb_query: Dict[str, Any], request: QueryGenerationRequest) -> Dict[str, Any]:
        """Ensure US exchange filter is applied if no exchange filter exists."""
        # Check if exchange_acronym is mentioned in the unified interpretation
        # TODO: Expand this or make more comprehensive
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
    
    def _ensure_positive_valuation_ratios(self, mongodb_query: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure valuation ratio fields exclude negative values when using 'less than' filters.
        
        For valuation ratios, negative values are meaningless. When a user asks for 
        "P/E < 10", they want positive P/E values less than 10, not negative P/E values.
        
        Rules:
        - Only hide negative values when user asks for "less than X" where X is positive
        - If user doesn't specify a valuation filter, show all values (including negative)
        - If user specifically asks for "less than -X", show negative values
        """
        def process_conditions(conditions: Dict[str, Any]) -> Dict[str, Any]:
            """Recursively process query conditions to fix valuation ratio filters."""
            modified_conditions = {}
            
            for field, value in conditions.items():
                if field in VALUATION_RATIO_FIELDS and isinstance(value, dict):
                    # Check if this field has only a "$lt" or "$lte" operator
                    has_lt = "$lt" in value or "$lte" in value
                    has_gt = "$gt" in value or "$gte" in value
                    
                    if has_lt and not has_gt:
                        # Get the threshold value
                        threshold = value.get("$lt") or value.get("$lte")
                        
                        # Only add positive constraint if threshold is positive
                        if threshold is not None and threshold > 0:
                            logger.info(f"Adding positive constraint for valuation field: {field} (threshold: {threshold})")
                            new_value = {"$gt": 0}
                            new_value.update(value)
                            modified_conditions[field] = new_value
                        else:
                            # Keep original filter for negative thresholds
                            modified_conditions[field] = value
                    else:
                        modified_conditions[field] = value
                elif field == "$and" and isinstance(value, list):
                    # Process each condition in the $and array
                    modified_conditions[field] = [
                        process_conditions(cond) if isinstance(cond, dict) else cond 
                        for cond in value
                    ]
                elif field == "$or" and isinstance(value, list):
                    # Process each condition in the $or array
                    modified_conditions[field] = [
                        process_conditions(cond) if isinstance(cond, dict) else cond 
                        for cond in value
                    ]
                elif isinstance(value, dict):
                    # Recursively process nested dictionaries
                    modified_conditions[field] = process_conditions(value)
                else:
                    modified_conditions[field] = value
            
            return modified_conditions
        
        return process_conditions(mongodb_query)
    
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
        
        # Extract field names from the unified interpretation
        relevant_fields = [fp.field_name for fp in request.field_priorities]
        
        # Create the prompt for the agent
        prompt = USER_PROMPT_TEMPLATE.format(
            query=request.query,
            unified_interpretation=request.unified_interpretation,
            field_priorities=self._format_priorities(request.field_priorities),
            categorical_values=self._format_categorical_values(relevant_fields),
            target_collection=request.target_collection,
            us_exchanges=json.dumps(list(US_EXCHANGES))
        )
        
        # Run the agent
        result = await self.query_generation_agent.run(prompt)
        
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
        
        # Ensure valuation ratios exclude negative values when using "less than" filters
        mongodb_query = self._ensure_positive_valuation_ratios(mongodb_query)
        
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
    
    def _format_categorical_values(self, relevant_fields: List[str] = None) -> str:
        """Format categorical field values for the prompt.
        
        Args:
            relevant_fields: Optional list of fields mentioned in the query. 
                           If provided, only show categorical values for these fields.
        """
        formatted = []
        
        # Priority fields to always include if they have categorical values
        priority_categorical_fields = {'company_sector', 'source_collections'}
        
        for field, info in self.categorical_values.items():
            if isinstance(info, dict) and 'values' in info:
                values = info['values']
                
                # Include if:
                # 1. It's a priority field, OR
                # 2. The field is mentioned in the current query (if relevant_fields provided), OR
                # 3. No relevant_fields specified AND field has <= 20 values
                should_include = (
                    field in priority_categorical_fields or
                    (relevant_fields and field in relevant_fields) or
                    (not relevant_fields and len(values) <= 20)
                )
                
                if should_include and len(values) <= 50:  # Hard limit at 50 values
                    formatted.append(f"- {field}: {json.dumps(values)}")
        
        return "\n".join(formatted) if formatted else "No categorical constraints apply"
    
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
        
        # Extract field names from the unified interpretation
        relevant_fields = [fp.field_name for fp in request.field_priorities]
        
        # Create enhanced prompt for refinement
        prompt = REFINEMENT_PROMPT_TEMPLATE.format(
            previous_query=previous_context.query,
            previous_mongodb_query=previous_context.mongodb_query,
            current_query=request.query,
            unified_interpretation=request.unified_interpretation,
            field_priorities=self._format_priorities(request.field_priorities),
            categorical_values=self._format_categorical_values(relevant_fields),
            target_collection=request.target_collection
        )
        
        # Run the query generation agent with refinement context
        result = await self.query_generation_agent.run(prompt)
        
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
        
        # Ensure valuation ratios exclude negative values when using "less than" filters
        mongodb_query = self._ensure_positive_valuation_ratios(mongodb_query)
        
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
