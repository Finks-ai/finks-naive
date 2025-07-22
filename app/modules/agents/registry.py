"""
Agent Registry - Central registry for managing agent instances with builder pattern.
"""

from typing import Dict, Any, Type, Optional, List
from enum import Enum
from dataclasses import dataclass
from loguru import logger


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
    """Registry for managing agent instances and metadata."""
    
    def __init__(self):
        self._agents: Dict[AgentType, AgentInfo] = {}
    
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


# Create singleton instance
agent_registry = AgentRegistry()


# Export convenience functions
def get_agent(agent_type: AgentType) -> Optional[Any]:
    """Get an agent service by type."""
    return agent_registry.get_service(agent_type)


def list_available_agents() -> Dict[str, Dict[str, Any]]:
    """List all available agents."""
    return agent_registry.list_agents()