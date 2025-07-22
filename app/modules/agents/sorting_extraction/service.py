"""
Sorting Extraction Service - Identifies sorting requirements from natural language queries.
"""

from typing import Dict, List, Optional
from pydantic_ai import Agent
from app.core.config import get_settings
from app.core.retry import retry_on_ai_errors
from loguru import logger
import json
from .models import SortingIntent
from .prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .guidelines import GUIDELINES, DEFAULT_FIELD_MAPPINGS

settings = get_settings()


class SortingExtractionService:
    """Service for extracting sorting requirements from queries."""
    
    def __init__(self):
        self.agent = Agent(
            settings.GEMINI_MODEL,
            result_type=SortingIntent,
            system_prompt=SYSTEM_PROMPT.format(guidelines=GUIDELINES)
        )
        
        # Load field mappings for better field identification
        self.field_mappings = self._load_field_mappings()
    
    def _load_field_mappings(self) -> Dict[str, str]:
        """Load field mappings for common sorting terms."""
        try:
            # Use default mappings from guidelines
            return DEFAULT_FIELD_MAPPINGS
        except Exception as e:
            logger.warning(f"Could not load field mappings: {e}")
            return {}
    
    @retry_on_ai_errors(max_retries=3)
    async def extract_sorting_intent(self, query: str) -> SortingIntent:
        """Extract sorting intent from a natural language query."""
        try:
            logger.info(f"Extracting sorting intent from query: {query}")
            
            # Prepare prompt
            prompt = USER_PROMPT_TEMPLATE.format(
                query=query,
                available_fields=', '.join(set(self.field_mappings.values())),
                field_mappings=json.dumps(self.field_mappings, indent=2)
            )
            
            result = await self.agent.run(prompt)
            
            logger.info(f"Sorting intent extracted: has_sorting={result.data.has_sorting}, "
                       f"field={result.data.sort_field}, direction={result.data.sort_direction}")
            
            return result.data
            
        except Exception as e:
            logger.error(f"Error in sorting extraction: {str(e)}")
            # Return no sorting on error
            return SortingIntent(
                has_sorting=False,
                confidence=0.0,
                reasoning=f"Error during extraction: {str(e)}"
            )
    
    def infer_sort_field_from_context(self, query: str, extracted_fields: List[str]) -> Optional[str]:
        """Infer the sort field based on query context and extracted fields."""
        # If only one numeric field is extracted, it's likely the sort field
        numeric_fields = [
            f for f in extracted_fields 
            if any(term in f for term in ['cap', 'revenue', 'income', 'ratio', 'yield', 'price', 'debt', 'assets'])
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
async def extract_sorting_step(context: dict) -> SortingIntent:
    """Pipeline step function for sorting extraction."""
    query = context['request'].query
    logger.info("Extracting sorting intent")
    
    result = await sorting_extraction_service.extract_sorting_intent(query)
    
    logger.info(f"Sorting intent: has_sorting={result.has_sorting}, field={result.sort_field}")
    return result