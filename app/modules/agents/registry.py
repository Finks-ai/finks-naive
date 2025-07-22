"""
Agent Registry - Central registry for managing agent instances with builder pattern.
Also holds shared configurations and AI agent instances as singletons.
"""

from typing import Dict, Any, Type, Optional, List
from enum import Enum
from dataclasses import dataclass
from loguru import logger
from pydantic_ai import Agent


class AgentType(str, Enum):
    """Enumeration of available agent types."""
    FIELD_EXTRACTION = "field_extraction"
    INSTRUCTION_PROCESSING = "instruction_processing"
    SYNTHESIS = "synthesis"
    QUERY_GENERATION = "query_generation"
    SORTING_EXTRACTION = "sorting_extraction"


@dataclass
class AgentInfo:
    """Information about a registered agent."""
    name: str
    description: str
    service_instance: Any
    input_model: Type[Any]
    output_model: Type[Any]
    dependencies: List[AgentType] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class AgentRegistryBuilder:
    """Builder for constructing an agent registry with fluent interface."""
    
    def __init__(self, registry: Optional['AgentRegistry'] = None):
        self._registry = registry if registry else AgentRegistry()
        self._current_agent_type: Optional[AgentType] = None
        self._current_info = {}
        self._current_dependencies = []
    
    def add_agent(self, agent_type: AgentType) -> 'AgentRegistryBuilder':
        """Start adding a new agent."""
        # Finalize previous agent if any
        self._finalize_current_agent()
        
        self._current_agent_type = agent_type
        self._current_info = {}
        self._current_dependencies = []
        return self
    
    def with_name(self, name: str) -> 'AgentRegistryBuilder':
        """Set the agent name."""
        if not self._current_agent_type:
            raise ValueError("Must call add_agent() before with_name()")
        self._current_info['name'] = name
        return self
    
    def with_description(self, description: str) -> 'AgentRegistryBuilder':
        """Set the agent description."""
        if not self._current_agent_type:
            raise ValueError("Must call add_agent() before with_description()")
        self._current_info['description'] = description
        return self
    
    def with_service(self, service_instance: Any) -> 'AgentRegistryBuilder':
        """Set the agent service instance."""
        if not self._current_agent_type:
            raise ValueError("Must call add_agent() before with_service()")
        self._current_info['service_instance'] = service_instance
        return self
    
    def with_models(self, input_model: Type[Any], output_model: Type[Any]) -> 'AgentRegistryBuilder':
        """Set the agent input and output models."""
        if not self._current_agent_type:
            raise ValueError("Must call add_agent() before with_models()")
        self._current_info['input_model'] = input_model
        self._current_info['output_model'] = output_model
        return self
    
    def with_dependency(self, dependency: AgentType) -> 'AgentRegistryBuilder':
        """Add a dependency to the current agent."""
        if not self._current_agent_type:
            raise ValueError("Must call add_agent() before with_dependency()")
        self._current_dependencies.append(dependency)
        return self
    
    def with_dependencies(self, dependencies: List[AgentType]) -> 'AgentRegistryBuilder':
        """Set multiple dependencies for the current agent."""
        if not self._current_agent_type:
            raise ValueError("Must call add_agent() before with_dependencies()")
        self._current_dependencies.extend(dependencies)
        return self
    
    def _finalize_current_agent(self):
        """Finalize and register the current agent if any."""
        if self._current_agent_type and all(
            key in self._current_info for key in 
            ['name', 'description', 'service_instance', 'input_model', 'output_model']
        ):
            agent_info = AgentInfo(
                name=self._current_info['name'],
                description=self._current_info['description'],
                service_instance=self._current_info['service_instance'],
                input_model=self._current_info['input_model'],
                output_model=self._current_info['output_model'],
                dependencies=self._current_dependencies.copy()
            )
            self._registry.register(self._current_agent_type, agent_info)
    
    def build(self) -> 'AgentRegistry':
        """Build and return the agent registry."""
        # Finalize any pending agent
        self._finalize_current_agent()
        
        # Validate all dependencies
        for agent_type in self._registry._agents:
            if not self._registry.validate_dependencies(agent_type):
                logger.warning(f"Agent {agent_type.value} has invalid dependencies")
        
        # Don't log here - the finalize method already logged each registration
        return self._registry


class AgentRegistry:
    """Registry for managing agent instances and metadata.
    
    Also holds shared configurations and AI agent instances as class attributes
    for Lambda container reuse.
    """
    
    # Shared configurations (loaded once per container)
    _field_mappings: Optional[Dict[str, str]] = None
    _available_fields: Optional[List[str]] = None
    _field_instructions: Optional[Dict[str, str]] = None
    _field_categories: Optional[Dict[str, Any]] = None
    _unavailable_fields: Optional[List[str]] = None
    
    # AI Agent instances (created once per container)
    _ai_agents: Dict[AgentType, Agent] = {}
    
    def __init__(self):
        self._agents: Dict[AgentType, AgentInfo] = {}
        # Initialize shared configurations on first instance
        if AgentRegistry._field_mappings is None:
            self._initialize_shared_configs()
    
    def builder(self) -> AgentRegistryBuilder:
        """Create a builder for this registry instance."""
        return AgentRegistryBuilder(self)
    
    def register(self, agent_type: AgentType, agent_info: AgentInfo) -> None:
        """Register an agent in the registry."""
        self._agents[agent_type] = agent_info
        logger.debug(f"Registered agent: {agent_type.value}")
    
    def get(self, agent_type: AgentType) -> Optional[AgentInfo]:
        """Get agent info by type."""
        return self._agents.get(agent_type)
    
    def get_service(self, agent_type: AgentType) -> Optional[Any]:
        """Get agent service instance by type."""
        agent_info = self._agents.get(agent_type)
        return agent_info.service_instance if agent_info else None
    
    def list_agents(self) -> Dict[str, Dict[str, Any]]:
        """List all registered agents with their metadata."""
        return {
            agent_type.value: {
                "name": info.name,
                "description": info.description,
                "input_model": info.input_model.__name__,
                "output_model": info.output_model.__name__,
                "dependencies": [dep.value for dep in info.dependencies]
            }
            for agent_type, info in self._agents.items()
        }
    
    def get_execution_order(self) -> List[AgentType]:
        """Get the recommended execution order based on dependencies."""
        # For now, return a fixed order. Could be enhanced with topological sort
        return [
            AgentType.FIELD_EXTRACTION,
            AgentType.SORTING_EXTRACTION,  # Can run in parallel with field extraction
            AgentType.INSTRUCTION_PROCESSING,
            AgentType.SYNTHESIS,
            AgentType.QUERY_GENERATION
        ]
    
    def validate_dependencies(self, agent_type: AgentType) -> bool:
        """Validate that all dependencies for an agent are registered."""
        agent_info = self._agents.get(agent_type)
        if not agent_info:
            return False
        
        for dependency in agent_info.dependencies:
            if dependency not in self._agents:
                logger.error(f"Missing dependency {dependency.value} for agent {agent_type.value}")
                return False
        
        return True
    
    def clear(self) -> None:
        """Clear all registered agents."""
        self._agents.clear()
        logger.debug("Cleared agent registry")
    
    def _initialize_shared_configs(self):
        """Initialize shared configurations once per container."""
        from app.core.config_loader import load_config
        
        logger.info("Initializing shared agent configurations...")
        
        try:
            # Load field mappings
            config = load_config("field_mappings")
            AgentRegistry._field_mappings = config.get("field_mappings", {})
            AgentRegistry._available_fields = list(AgentRegistry._field_mappings.keys())
            
            # Load field instructions
            AgentRegistry._field_instructions = load_config("field_instructions")
            
            # Load field categories
            AgentRegistry._field_categories = load_config("field_categories")
            
            # Load unavailable fields
            config = load_config("unavailable_fields")
            AgentRegistry._unavailable_fields = config.get("unavailable_fields", [])
            
            logger.info(f"Loaded shared configs: {len(AgentRegistry._available_fields)} available fields, "
                       f"{len(AgentRegistry._field_instructions)} instructions, "
                       f"{len(AgentRegistry._unavailable_fields)} unavailable fields")
        except Exception as e:
            logger.error(f"Failed to initialize shared configs: {e}")
            # Set defaults
            AgentRegistry._field_mappings = {}
            AgentRegistry._available_fields = []
            AgentRegistry._field_instructions = {}
            AgentRegistry._field_categories = {"categories": {}, "field_to_category": {}}
            AgentRegistry._unavailable_fields = []
    
    @classmethod
    def get_field_mappings(cls) -> Dict[str, str]:
        """Get shared field mappings."""
        return cls._field_mappings or {}
    
    @classmethod
    def get_available_fields(cls) -> List[str]:
        """Get shared available fields list."""
        return cls._available_fields or []
    
    @classmethod
    def get_field_instructions(cls) -> Dict[str, str]:
        """Get shared field instructions."""
        return cls._field_instructions or {}
    
    @classmethod
    def get_field_categories(cls) -> Dict[str, Any]:
        """Get shared field categories."""
        return cls._field_categories or {"categories": {}, "field_to_category": {}}
    
    @classmethod
    def get_unavailable_fields(cls) -> List[str]:
        """Get shared unavailable fields list."""
        return cls._unavailable_fields or []
    
    @classmethod
    def get_ai_agent(cls, agent_type: AgentType, create_if_missing: bool = True) -> Optional[Agent]:
        """Get or create an AI agent instance.
        
        Args:
            agent_type: Type of agent to get
            create_if_missing: Whether to create the agent if it doesn't exist
            
        Returns:
            The AI agent instance or None
        """
        if agent_type not in cls._ai_agents and create_if_missing:
            cls._create_ai_agent(agent_type)
        return cls._ai_agents.get(agent_type)
    
    @classmethod
    def _create_ai_agent(cls, agent_type: AgentType) -> None:
        """Create an AI agent instance for the given type."""
        from app.core.config import get_settings
        settings = get_settings()
        
        logger.info(f"Creating AI agent instance for {agent_type.value}")
        
        try:
            if agent_type == AgentType.FIELD_EXTRACTION:
                from .field_extraction.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
                from .field_extraction.guidelines import GUIDELINES
                from .field_extraction.models import FieldExtractionResponse
                
                cls._ai_agents[agent_type] = Agent(
                    model=settings.GEMINI_MODEL,
                    result_type=FieldExtractionResponse,
                    system_prompt=SYSTEM_PROMPT.format(guidelines=GUIDELINES)
                )
                
            elif agent_type == AgentType.INSTRUCTION_PROCESSING:
                from .instruction_processing.prompts import SYSTEM_PROMPT
                from .instruction_processing.guidelines import GUIDELINES
                from .instruction_processing.models import InstructionProcessingResponse
                
                cls._ai_agents[agent_type] = Agent(
                    model=settings.GEMINI_MODEL,
                    result_type=InstructionProcessingResponse,
                    system_prompt=SYSTEM_PROMPT.format(guidelines=GUIDELINES)
                )
                
            elif agent_type == AgentType.SORTING_EXTRACTION:
                from .sorting_extraction.prompts import SYSTEM_PROMPT
                from .sorting_extraction.guidelines import GUIDELINES
                from .sorting_extraction.models import SortingIntentResponse
                
                cls._ai_agents[agent_type] = Agent(
                    model=settings.GEMINI_MODEL,
                    result_type=SortingIntentResponse,
                    system_prompt=SYSTEM_PROMPT.format(guidelines=GUIDELINES)
                )
                
            elif agent_type == AgentType.SYNTHESIS:
                from .synthesis.prompts import SYSTEM_PROMPT
                from .synthesis.guidelines import GUIDELINES
                from .synthesis.models import SynthesisResponse
                from app.core.constants import US_EXCHANGES
                
                cls._ai_agents[agent_type] = Agent(
                    model=settings.GEMINI_MODEL,
                    result_type=SynthesisResponse,
                    system_prompt=SYSTEM_PROMPT.format(
                        guidelines=GUIDELINES,
                        us_exchanges=', '.join(US_EXCHANGES)
                    )
                )
                
            elif agent_type == AgentType.QUERY_GENERATION:
                from .query_generation.prompts import SYSTEM_PROMPT
                from .query_generation.guidelines import GUIDELINES
                from .query_generation.models import QueryGenerationResponse
                
                cls._ai_agents[agent_type] = Agent(
                    model=settings.GEMINI_MODEL,
                    result_type=QueryGenerationResponse,
                    system_prompt=SYSTEM_PROMPT.format(guidelines=GUIDELINES)
                )
                
            logger.info(f"Successfully created AI agent for {agent_type.value}")
            
        except Exception as e:
            logger.error(f"Failed to create AI agent for {agent_type.value}: {e}")


# Create singleton instance
agent_registry = AgentRegistry()


# Export convenience functions
def get_agent(agent_type: AgentType) -> Optional[Any]:
    """Get an agent service by type."""
    return agent_registry.get_service(agent_type)


def list_available_agents() -> Dict[str, Dict[str, Any]]:
    """List all available agents."""
    return agent_registry.list_agents()