"""
Agent router for query processing endpoints with optional optimizations.
"""

import os
import time
import asyncio
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional, List
from app.modules.agents.models import AgentPipelineRequest, AgentPipelineResponse
from app.modules.agents.service import agent_orchestrator
from loguru import logger

# Check if optimizations are available
HAS_CACHE = False
HAS_CONCURRENT = False
IS_LAMBDA = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

try:
    from app.core.cache import get_query_cache
    HAS_CACHE = True
except ImportError:
    logger.info("Cache module not available - running without cache endpoints")

try:
    from app.core.concurrent import get_executor
    HAS_CONCURRENT = True
except ImportError:
    logger.info("Concurrent module not available - running sequentially")

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/query", response_model=AgentPipelineResponse)
async def process_query(request: AgentPipelineRequest) -> AgentPipelineResponse:
    """
    Process a natural language query through the multi-agent pipeline.
    
    The pipeline consists of:
    1. Field Extraction: Identify relevant database fields
    2. Instruction Processing: Apply field-specific instructions
    3. Sorting Extraction: Detect sorting intent
    4. Synthesis: Combine interpretations and resolve conflicts
    5. Query Generation: Create MongoDB query
    6. Execution: Run query against database
    
    When optimizations are available:
    - Parallel agent execution where possible
    - Multi-level caching (Memory → MongoDB)
    - Query pattern fingerprinting for cache reuse
    - Connection pooling optimized for Lambda
    - Background cache warming for related queries
    """
    try:
        start_time = time.time()
        logger.info(f"Processing query: {request.query}")
        
        # Process through pipeline (service handles optimization detection)
        result = await agent_orchestrator.process_query(request)
        
        # Log performance metrics
        total_time = (time.time() - start_time) * 1000
        logger.info(f"Query processed in {total_time:.2f}ms, returned {result.total_results} results")
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")


@router.post("/query/batch")
async def process_batch_queries(
    queries: List[str],
    max_results: int = 10
) -> Dict[str, Any]:
    """
    Process multiple queries in batch for efficiency.
    Useful for warming cache or bulk processing.
    """
    try:
        logger.info(f"Processing batch of {len(queries)} queries")
        
        results = []
        processing_times = []
        
        # Process queries concurrently
        tasks = [
            agent_orchestrator.process_query(
                AgentPipelineRequest(query=query, max_results=max_results)
            )
            for query in queries
        ]
        
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                results.append({
                    "query": queries[i],
                    "error": str(result),
                    "success": False
                })
            else:
                results.append({
                    "query": queries[i],
                    "total_results": result.total_results,
                    "processing_time_ms": result.processing_time_ms,
                    "success": True
                })
                processing_times.append(result.processing_time_ms)
        
        avg_time = sum(processing_times) / len(processing_times) if processing_times else 0
        
        return {
            "batch_size": len(queries),
            "successful": len(processing_times),
            "failed": len(queries) - len(processing_times),
            "average_processing_time_ms": avg_time,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error processing batch: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {str(e)}")




@router.get("/stats")
async def get_query_stats() -> Dict[str, Any]:
    """
    Get statistics about the query database, available fields, and cache performance.
    """
    try:
        # Get stats from service (includes cache stats if available)
        stats = await agent_orchestrator.get_query_stats()
        
        # Add feature status
        stats["features"] = {
            "parallel_execution": HAS_CONCURRENT,
            "caching_enabled": HAS_CACHE,
            "lambda_optimized": IS_LAMBDA
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting query stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


if HAS_CACHE:
    @router.delete("/cache")
    async def clear_cache(pattern: Optional[str] = None) -> Dict[str, str]:
        """
        Clear cache entries. If pattern is provided, only clear matching entries.
        
        Note: This endpoint is only available when caching is enabled.
        """
        try:
            cache = get_query_cache()
            
            if pattern:
                # TODO: Implement pattern-based cache clearing
                return {"status": "not_implemented", "message": "Pattern-based clearing not yet implemented"}
            else:
                # Clear all memory cache
                cache._memory_cache.clear()
                cache._cache_stats = {
                    "hits": 0,
                    "misses": 0,
                    "memory_hits": 0,
                    "mongodb_hits": 0
                }
                logger.info("Cache cleared")
                return {"status": "success", "message": "Cache cleared successfully"}
        
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for the agent system.
    """
    health = {
        "status": "healthy",
        "service": "agent_pipeline",
        "features": {
            "parallel_execution": HAS_CONCURRENT,
            "caching": HAS_CACHE,
            "lambda_optimized": IS_LAMBDA
        }
    }
    
    # Include cache health if available
    if HAS_CACHE:
        try:
            cache = get_query_cache()
            cache_stats = cache.get_stats()
            health["cache_health"] = {
                "operational": True,
                "stats": cache_stats
            }
        except Exception as e:
            health["cache_health"] = {
                "operational": False,
                "error": str(e)
            }
    
    return health

