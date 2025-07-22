"""
Pipeline definitions and factory functions.
"""

import os
from typing import List
from loguru import logger

from app.modules.agents.orchestrator import PipelineStep, ExecutionStrategy, step
from app.modules.agents.registry import agent_registry, AgentType

# Import step functions from agents
from app.modules.agents.field_extraction.service import extract_fields_step
from app.modules.agents.instruction_processing.service import process_instructions_step
from app.modules.agents.synthesis.service import synthesize_interpretations_step
from app.modules.agents.query_generation.service import generate_query_step
from app.modules.agents.sorting_extraction.service import extract_sorting_step
from app.modules.agents.steps import execute_database_query


# Feature detection
HAS_CACHE = False
HAS_CONCURRENT = False
IS_LAMBDA = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

try:
    from app.core.cache import get_query_cache, cached_query, cache_field_extraction
    HAS_CACHE = True
except ImportError:
    logger.info("Cache module not available - running without caching")

try:
    from app.core.concurrent import get_executor, get_batcher
    HAS_CONCURRENT = True
except ImportError:
    logger.info("Concurrent module not available - running sequentially")


def validate_required_agents():
    """Validate that all required agents are registered."""
    required_agents = [
        AgentType.FIELD_EXTRACTION,
        AgentType.SORTING_EXTRACTION,
        AgentType.INSTRUCTION_PROCESSING,
        AgentType.SYNTHESIS,
        AgentType.QUERY_GENERATION
    ]
    
    for agent_type in required_agents:
        if not agent_registry.get(agent_type):
            raise RuntimeError(f"Required agent {agent_type.value} is not registered")


def create_sequential_pipeline() -> List[PipelineStep]:
    """Create the sequential pipeline for query processing."""
    validate_required_agents()
    
    return [
        step("extract_fields", extract_fields_step),
        step("extract_sorting", extract_sorting_step),
        step("process_instructions", process_instructions_step, dependencies=["extract_fields"]),
        step("synthesize_interpretations", synthesize_interpretations_step, dependencies=["process_instructions"]),
        step("generate_query", generate_query_step, dependencies=["synthesize_interpretations"]),
        step("execute_database_query", execute_database_query, dependencies=["generate_query", "extract_sorting"])
    ]


def create_parallel_pipeline() -> List[PipelineStep]:
    """Create the optimized parallel pipeline for query processing."""
    validate_required_agents()
    
    return [
        # Parallel extraction phase
        step("extract_fields", extract_fields_step, strategy=ExecutionStrategy.PARALLEL),
        step("extract_sorting", extract_sorting_step, strategy=ExecutionStrategy.PARALLEL),
        
        # Sequential processing phase
        step("process_instructions", process_instructions_step, dependencies=["extract_fields"]),
        step("synthesize_interpretations", synthesize_interpretations_step, dependencies=["process_instructions"]),
        step("generate_query", generate_query_step, dependencies=["synthesize_interpretations"]),
        step("execute_database_query", execute_database_query, dependencies=["generate_query", "extract_sorting"])
    ]


def get_pipeline_for_request(request) -> List[PipelineStep]:
    """Get the appropriate pipeline based on request and system capabilities."""
    # Use parallel pipeline if we have concurrent support and no previous context
    if HAS_CONCURRENT and not request.previous_context:
        return create_parallel_pipeline()
    else:
        return create_sequential_pipeline()


# Export feature flags
__all__ = [
    'create_sequential_pipeline',
    'create_parallel_pipeline',
    'get_pipeline_for_request',
    'HAS_CACHE',
    'HAS_CONCURRENT',
    'IS_LAMBDA'
]