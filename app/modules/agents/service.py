"""
Agent Pipeline Service - Orchestrates multi-agent query processing.
"""

import time
from typing import Any

from loguru import logger

from app.core.database import get_db_service
from app.core.retry import retry_on_ai_errors
from app.modules.agents.models import (
    AgentPipelineRequest,
    AgentPipelineResponse,
    PreviousQueryContext,
    SortingIntentResponse,
)
from app.modules.agents.orchestrator import AgentOrchestrator, StepResult
from app.modules.agents.pipeline import HAS_CACHE, HAS_CONCURRENT, IS_LAMBDA, get_pipeline_for_request
from app.modules.agents.registry import agent_registry


class AgentPipelineService:
    """Service that manages the agent pipeline execution."""

    def __init__(self) -> None:
        self.orchestrator = AgentOrchestrator(agent_registry)

    @retry_on_ai_errors(max_retries=3)
    async def process_query(self, request: AgentPipelineRequest) -> AgentPipelineResponse:
        """Process a query through the agent pipeline."""
        start_time = time.time()

        # Check cache first
        cache_info = None
        if HAS_CACHE and not request.previous_context:
            cache_info = await self._check_cache(request)
            if cache_info and cache_info.get("result"):
                return AgentPipelineResponse(**cache_info["result"])

        # Prepare context
        context = {"request": request, "use_cache": HAS_CACHE and not request.previous_context}

        # Get appropriate pipeline
        pipeline = get_pipeline_for_request(request)

        # Execute pipeline
        try:
            results = await self.orchestrator.execute_pipeline(pipeline, context, timeout=30.0)

            # Build response
            response = self._build_response(request, results, start_time)

            # Cache result if applicable
            if cache_info and cache_info.get("key") and HAS_CACHE and not request.previous_context:
                await self._cache_result(cache_info["key"], response)

            return response

        except Exception as e:
            logger.error(f"Error in agent pipeline: {e!s}")
            raise

    async def get_query_stats(self) -> dict[str, Any]:
        """Get statistics about the query system."""
        try:
            db_service = get_db_service()
            db = db_service.get_database()
            collection = db["master_search"]

            total_docs = collection.count_documents({})
            sample_doc = collection.find_one()

            stats = {
                "total_documents": total_docs,
                "sample_fields": list(sample_doc.keys()) if sample_doc else [],
                "collection_name": "master_search",
                "registered_agents": agent_registry.list_agents(),
                "features": {"parallel_execution": HAS_CONCURRENT, "caching": HAS_CACHE, "lambda_optimized": IS_LAMBDA},
            }

            if HAS_CACHE:
                from app.core.cache import get_query_cache

                cache = get_query_cache()
                stats["cache_performance"] = cache.get_stats()

            return stats

        except Exception as e:
            logger.error(f"Error getting query stats: {e!s}")
            return {"error": str(e)}

    async def _check_cache(self, request: AgentPipelineRequest) -> dict[str, Any]:
        """Check cache for existing results."""
        try:
            from app.core.cache import get_query_cache

            cache = get_query_cache()
            cache_key = cache.get_query_fingerprint(request.query, {"max_results": request.max_results})

            cached_result = await cache.get_cached_result(cache_key)
            if cached_result:
                logger.info(f"Returning cached result for query: {request.query}")
                return {"key": cache_key, "result": cached_result}

            return {"key": cache_key, "result": None}
        except Exception as e:
            logger.warning(f"Cache check failed: {e}")
            return {"key": None, "result": None}

    async def _cache_result(self, cache_key: str, response: AgentPipelineResponse) -> None:
        """Cache the response."""
        try:
            from app.core.cache import get_query_cache

            cache = get_query_cache()
            await cache.set_cached_result(cache_key, response.dict(), ttl_seconds=3600)
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")

    def _build_response(
        self, request: AgentPipelineRequest, results: dict[str, StepResult], start_time: float
    ) -> AgentPipelineResponse:
        """Build the response from pipeline execution results."""
        processing_time = (time.time() - start_time) * 1000

        # Extract results
        sorting_intent = results["extract_sorting"].result
        synthesis_result = results["synthesize_interpretations"].result
        query_result = results["generate_query"].result
        db_results = results["execute_database_query"].result

        # Build processing chain for debugging
        processing_chain = self._build_processing_chain(results)

        # Create context for refinements
        query_context = PreviousQueryContext(
            query=request.query,
            mongodb_query=query_result.mongodb_query,
            field_priorities=synthesis_result.field_priorities,
            unified_interpretation=synthesis_result.unified_interpretation,
            sorting_intent=(
                SortingIntentResponse(
                    has_sorting=sorting_intent.has_sorting,
                    sort_field=sorting_intent.sort_field,
                    sort_direction=sorting_intent.sort_direction,
                    confidence=sorting_intent.confidence,
                    reasoning=sorting_intent.reasoning,
                    sorting_phrase=sorting_intent.sorting_phrase,
                )
                if sorting_intent.has_sorting
                else None
            ),
        )

        return AgentPipelineResponse(
            results=db_results,
            query_used=query_result.mongodb_query,
            processing_chain=processing_chain,
            total_results=len(db_results),
            processing_time_ms=processing_time,
            query_context=query_context,
        )

    def _build_processing_chain(self, results: dict[str, StepResult]) -> dict[str, Any]:
        """Build the processing chain for debugging."""
        field_extraction_result = results["extract_fields"].result
        sorting_intent = results["extract_sorting"].result
        instruction_result = results["process_instructions"].result
        synthesis_result = results["synthesize_interpretations"].result
        query_result = results["generate_query"].result

        return {
            "field_extraction": {
                "relevant_fields": field_extraction_result.relevant_fields,
                "confidence": field_extraction_result.confidence,
                "reasoning": field_extraction_result.reasoning,
                "duration_ms": results["extract_fields"].duration_ms,
            },
            "sorting_extraction": {
                "has_sorting": sorting_intent.has_sorting,
                "sort_field": sorting_intent.sort_field,
                "sort_direction": sorting_intent.sort_direction,
                "confidence": sorting_intent.confidence,
                "reasoning": sorting_intent.reasoning,
                "duration_ms": results["extract_sorting"].duration_ms,
            },
            "instruction_processing": {
                "field_interpretations": {
                    fi.field_name: fi.interpretation for fi in instruction_result.field_interpretations
                },
                "processing_notes": instruction_result.processing_notes,
                "duration_ms": results["process_instructions"].duration_ms,
            },
            "synthesis": {
                "unified_interpretation": synthesis_result.unified_interpretation,
                "field_priorities": {fp.field_name: fp.priority for fp in synthesis_result.field_priorities},
                "conflicts_resolved": synthesis_result.conflicts_resolved,
                "duration_ms": results["synthesize_interpretations"].duration_ms,
            },
            "query_generation": {
                "mongodb_query": query_result.mongodb_query,
                "query_explanation": query_result.query_explanation,
                "estimated_results": query_result.estimated_results,
                "duration_ms": results["generate_query"].duration_ms,
            },
        }


# Import agent registration (this triggers registration on import)

# Create the main service instance
agent_orchestrator = AgentPipelineService()

# Export
__all__ = ["AgentPipelineService", "agent_orchestrator", "agent_registry"]
