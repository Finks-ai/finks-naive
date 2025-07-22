"""
Guidelines for the Field Extraction Agent.
"""

GUIDELINES = """Guidelines:
1. Look for explicit mentions of financial metrics, company attributes, or performance indicators
2. Identify implicit requirements (e.g., "cheap stocks" implies price-based valuation metrics)
3. Consider synonyms and related terms (e.g., "profitable" relates to margin and return metrics)
4. Prioritize fields that directly address the user's intent
5. Include supporting fields that provide context
6. Be aware of field categories:
   - Valuation: Price ratios (single select)
   - Returns: Price performance over time (single select)
   - Profitability: Margin and return metrics (single select)
   - Overview: Company attributes like sector, exchange, etc. (multiselect allowed)
   - Quality: Financial health metrics (single select)
   - Growth: Revenue and earnings growth (single select)
7. For single select categories, choose the most relevant field
8. For Overview category (multiselect), include all relevant fields"""

FIELD_MAPPING_EXAMPLES = {
    "cheap stocks": ["ttm_price_to_earnings_ratio", "ttm_price_to_book_ratio", "ttm_price_to_sales_ratio"],
    "profitable companies": ["ttm_net_profit_margin", "ttm_operating_margin", "ttm_return_on_equity"],
    "dividend stocks": ["ttm_dividend_yield"],
    "tech companies": ["company_sector"],
    "large cap": ["market_capitalization"],
    "growth stocks": ["revenue_growth", "ttm_revenue", "ttm_price_to_earnings_ratio"],
    "value stocks": ["ttm_price_to_book_ratio", "ttm_price_to_earnings_ratio", "ttm_dividend_yield"],
    "quality companies": ["ttm_return_on_equity", "ttm_return_on_assets", "debt_to_equity_ratio"],
    "safe investments": ["ttm_dividend_yield", "debt_to_equity_ratio", "ttm_current_ratio"],
    "high margin": ["ttm_net_profit_margin", "ttm_operating_margin", "ttm_gross_margin"]
}