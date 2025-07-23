# Singleton Optimization for Lambda Performance

## Overview

We've implemented a comprehensive singleton pattern using the existing agent registry to optimize Lambda cold starts and container reuse.

## Key Changes

### 1. Centralized Configuration Management

The `AgentRegistry` class now serves as the central hub for:
- **Shared Configurations**: Field mappings, instructions, categories, and unavailable fields
- **AI Agent Instances**: Lazy-loaded Pydantic AI agents

```python
class AgentRegistry:
    # Shared configurations (loaded once per container)
    _field_mappings: Optional[Dict[str, str]] = None
    _available_fields: Optional[List[str]] = None
    _field_instructions: Optional[Dict[str, str]] = None
    _field_categories: Optional[Dict[str, Any]] = None
    _unavailable_fields: Optional[List[str]] = None

    # AI Agent instances (created once per container)
    _ai_agents: Dict[AgentType, Agent] = {}
```

### 2. Service Updates

All agent services now use the registry's shared resources:

```python
# Before: Each service loaded its own configs
class FieldExtractionService:
    def __init__(self):
        self.available_fields = self._load_available_fields()  # File I/O
        self.unavailable_fields = self._load_unavailable_fields()  # File I/O
        self.field_categories = self._load_field_categories()  # File I/O

# After: Services use registry's shared configs
class FieldExtractionService:
    def __init__(self):
        self.available_fields = agent_registry.get_available_fields()  # No I/O
        self.unavailable_fields = agent_registry.get_unavailable_fields()  # No I/O
        self.field_categories = agent_registry.get_field_categories()  # No I/O
        self.ai_agent = agent_registry.get_ai_agent(AgentType.FIELD_EXTRACTION)
```

### 3. Performance Benefits

#### Cold Start Improvements
- **Before**: ~10 second init timeout (loading configs multiple times)
- **After**: Significantly reduced (configs loaded once)

#### Memory Usage
- **Before**: Each service had its own copy of configs and AI agents
- **After**: Single shared instance across all services

#### Concurrent Execution
- No file I/O contention when agents run in parallel
- Shared AI agents are stateless and thread-safe
- Works seamlessly with `ConcurrentExecutor`

### 4. Lambda Container Lifecycle

```
Container Start
    ↓
AgentRegistry initialized
    ↓
Configs loaded once (I/O happens here)
    ↓
First Request
    ↓
AI agents created lazily on first use
    ↓
Subsequent Requests (container reused)
    ↓
Use existing configs and AI agents (no I/O)
```

## Implementation Details

### Registry Methods

- `get_field_mappings()`: Returns shared field mappings
- `get_available_fields()`: Returns list of available fields
- `get_field_instructions()`: Returns field instructions
- `get_field_categories()`: Returns field categories
- `get_unavailable_fields()`: Returns unavailable fields list
- `get_ai_agent(agent_type)`: Gets or creates AI agent instance

### Service Pattern

All services follow this pattern:
1. Get shared configs from registry in `__init__`
2. Get AI agent instance from registry
3. Use instance variables for fast access during request processing

## Testing the Optimization

To verify the optimization works:

```bash
# Deploy to Lambda
cd pulumi
pulumi up

# Monitor cold start performance
aws logs tail "/aws/lambda/dev-finks-screener-lambda" --follow --region ca-central-1
```

Look for:
- Reduced init duration
- "Loaded shared configs" message only once per container
- "Creating AI agent instance" messages only on first use

## Future Enhancements

1. **Pre-warm AI Agents**: Create all agents during init instead of lazy loading
2. **Config Versioning**: Add version checking for config updates
3. **Metrics**: Add CloudWatch metrics for singleton performance
4. **Cache Warming**: Pre-populate common query patterns

## Conclusion

This singleton optimization significantly improves Lambda performance by:
- Reducing cold start times
- Minimizing memory usage
- Eliminating redundant I/O operations
- Enabling efficient concurrent execution

The changes maintain backward compatibility while providing substantial performance gains for production deployments.
