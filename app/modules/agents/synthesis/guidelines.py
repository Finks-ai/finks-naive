"""
Guidelines for the Synthesis Agent.
"""

GUIDELINES = """Guidelines:
1. ALWAYS include exchange_acronym field to filter for American exchanges unless user explicitly requests otherwise
2. CRITICAL: Only use fields that were provided in the field_interpretations - NEVER create new fields
3. If the user asks for something not available (like stock price), acknowledge the limitation and use the closest available metric
4. Identify conflicts between field interpretations (e.g., wanting both "cheap" and "high quality")
5. Resolve conflicts by prioritizing based on user intent
6. Create a unified interpretation that balances all requirements
7. Assign priority rankings to fields (1=highest priority)
8. Provide clear reasoning for conflict resolution decisions

IMPORTANT: You must work only with the fields provided in field_interpretations. Do not invent or add any fields that were not explicitly provided by the field extraction and instruction processing agents."""

CONFLICT_RESOLUTION_STRATEGIES = {
    "cheap_vs_quality": {
        "description": "User wants both value and quality",
        "resolution": "Prioritize quality metrics with reasonable valuation constraints",
        "example": "Filter for positive margins and ROE > 15%, then apply PE < 20 as secondary filter"
    },
    "growth_vs_dividend": {
        "description": "User wants both growth and income",
        "resolution": "Look for companies with moderate growth and sustainable dividends",
        "example": "Revenue growth > 5% AND dividend yield > 2%"
    },
    "size_vs_value": {
        "description": "User wants large cap but also undervalued",
        "resolution": "Apply size filter first, then look for relative value within that segment",
        "example": "Market cap > $10B AND PE ratio below sector average"
    },
    "multiple_sectors": {
        "description": "User mentions multiple sectors",
        "resolution": "Use OR condition for sectors unless user implies intersection",
        "example": "company_sector IN ['Technology', 'Healthcare']"
    }
}

PRIORITY_ASSIGNMENT_RULES = {
    "primary_intent": "Priority 1 - The main focus of the user's query",
    "exchange_filter": "Priority 2-3 - Geographic/exchange filtering",
    "supporting_criteria": "Priority 3-4 - Additional filters that support main intent",
    "context_fields": "Priority 5+ - Nice-to-have fields for additional context"
}