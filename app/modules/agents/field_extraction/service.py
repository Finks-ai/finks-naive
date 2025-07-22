"""
Field Extraction Agent Service - Identifies relevant database fields from natural language queries.
"""

from typing import List, Dict, Any
from pathlib import Path
from pydantic_ai import Agent
from app.core.config import get_settings
from app.core.config_loader import load_config
from app.core.retry import retry_on_ai_errors
from .models import FieldExtractionRequest, FieldExtractionResponse
from .prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .guidelines import GUIDELINES

settings = get_settings()

# Initialize the field extraction agent
field_extraction_agent = Agent(
    model=settings.GEMINI_MODEL,
    result_type=FieldExtractionResponse,
    system_prompt=SYSTEM_PROMPT.format(guidelines=GUIDELINES)
)


class FieldExtractionService:
    """Service for extracting relevant fields from natural language queries."""
    
    def __init__(self):
        self.available_fields = self._load_available_fields()
        self.unavailable_fields = self._load_unavailable_fields()
        self.field_categories = self._load_field_categories()
    
    def _load_available_fields(self) -> List[str]:
        """Load available fields from configuration."""
        try:
            config = load_config("field_mappings")
            return list(config["field_mappings"].keys())
        except FileNotFoundError:
            # Fallback to basic fields if config not found
            return [
                "ttm_price_to_earnings_ratio",
                "ttm_price_to_book_ratio", 
                "market_capitalization",
                "company_sector",
                "ttm_dividend_yield",
                "ttm_return_on_equity"
            ]
    
    def _load_unavailable_fields(self) -> List[str]:
        """Load unavailable fields that should be filtered out."""
        try:
            config = load_config("unavailable_fields")
            return config.get("unavailable_fields", [])
        except FileNotFoundError:
            return []
    
    def _load_field_categories(self) -> Dict[str, Any]:
        """Load field categories and their selection types."""
        try:
            return load_config("field_categories")
        except FileNotFoundError:
            return {"categories": {}, "field_to_category": {}}
    
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
        result = await field_extraction_agent.run(prompt)
        
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