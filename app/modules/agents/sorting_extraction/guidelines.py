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
- "biggest/largest companies" → market_capitalization
- "most profitable" → ttm_net_profit_margin
- "highest revenue/sales" → year_over_year_quarterly_revenue_growth
- "best performing" → price_change_yeartodate_percentage or price_change_1year_percentage
- "most expensive/cheapest" → ttm_price_to_earnings_ratio (expensive=high, cheap=low)
- "highest dividend" → ttm_dividend_yield"""

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
    "market cap": "market_capitalization",
    "valuation": "market_capitalization",
    "size": "market_capitalization",
    "revenue": "year_over_year_quarterly_revenue_growth",
    "sales": "year_over_year_quarterly_revenue_growth",
    "profit": "ttm_net_profit_margin",
    "earnings": "ttm_net_profit_margin",
    "profitability": "ttm_net_profit_margin",
    "margin": "ttm_net_profit_margin",
    "pe": "ttm_price_to_earnings_ratio",
    "price to earnings": "ttm_price_to_earnings_ratio",
    "dividend": "ttm_dividend_yield",
    "dividend yield": "ttm_dividend_yield",
    "performance": "price_change_yeartodate_percentage",
    "return": "price_change_yeartodate_percentage",
    "growth": "year_over_year_quarterly_revenue_growth",
    "debt": "ttm_debt_to_equity_ratio",
    "assets": "ttm_return_on_assets",
    "volume": "average_volume",
    "beta": "beta",
    "roe": "ttm_return_on_equity",
    "return on equity": "ttm_return_on_equity",
}

CONTEXTUAL_DEFAULTS = {
    "companies": "market_capitalization",
    "stocks": "market_capitalization",
    "profitable": "ttm_net_profit_margin",
    "performance": "price_change_yeartodate_percentage",
    "dividend": "ttm_dividend_yield",
    "expensive": "ttm_price_to_earnings_ratio",
    "cheap": "ttm_price_to_earnings_ratio",
}
