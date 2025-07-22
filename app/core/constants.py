"""
Constants for the Finks Naive application.
"""

# Default US exchanges to filter when no country is specified
US_EXCHANGES = ["NASDAQ", "NYSE", "AMEX", "CBOE", "CNQ", "ICE", "OTC"]

# Exchange filter for MongoDB queries
US_EXCHANGE_FILTER = {"exchange_acronym": {"$in": US_EXCHANGES}}