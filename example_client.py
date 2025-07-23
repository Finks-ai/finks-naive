#!/usr/bin/env python3
"""
Example client for the Finks Naive API using Pydantic models.
"""

import asyncio

import httpx

from app.modules.agents.models import AgentPipelineRequest, AgentPipelineResponse

API_BASE_URL = "http://127.0.0.1:8000"


class QueryClient:
    """Client for interacting with the Finks Naive API."""

    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def query(self, request: AgentPipelineRequest) -> AgentPipelineResponse:
        """Send a query to the API."""
        response = await self.client.post(f"{self.base_url}/agents/query", json=request.model_dump(exclude_none=True))
        response.raise_for_status()
        return AgentPipelineResponse(**response.json())

    async def get_stats(self) -> dict:
        """Get database statistics."""
        response = await self.client.get(f"{self.base_url}/agents/stats")
        response.raise_for_status()
        return response.json()


async def example_basic_query():
    """Example: Basic query for cheap profitable stocks."""
    print("\n=== Example 1: Basic Query ===")

    # Create the request using the Pydantic model
    request = AgentPipelineRequest(query="Find cheap profitable stocks", max_results=5)

    client = QueryClient()
    try:
        response = await client.query(request)

        print(f"Query: {request.query}")
        print(f"Found {response.total_results} results in {response.processing_time_ms:.2f}ms")
        print("\nTop Results:")

        for i, result in enumerate(response.results, 1):
            symbol = result.get("symbol", "N/A")
            exchange = result.get("exchange_acronym", "N/A")
            pe_ratio = result.get("ttm_price_to_earnings_ratio", "N/A")
            profit_margin = result.get("ttm_net_profit_margin", "N/A")

            print(f"  {i}. {symbol} ({exchange})")
            if pe_ratio != "N/A":
                print(f"     P/E Ratio: {pe_ratio:.2f}")
            if profit_margin != "N/A":
                print(f"     Profit Margin: {profit_margin*100:.1f}%")

    finally:
        await client.close()


async def example_refinement_query():
    """Example: Query with refinement."""
    print("\n=== Example 2: Query Refinement ===")

    client = QueryClient()
    try:
        # First query
        request1 = AgentPipelineRequest(query="Find large cap companies", max_results=5)
        response1 = await client.query(request1)
        print(f"Initial query: {request1.query}")
        print(f"Found {response1.total_results} results")

        # Refinement query using previous context
        request2 = AgentPipelineRequest(
            query="only ones in the technology sector", max_results=5, previous_context=response1.query_context
        )
        response2 = await client.query(request2)
        print(f"\nRefinement: {request2.query}")
        print(f"Refined to {response2.total_results} results")

        print("\nRefined Results:")
        for i, result in enumerate(response2.results, 1):
            symbol = result.get("symbol", "N/A")
            exchange = result.get("exchange_acronym", "N/A")
            sector = result.get("company_sector", "N/A")
            market_cap = result.get("market_capitalization", 0)

            print(f"  {i}. {symbol} ({exchange}) - {sector}")
            if market_cap > 0:
                print(f"     Market Cap: ${market_cap/1e9:.2f}B")

    finally:
        await client.close()


async def example_complex_query():
    """Example: Complex query with multiple criteria."""
    print("\n=== Example 3: Complex Query ===")

    request = AgentPipelineRequest(
        query="Find dividend paying technology stocks with PE ratio under 20 and market cap over 10 billion",
        max_results=10,
    )

    client = QueryClient()
    try:
        response = await client.query(request)

        print(f"Query: {request.query}")
        print(f"Found {response.total_results} results")
        print("\nMongoDB Query Generated:")
        import json

        print(json.dumps(response.query_used, indent=2))

        if response.results:
            print("\nTop Results:")
            for i, result in enumerate(response.results[:5], 1):
                symbol = result.get("symbol", "N/A")
                print(f"  {i}. {symbol}")

    finally:
        await client.close()


async def main():
    """Run all examples."""
    # Get stats first
    client = QueryClient()
    try:
        stats = await client.get_stats()
        print(f"Database contains {stats['total_documents']:,} companies")
    finally:
        await client.close()

    # Run examples
    await example_basic_query()
    await example_refinement_query()
    await example_complex_query()


if __name__ == "__main__":
    asyncio.run(main())
