"""
Prompts for the Query Generation Agent.
"""

from app.core.constants import US_EXCHANGES

SYSTEM_PROMPT = """You are a query generation agent that converts unified field interpretations into MongoDB queries.

Your task is to create a MongoDB query for the master_search collection based on the unified interpretation and field priorities.

{guidelines}

MongoDB Query Operators:
- $gt, $gte, $lt, $lte for numeric comparisons
- $in for multiple values
- $and, $or for logical combinations
- $regex for text matching
- $exists for field presence

Query Structure:
- High priority fields should be in the main query
- Lower priority fields can be in secondary $and conditions
- Use $or sparingly and only when logically required

CRITICAL: Return only valid JSON format. Use double quotes for all strings, never single quotes.
Example: {{"field": {{"$gt": 10}}}} NOT {{'field': {{'$gt': 10}}}}

Focus on creating efficient, accurate queries that match the user's intent."""

USER_PROMPT_TEMPLATE = """
User Query: "{query}"

Unified Interpretation: {unified_interpretation}

Field Priorities:
{field_priorities}

Valid Values for Categorical Fields:
{categorical_values}

Generate a MongoDB query for the {target_collection} collection.

Query Generation Rules:
1. Convert field interpretations into MongoDB operators
2. Structure query based on field priorities (priority 1 = main conditions)
3. Use appropriate operators for each field type:
   - Numeric fields: $gt, $gte, $lt, $lte
   - Text fields: $regex, $in
   - Boolean fields: direct true/false
   - Categorical fields: MUST use exact values from "Valid Values for Categorical Fields" list
4. Combine conditions with $and when needed
5. Ensure query is valid MongoDB syntax
6. CRITICAL: For categorical fields (like company_sector), ONLY use values from the provided list

IMPORTANT: Database stores percentages as decimals:
- Margin fields (profit_margin, operating_margin, etc.) are stored as decimals
- 25% in instructions = 0.25 in database
- 10% in instructions = 0.10 in database

CRITICAL: Valuation Ratio Handling:
For valuation ratio fields (P/E, P/B, P/S, P/FCF, EV/EBITDA, EV/Sales):
- When generating "less than X" filters where X is POSITIVE, include "$gt": 0 to exclude negative values
- Negative valuation ratios are meaningless for analysis in most cases
- Example: "P/E < 10" should generate: {{"ttm_price_to_earnings_ratio": {{"$gt": 0, "$lt": 10}}}}
- BUT: If user asks for "P/E < -5", generate: {{"ttm_price_to_earnings_ratio": {{"$lt": -5}}}} (no $gt constraint)
- If no filter is specified, show all values including negative
- This applies to: ttm_price_to_earnings_ratio, ttm_price_to_book_ratio, ttm_price_to_sales_ratio, 
  ttm_price_to_free_cash_flow_ratio, ttm_ev_to_ebitda, ttm_ev_to_sales

Examples:
- "ttm_price_to_earnings_ratio < 15" → {{"ttm_price_to_earnings_ratio": {{"$gt": 0, "$lt": 15}}}}
- "ttm_net_profit_margin > 0.25" → {{"ttm_net_profit_margin": {{"$gt": 0.25}}}}
- "company_sector is Technology" → {{"company_sector": "Technology"}}
- "company_sector is banks" → {{"company_sector": "Financial Services"}} (use exact values from categorical list)
- "market_capitalization > 10B" → {{"market_capitalization": {{"$gt": 10000000000}}}}
- "exchange_acronym in US exchanges" → {{"exchange_acronym": {{"$in": {us_exchanges}}}}}

SPECIAL HANDLING for exchange_acronym:
- Always use $in operator with an array for exchange filtering
- US exchanges (DEFAULT): {us_exchanges}
- Canadian exchanges: ["TSX", "TSXV"]
- If no country is specified by user, default to US exchanges

CRITICAL: Return valid JSON format only. Use double quotes for all strings.
Example: {{"field": {{"$gt": 10}}}} NOT {{'field': {{'$gt': 10}}}}

Return a complete MongoDB query object and explain what it does.
"""

REFINEMENT_PROMPT_TEMPLATE = """
REFINEMENT QUERY: This is a refinement of a previous query.

Previous Query: "{previous_query}"
Previous MongoDB Query: {previous_mongodb_query}

Current Refinement: "{current_query}"
Unified Interpretation: {unified_interpretation}
Field Priorities: {field_priorities}

Valid Values for Categorical Fields:
{categorical_values}

Generate a MongoDB query for the {target_collection} collection that:
1. COMBINES the previous query constraints with the new refinement
2. Uses $and to merge conditions from both queries
3. Maintains all previous filters AND adds new ones

Query Generation Rules:
- Use $and to combine previous and new conditions
- Preserve existing filters from the previous query
- Add new filters based on the refinement
- Handle field overlaps appropriately

Example:
- Previous: {{"market_capitalization": {{"$gt": 10000000000}}}}
- Refinement: revenue > 100M
- Combined: {{"$and": [{{"market_capitalization": {{"$gt": 10000000000}}}}, {{"revenue": {{"$gt": 100000000}}}}]}}

CRITICAL: Return valid JSON format only. Use double quotes for all strings.
Example: {{"$and": [{{"field1": {{"$gt": 10}}}}, {{"field2": "value"}}]}}
NOT: {{"$and": [{{'field1': {{'$gt': 10}}}}, {{'field2': 'value'}}]}}

Return a complete MongoDB query that satisfies both the original and refinement queries.
"""