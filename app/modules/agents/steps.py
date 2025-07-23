"""
Pipeline step functions - Database execution and other utility steps.
"""

from typing import Any

import pymongo
from loguru import logger

from app.core.database import get_db_service
from app.modules.agents.orchestrator import StepResult


async def execute_database_query(context: dict[str, Any], results: dict[str, StepResult]) -> Any:
    """Execute the generated query against the database."""
    request = context["request"]
    query_result = results["generate_query"].result
    sorting_intent = results["extract_sorting"].result

    logger.info("Executing query against database")

    db_service = get_db_service()
    db = db_service.get_database()
    collection = db["master_search"]

    # Apply caching if available
    cache_key = None
    if context.get("use_cache", False):
        try:
            from app.core.cache import get_query_cache

            cache = get_query_cache()
            cache_key = f"mongo:{cache.get_query_fingerprint(str(query_result.mongodb_query))}"

            cached_results = await cache.get_cached_result(cache_key, ["memory"])
            if cached_results:
                logger.debug("MongoDB results cache hit")
                return cached_results.get("results", [])[: request.max_results]
        except ImportError:
            pass

    # Execute query
    cursor = collection.find(query_result.mongodb_query)

    # Apply sorting using pymongo constants
    if sorting_intent and sorting_intent.has_sorting and sorting_intent.sort_field:
        # Use pymongo constants for sort direction
        sort_direction = pymongo.DESCENDING if sorting_intent.sort_direction == "desc" else pymongo.ASCENDING
        sort_direction_name = "DESCENDING" if sorting_intent.sort_direction == "desc" else "ASCENDING"

        logger.info(f"Applying sort: {sorting_intent.sort_field} {sort_direction_name} (pymongo.{sort_direction_name})")
        cursor = cursor.sort(sorting_intent.sort_field, sort_direction)

    # Apply limit
    cursor = cursor.limit(request.max_results)

    # Collect results
    results_list = []
    for doc in cursor:
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        results_list.append(doc)

    # Cache results if available
    if cache_key and context.get("use_cache", False) and results_list:
        try:
            from app.core.cache import get_query_cache

            cache = get_query_cache()
            await cache.set_cached_result(
                cache_key, {"results": results_list}, ttl_seconds=300, cache_levels=["memory"]
            )
        except ImportError:
            pass

    logger.info(f"Query returned {len(results_list)} results")
    return results_list
