"""
Guidelines for the Sorting Extraction Agent.
"""

GUIDELINES = """Common sorting patterns:
- "biggest/largest/top" → descending by size/value
- "smallest/lowest/bottom" → ascending by size/value
- "highest/most" → descending
- "least/fewest" → ascending
- "sort by X from high to low" → descending by X
- "order by X" → typically descending for financial metrics
- "rank by X" → implies sorting

Field mapping hints:
- "biggest/largest companies" → market_cap
- "most profitable" → ttm_net_income or net_profit_margin
- "highest revenue/sales" → ttm_revenue
- "best performing" → price_change_percentage_YTD or price_change_percentage_1year
- "most expensive/cheapest" → pe_ratio (expensive=high, cheap=low)
- "highest dividend" → dividend_rate or dividend_yield"""

SORTING_PATTERNS = {
    "descending_indicators": [
        "biggest",
        "largest",
        "top",
        "highest",
        "most",
        "greatest",
        "maximum",
        "best",
        "leading",
        "major",
        "primary",
    ],
    "ascending_indicators": [
        "smallest",
        "lowest",
        "bottom",
        "least",
        "fewest",
        "minimum",
        "worst",
        "trailing",
        "minor",
        "cheapest",
    ],
    "explicit_sorting": [
        "sort by",
        "order by",
        "rank by",
        "arrange by",
        "list by",
        "show by",
        "display by",
        "from high to low",
        "from low to high",
        "ascending",
        "descending",
        "asc",
        "desc",
    ],
}

DEFAULT_FIELD_MAPPINGS = {
    "market cap": "market_cap",
    "valuation": "market_cap",
    "size": "market_cap",
    "revenue": "ttm_revenue",
    "sales": "ttm_revenue",
    "profit": "ttm_net_income",
    "earnings": "ttm_net_income",
    "profitability": "net_profit_margin",
    "margin": "net_profit_margin",
    "pe": "pe_ratio",
    "price to earnings": "pe_ratio",
    "dividend": "dividend_yield",
    "dividend yield": "dividend_yield",
    "performance": "price_change_percentage_YTD",
    "return": "price_change_percentage_YTD",
    "growth": "year_over_year_quarterly_revenue_growth",
    "debt": "total_debt",
    "assets": "total_assets",
    "volume": "volume",
    "beta": "beta",
    "roe": "return_on_equity",
    "return on equity": "return_on_equity",
}

CONTEXTUAL_DEFAULTS = {
    "companies": "market_cap",
    "stocks": "market_cap",
    "profitable": "ttm_net_income",
    "performance": "price_change_percentage_YTD",
    "dividend": "dividend_yield",
    "expensive": "pe_ratio",
    "cheap": "pe_ratio",
}
