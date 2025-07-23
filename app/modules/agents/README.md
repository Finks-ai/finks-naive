# Multi-Agent Query Processing System

This package implements a sophisticated multi-agent pipeline for converting natural language queries into MongoDB queries for financial stock screening.

## Architecture Overview

The system uses a pipeline of specialized AI agents, each responsible for a specific aspect of query understanding and transformation:

```
User Query → Field Extraction → Instruction Processing → Synthesis → Query Generation → MongoDB Query
                     ↓
              Sorting Extraction
```

## Agents

### 1. Field Extraction Agent (`field_extraction/`)
- **Purpose**: Identifies relevant database fields from natural language queries
- **Example**: "cheap tech stocks" → identifies `company_sector`, `ttm_price_to_earnings_ratio`
- **Key Features**:
  - Category-aware field selection
  - Confidence scoring
  - Handles multi-select vs single-select categories

### 2. Instruction Processing Agent (`instruction_processing/`)
- **Purpose**: Maps extracted fields to specific filter values using field-specific instructions
- **Example**: "cheap" + `ttm_price_to_earnings_ratio` → "Under 10"
- **Configuration**: Uses `settings/field_instructions.yaml` for interpretation rules

### 3. Synthesis Agent (`synthesis/`)
- **Purpose**: Combines field interpretations and resolves conflicts
- **Features**:
  - Prioritizes fields based on query intent
  - Resolves conflicting interpretations
  - Validates categorical values
  - Handles query refinements

### 4. Query Generation Agent (`query_generation/`)
- **Purpose**: Converts synthesized interpretations into MongoDB queries
- **Special Handling**:
  - Automatic US exchange filtering when no country specified
  - Excludes negative valuation ratios for "less than X" filters (where X > 0)
  - Percentage to decimal conversion
  - JSON format validation

### 5. Sorting Extraction Agent (`sorting_extraction/`)
- **Purpose**: Detects sorting intent from queries
- **Example**: "top dividend stocks" → sort by `ttm_dividend_yield` DESC

## Pipeline Execution

The pipeline is orchestrated by the `AgentOrchestrator` class which supports:
- Parallel execution (e.g., field extraction + sorting extraction)
- Sequential dependencies
- Error handling and retries
- Performance tracking

## Usage

### Basic Query
```python
from app.modules.agents.models import AgentPipelineRequest
from app.modules.agents.service import agent_orchestrator

request = AgentPipelineRequest(
    query="Find undervalued tech stocks with good dividends",
    max_results=10
)

response = await agent_orchestrator.process_query(request)
```

### Query Refinement
```python
# First query
response1 = await agent_orchestrator.process_query(request1)

# Refinement using previous context
request2 = AgentPipelineRequest(
    query="only large cap ones",
    previous_context=response1.query_context,
    max_results=10
)
response2 = await agent_orchestrator.process_query(request2)
```

## Configuration

### Field Instructions (`settings/field_instructions.yaml`)
Defines how natural language maps to field values:
```yaml
ttm_price_to_earnings_ratio: |
  • If user requests 'undervalued', 'cheap', or 'value', set the filter to Under 10.
  • If user requests 'fair value', apply > 15 and < 20 in the same filter.
```

### Constants (`app/core/constants.py`)
- `US_EXCHANGES`: Default exchanges when no country specified
- `VALUATION_RATIO_FIELDS`: Fields that exclude negative values for "less than" filters

## Key Features

### 1. Intelligent Valuation Ratio Handling
When users search for "P/E < 10", the system automatically adds `> 0` constraint because negative P/E ratios are meaningless for valuation analysis.

### 2. Categorical Value Validation
Ensures categorical fields (like `company_sector`) only use valid values from the database.

### 3. Query Caching
Caches query results to improve performance for repeated queries (when enabled).

### 4. Parallel Processing
Field extraction and sorting extraction run in parallel for better performance.

## Adding New Agents

1. Create a new directory under `app/modules/agents/`
2. Implement the agent with:
   - `models.py`: Pydantic models for input/output
   - `prompts.py`: System and user prompts
   - `guidelines.py`: Agent-specific guidelines
   - `service.py`: Business logic and step function
3. Register in `agents.py`
4. Add to the pipeline in `pipeline.py`

## Error Handling

- Each agent has retry logic for AI model errors
- Failed steps are logged with detailed error information
- Pipeline continues gracefully when non-critical steps fail

## Performance Considerations

- Agents are initialized once and reused (singleton pattern)
- MongoDB queries are optimized with proper indexing
- Parallel execution where possible
- Result caching for repeated queries

## Testing

```bash
# Run the example client
uv run python example_client.py

# Test specific queries
uv run python -c "
import asyncio
from app.modules.agents.models import AgentPipelineRequest
from app.modules.agents.service import agent_orchestrator

async def test():
    request = AgentPipelineRequest(query='Your test query here')
    response = await agent_orchestrator.process_query(request)
    print(response.query_used)

asyncio.run(test())
"
```

## Debugging

Enable debug logging to see the full pipeline execution:
```python
import logging
logging.getLogger("app.modules.agents").setLevel(logging.DEBUG)
