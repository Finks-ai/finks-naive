"""
Guidelines for the Instruction Processing Agent.
"""

GUIDELINES = """Guidelines:
1. CRITICAL: Only process fields that are provided in the relevant_fields list
2. DO NOT add new fields that weren't extracted by the field extraction agent
3. Read the field instruction carefully to understand the field's purpose
4. Apply the instruction to the user's query context
5. Look for specific thresholds, ranges, or qualitative terms mentioned in instructions
6. Handle conflicts between fields (e.g., user wants "cheap" and "high quality")
7. Provide clear interpretation for each field that can guide query generation
8. Note any processing conflicts or ambiguities
9. If the query mentions concepts (like "revenue growth") that don't have corresponding fields in the relevant_fields list, note this in processing_notes but DO NOT add new fields"""

PROCESSING_RULES = {
    "percentage_conversion": {
        "description": "Convert percentage values to decimals",
        "examples": {"25%": 0.25, "10%": 0.10, "100%": 1.0, "5%": 0.05},
    },
    "monetary_conversion": {
        "description": "Convert monetary values to numeric",
        "examples": {"$1B": 1000000000, "$10B": 10000000000, "$100M": 100000000, "$1M": 1000000},
    },
    "qualitative_mapping": {
        "description": "Map qualitative terms to quantitative thresholds",
        "examples": {
            "cheap": "below median or bottom quartile",
            "expensive": "above median or top quartile",
            "high": "top 25% or above specified threshold",
            "low": "bottom 25% or below specified threshold",
            "strong": "significantly above average",
            "weak": "significantly below average",
        },
    },
}
