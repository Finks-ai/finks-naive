from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request model for natural language queries."""

    query: str = Field(..., description="Natural language query", min_length=1)
    limit: int | None = Field(default=50, description="Maximum number of results", ge=1, le=1000)

    model_config = {
        "json_schema_extra": {
            "example": {"query": "Find undervalued technology companies with high growth", "limit": 50}
        }
    }


class CompanyResult(BaseModel):
    """Individual company result model."""

    symbol: str = Field(..., description="Stock symbol")
    company_name: str | None = Field(None, description="Company name")
    sector: str | None = Field(None, description="Industry sector")
    market_capitalization: float | None = Field(None, description="Market capitalization")
    pe_ratio: float | None = Field(None, description="Price-to-earnings ratio")
    revenue_growth: float | None = Field(None, description="Revenue growth rate")

    # Additional fields will be populated dynamically based on query
    additional_fields: dict[str, Any] = Field(default_factory=lambda: {}, description="Additional company data")

    model_config = {
        "json_schema_extra": {
            "example": {
                "symbol": "AAPL",
                "company_name": "Apple Inc.",
                "sector": "Technology",
                "market_capitalization": 3000000000000,
                "pe_ratio": 25.5,
                "revenue_growth": 0.15,
                "additional_fields": {"debt_to_equity": 0.5, "dividend_yield": 0.02},
            }
        }
    }


class QueryResponse(BaseModel):
    """Response model for query results."""

    success: bool = Field(..., description="Whether query was successful")
    query: str = Field(..., description="Original query")
    results: list[CompanyResult] = Field(..., description="List of matching companies")
    total_count: int = Field(..., description="Total number of results")
    execution_time_ms: float = Field(..., description="Query execution time in milliseconds")

    # Query processing metadata
    identified_fields: list[str] = Field(default_factory=list, description="Fields identified from query")
    mongo_query: dict[str, Any] | None = Field(None, description="Generated MongoDB query")

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "query": "Find undervalued technology companies",
                "results": [
                    {
                        "symbol": "AAPL",
                        "company_name": "Apple Inc.",
                        "sector": "Technology",
                        "market_capitalization": 3000000000000,
                        "pe_ratio": 12.5,
                        "revenue_growth": 0.15,
                    }
                ],
                "total_count": 1,
                "execution_time_ms": 250.5,
                "identified_fields": ["sector", "pe_ratio"],
                "mongo_query": {"sector": "Technology", "pe_ratio": {"$lt": 15}},
            }
        }
    }


class QueryError(BaseModel):
    """Error response model."""

    success: bool = Field(default=False, description="Always false for errors")
    error: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Type of error")
    query: str | None = Field(None, description="Original query if available")

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": False,
                "error": "Unable to parse query: no recognizable fields found",
                "error_type": "parsing_error",
                "query": "invalid query text",
            }
        }
    }
