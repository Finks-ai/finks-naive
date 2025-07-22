"""
Field Extraction Agent Service - Identifies relevant database fields from natural language queries.
"""

from typing import List, Dict, Any
from app.core.retry import retry_on_ai_errors
from .models import FieldExtractionRequest, FieldExtractionResponse
from .prompts import USER_PROMPT_TEMPLATE
from ..registry import agent_registry, AgentType


class FieldExtractionService:
    """Service for extracting relevant fields from natural language queries."""
    
    def __init__(self):
        # Get shared configurations from registry
        self.available_fields = agent_registry.get_available_fields()
        self.unavailable_fields = agent_registry.get_unavailable_fields()
        self.field_categories = agent_registry.get_field_categories()
        # Get or create the AI agent
        self.ai_agent = agent_registry.get_ai_agent(AgentType.FIELD_EXTRACTION)
    
    def _get_category_info(self, field: str) -> Dict[str, Any]:
        """Get category information for a field."""
        field_to_category = self.field_categories.get("field_to_category", {})
        category_name = field_to_category.get(field)
        
        if category_name:
            categories = self.field_categories.get("categories", {})
            category_info = categories.get(category_name, {})
            return {
                "category": category_name,
                "type": category_info.get("type", "single"),
                "is_multiselect": category_info.get("type") == "multiselect"
            }
        
        return {
            "category": "Unknown",
            "type": "single",
            "is_multiselect": False
        }
    
    def _apply_category_constraints(self, fields: List[str]) -> List[str]:
        """Apply category constraints - single select for most categories, multiselect for Overview."""
        from loguru import logger
        
        # Group fields by category
        fields_by_category = {}
        for field in fields:
            category_info = self._get_category_info(field)
            category = category_info["category"]
            
            if category not in fields_by_category:
                fields_by_category[category] = []
            fields_by_category[category].append(field)
        
        # Apply constraints
        constrained_fields = []
        for category, category_fields in fields_by_category.items():
            category_info = self._get_category_info(category_fields[0])
            
            if category_info["is_multiselect"]:
                # Multiselect - keep all fields
                constrained_fields.extend(category_fields)
                logger.debug(f"Category {category} is multiselect, keeping all {len(category_fields)} fields")
            else:
                # Single select - keep only the first/most relevant field
                constrained_fields.append(category_fields[0])
                if len(category_fields) > 1:
                    logger.debug(f"Category {category} is single select, keeping only {category_fields[0]} out of {category_fields}")
        
        return constrained_fields
    
    @retry_on_ai_errors(max_retries=3)
    async def extract_fields(self, request: FieldExtractionRequest) -> FieldExtractionResponse:
        """Extract relevant fields from user query."""
        
        # Create the prompt for the agent
        prompt = USER_PROMPT_TEMPLATE.format(
            query=request.query,
            available_fields=', '.join(request.available_fields)
        )
        
        # Run the agent
        result = await self.ai_agent.run(prompt)
        
        # Validate that returned fields exist in available fields
        # and are not in unavailable fields
        validated_fields = [
            field for field in result.data.relevant_fields 
            if field in request.available_fields and field not in self.unavailable_fields
        ]
        
        # Apply category constraints (single select vs multiselect)
        validated_fields = self._apply_category_constraints(validated_fields)
        
        # Always include exchange_acronym for filtering American exchanges
        if "exchange_acronym" not in validated_fields and "exchange_acronym" in request.available_fields:
            validated_fields.append("exchange_acronym")
        
        return FieldExtractionResponse(
            relevant_fields=validated_fields,
            confidence=result.data.confidence,
            reasoning=result.data.reasoning
        )
    
    async def extract_fields_from_query(self, query: str) -> FieldExtractionResponse:
        """Convenience method to extract fields from a query string."""
        request = FieldExtractionRequest(
            query=query,
            available_fields=self.available_fields
        )
        return await self.extract_fields(request)


# Service instance
field_extraction_service = FieldExtractionService()


# Step function for pipeline integration
async def extract_fields_step(context: dict) -> FieldExtractionResponse:
    """Pipeline step function for field extraction."""
    query = context['request'].query
    from loguru import logger
    logger.info(f"Starting field extraction for query: {query}")
    
    # Check if caching is available
    if context.get('use_cache', False):
        try:
            from app.core.cache import cache_field_extraction
            @cache_field_extraction(ttl_seconds=7200)
            async def cached_extract():
                return await field_extraction_service.extract_fields_from_query(query)
            result = await cached_extract()
        except ImportError:
            result = await field_extraction_service.extract_fields_from_query(query)
    else:
        result = await field_extraction_service.extract_fields_from_query(query)
    
    logger.info(f"Extracted {len(result.relevant_fields)} relevant fields")
    return result