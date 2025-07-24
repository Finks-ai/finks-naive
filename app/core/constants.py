"""
Constants for the Finks Naive application.
"""

# Default US exchanges to filter when no country is specified
US_EXCHANGES = ["NASDAQ", "NYSE", "AMEX", "CBOE", "CNQ", "ICE"]

# Exchange filter for MongoDB queries
US_EXCHANGE_FILTER = {"exchange_acronym": {"$in": US_EXCHANGES}}

# Valuation ratio fields that should exclude negative values when using "less than" filters
# Negative values for these ratios are meaningless for valuation analysis
VALUATION_RATIO_FIELDS = [
    "ttm_ev_to_ebitda",
    "ttm_ev_to_sales",
    "ttm_price_to_earnings_ratio",
    "ttm_price_to_free_cash_flow_ratio",
    "ttm_price_to_book_ratio",
    "ttm_price_to_sales_ratio",
]
