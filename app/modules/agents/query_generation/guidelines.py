"""
Guidelines for the Query Generation Agent.
"""

GUIDELINES = """Guidelines:
1. Convert field interpretations into MongoDB query operators
2. Use priority rankings to structure the query logically
3. Handle range queries, comparison operators, and text searches appropriately
4. Ensure the query is valid MongoDB syntax
5. Provide clear explanation of the generated query
6. ALWAYS return valid JSON with double quotes - never use single quotes or Python dict syntax"""

OPERATOR_MAPPING = {
    "numeric_operators": {
        "greater_than": "$gt",
        "greater_equal": "$gte",
        "less_than": "$lt",
        "less_equal": "$lte",
        "equals": {"direct": "value"},
        "not_equals": "$ne"
    },
    "array_operators": {
        "in_list": "$in",
        "not_in_list": "$nin",
        "all_of": "$all"
    },
    "logical_operators": {
        "and": "$and",
        "or": "$or",
        "not": "$not",
        "nor": "$nor"
    },
    "text_operators": {
        "regex": "$regex",
        "options": "$options"
    },
    "existence_operators": {
        "exists": "$exists",
        "type": "$type"
    }
}

QUERY_CONSTRUCTION_PATTERNS = {
    "single_condition": {
        "pattern": '{"field": {"$operator": value}}',
        "example": '{"ttm_price_to_earnings_ratio": {"$lt": 15}}'
    },
    "multiple_conditions_same_field": {
        "pattern": '{"field": {"$gte": min_value, "$lte": max_value}}',
        "example": '{"market_capitalization": {"$gte": 1000000000, "$lte": 10000000000}}'
    },
    "and_conditions": {
        "pattern": '{"$and": [condition1, condition2, ...]}',
        "example": '{"$and": [{"ttm_price_to_earnings_ratio": {"$lt": 15}}, {"ttm_dividend_yield": {"$gt": 0.02}}]}'
    },
    "or_conditions": {
        "pattern": '{"$or": [condition1, condition2, ...]}',
        "example": '{"$or": [{"company_sector": "Technology"}, {"company_sector": "Healthcare"}]}'
    },
    "in_array": {
        "pattern": '{"field": {"$in": [value1, value2, ...]}}',
        "example": '{"exchange_acronym": {"$in": ["NASDAQ", "NYSE", "AMEX"]}}'
    }
}

JSON_FORMATTING_RULES = """
JSON Formatting Rules:
1. ALWAYS use double quotes for strings: "field" not 'field'
2. Numbers don't need quotes: 10 not "10"
3. Booleans are lowercase without quotes: true not "true"
4. Arrays use square brackets: ["A", "B", "C"]
5. Objects use curly braces: {"key": "value"}
6. No trailing commas in arrays or objects
7. Escape special characters in strings with backslash
"""