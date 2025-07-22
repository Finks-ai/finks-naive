"""
Agent registration and initialization.
"""

from loguru import logger
from .registry import agent_registry, AgentType
from .field_extraction import field_extraction_service
from .instruction_processing import instruction_processing_service
from .synthesis import synthesis_service
from .query_generation import query_generation_service
from .sorting_extraction import sorting_extraction_service


def register_agents():
    """Register all agents using the builder pattern."""
    from app.modules.agents.field_extraction.models import FieldExtractionRequest, FieldExtractionResponse
    from app.modules.agents.instruction_processing.models import InstructionProcessingRequest, InstructionProcessingResponse
    from app.modules.agents.synthesis.models import SynthesisRequest, SynthesisResponse
    from app.modules.agents.query_generation.models import QueryGenerationRequest, QueryGenerationResponse
    from app.modules.agents.sorting_extraction.models import SortingIntentRequest, SortingIntentResponse
    
    agent_registry.clear()
    
    (
        agent_registry.builder()
        .add_agent(AgentType.FIELD_EXTRACTION)
        .with_name("Field Extraction Agent")
        .with_description("Identifies relevant database fields from natural language queries")
        .with_service(field_extraction_service)
        .with_models(FieldExtractionRequest, FieldExtractionResponse)
        
        .add_agent(AgentType.INSTRUCTION_PROCESSING)
        .with_name("Instruction Processing Agent")
        .with_description("Applies field instructions and context-aware interpretation")
        .with_service(instruction_processing_service)
        .with_models(InstructionProcessingRequest, InstructionProcessingResponse)
        .with_dependency(AgentType.FIELD_EXTRACTION)
        
        .add_agent(AgentType.SYNTHESIS)
        .with_name("Synthesis Agent")
        .with_description("Combines field interpretations and resolves conflicts")
        .with_service(synthesis_service)
        .with_models(SynthesisRequest, SynthesisResponse)
        .with_dependencies([AgentType.FIELD_EXTRACTION, AgentType.INSTRUCTION_PROCESSING])
        
        .add_agent(AgentType.QUERY_GENERATION)
        .with_name("Query Generation Agent")
        .with_description("Converts unified interpretation into MongoDB queries")
        .with_service(query_generation_service)
        .with_models(QueryGenerationRequest, QueryGenerationResponse)
        .with_dependency(AgentType.SYNTHESIS)
        
        .add_agent(AgentType.SORTING_EXTRACTION)
        .with_name("Sorting Extraction Agent")
        .with_description("Identifies sorting requirements from natural language queries")
        .with_service(sorting_extraction_service)
        .with_models(SortingIntentRequest, SortingIntentResponse)
        
        .build()
    )
    
    logger.info(f"Registered {len(agent_registry.list_agents())} agents")


# Register all agents at module initialization
register_agents()