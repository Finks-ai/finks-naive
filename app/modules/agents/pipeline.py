"""
Pipeline definitions and factory functions.
"""

import importlib.util
import os
from typing import Any

from loguru import logger

# Import step functions from agents
from app.modules.agents.field_extraction.service import extract_fields_step
from app.modules.agents.instruction_processing.service import process_instructions_step
from app.modules.agents.orchestrator import ExecutionStrategy, PipelineStep, step
from app.modules.agents.query_generation.service import generate_query_step
from app.modules.agents.registry import AgentType, agent_registry
from app.modules.agents.sorting_extraction.service import extract_sorting_step
from app.modules.agents.steps import execute_database_query
from app.modules.agents.synthesis.service import synthesize_interpretations_step

# Feature detection
HAS_CACHE = False
HAS_CONCURRENT = False
IS_LAMBDA = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

# Check cache availability
if importlib.util.find_spec("app.core.cache") is not None:
    HAS_CACHE = True
else:
    HAS_CACHE = False
    logger.info("Cache module not available - running without caching")

# Check concurrent availability
if importlib.util.find_spec("app.core.concurrent") is not None:
    HAS_CONCURRENT = True
else:
    HAS_CONCURRENT = False
    logger.info("Concurrent module not available - running sequentially")


def validate_required_agents() -> None:
    """Validate that all required agents are registered."""
    required_agents = [
        AgentType.FIELD_EXTRACTION,
        AgentType.SORTING_EXTRACTION,
        AgentType.INSTRUCTION_PROCESSING,
        AgentType.SYNTHESIS,
        AgentType.QUERY_GENERATION,
    ]

    for agent_type in required_agents:
        if not agent_registry.get(agent_type):
            raise RuntimeError(f"Required agent {agent_type.value} is not registered")


def create_sequential_pipeline() -> list[PipelineStep]:
    """Create the sequential pipeline for query processing."""
    validate_required_agents()

    return [
        step("extract_fields", extract_fields_step),
        step("extract_sorting", extract_sorting_step),
        step("process_instructions", process_instructions_step, dependencies=["extract_fields"]),
        step("synthesize_interpretations", synthesize_interpretations_step, dependencies=["process_instructions"]),
        step("generate_query", generate_query_step, dependencies=["synthesize_interpretations"]),
        step("execute_database_query", execute_database_query, dependencies=["generate_query", "extract_sorting"]),
    ]


def create_parallel_pipeline() -> list[PipelineStep]:
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
        step("execute_database_query", execute_database_query, dependencies=["generate_query", "extract_sorting"]),
    ]


def get_pipeline_for_request(request: Any) -> list[PipelineStep]:
    """Get the appropriate pipeline based on request and system capabilities."""
    # Use parallel pipeline if we have concurrent support and no previous context
    if HAS_CONCURRENT and not request.previous_context:
        return create_parallel_pipeline()
    else:
        return create_sequential_pipeline()


# Export feature flags
__all__ = [
    "HAS_CACHE",
    "HAS_CONCURRENT",
    "IS_LAMBDA",
    "create_parallel_pipeline",
    "create_sequential_pipeline",
    "get_pipeline_for_request",
]
