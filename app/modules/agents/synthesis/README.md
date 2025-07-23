# Synthesis Agent

The Synthesis Agent is the third stage in the multi-agent pipeline, responsible for combining field interpretations from the Instruction Processing Agent and resolving any conflicts or ambiguities.

## Purpose

This agent takes individual field interpretations and creates a unified, coherent interpretation of the user's query. It resolves conflicts between fields, prioritizes them based on importance to the query, and validates categorical values to ensure query accuracy.

## How It Works

### Input
- Original user query
- Field interpretations from Instruction Processing Agent
- Previous query context (for refinements)
- Categorical value constraints

### Output
- Unified interpretation (natural language summary)
- Field priorities (ordered by importance)
- Conflicts resolved (list of decisions made)

## Example Transformations

### Basic Synthesis
**Query**: "Find cheap profitable tech stocks"

**Input Field Interpretations**:
- `company_sector`: "Technology"
- `ttm_price_to_earnings_ratio`: "Under 10"
- `ttm_net_profit_margin`: "Positive > 0%"

**Unified Output**:
```
"Looking for technology sector companies with P/E ratio under 10
and positive profit margins to identify undervalued profitable tech stocks"
```

**Field Priorities**:
1. `company_sector` (essential filter)
2. `ttm_price_to_earnings_ratio` (primary valuation metric)
3. `ttm_net_profit_margin` (quality filter)

### Conflict Resolution Example
**Query**: "Best value energy stocks"

**Potential Conflict**: Multiple valuation metrics available
- `ttm_price_to_earnings_ratio`: "Under 10"
- `ttm_price_to_book_ratio`: "Under 1"
- `ttm_ev_to_ebitda`: "Under 5"

**Resolution**: Synthesizes all metrics with P/E as primary (priority 1) and others as supporting filters

## Key Features

### 1. Conflict Resolution
The agent handles various types of conflicts:

#### Multiple Valuation Metrics
When multiple valuation fields are present:
- Identifies primary metric based on query emphasis
- Includes complementary metrics at lower priorities
- Notes resolution in `conflicts_resolved`

#### Overlapping Concepts
Example: "large profitable companies"
- `market_capitalization`: Large-cap filter
- `ttm_net_profit_margin`: Profitability filter
- Both included without conflict

#### Contradictory Filters
Example: "cheap stocks with high P/E"
- Identifies logical contradiction
- Resolves based on primary intent
- Documents resolution reasoning

### 2. Field Prioritization
Assigns priority scores (1 = highest) based on:
- **Query emphasis**: Fields directly mentioned get higher priority
- **Logical dependencies**: Sector before sub-filters
- **User intent**: Primary goal vs. additional criteria

### 3. Categorical Value Validation
Validates and corrects categorical values:
```python
# Example validation
Input: "company_sector: Tech"  # Invalid
Output: "company_sector: Technology"  # Corrected to valid value
```

Supported categorical fields:
- `company_sector`: Must match exact sector names
- `exchange_acronym`: Must be valid exchange codes
- Other fields as defined in configuration

### 4. Query Refinement Handling
For follow-up queries:
- Preserves context from previous query
- Merges new interpretations with existing ones
- Adjusts priorities to emphasize new criteria
- Handles "only" and "also" modifiers

## Implementation Details

### Models (`models.py`)
```python
class SynthesisRequest(BaseModel):
    query: str
    field_interpretations: List[FieldInterpretation]
    previous_context: Optional[PreviousContext] = None

class SynthesisResponse(BaseModel):
    unified_interpretation: str
    field_priorities: List[FieldPriority]
    conflicts_resolved: List[str]

class FieldPriority(BaseModel):
    field_name: str
    priority: int  # 1 = highest priority
```

### Service Logic (`service.py`)

#### Main Synthesis Flow
1. **Validation**: Check categorical values against valid lists
2. **Conflict Detection**: Identify overlapping/contradicting fields
3. **Priority Assignment**: Order fields by importance
4. **Unification**: Create coherent natural language summary

#### Categorical Validation
```python
def _validate_categorical_value(self, field_name: str, user_value: str) -> bool:
    """Validate if a categorical value is in the valid list."""
    # Handles format "field_name: value" by extracting just the value
    # Checks against valid values from registry
    # Returns validation warnings if invalid
```

### Prompts (`prompts.py`)
The system prompt instructs the agent to:
- Analyze relationships between fields
- Resolve conflicts logically
- Prioritize based on query intent
- Create clear unified interpretations

## Integration Points

### Input From
- Instruction Processing Agent: Field interpretations
- Agent Registry: Valid categorical values
- Previous pipeline results (for refinements)

### Output To
- Query Generation Agent: Uses unified interpretation and priorities
- Response Context: Saves for potential refinements

## Common Patterns

### E-commerce Queries
**Query**: "dividend stocks under $50"
- Prioritizes price constraint first
- Then dividend yield filter
- Resolves "under $50" ambiguity (price, not P/E)

### Sector + Quality
**Query**: "best healthcare companies"
- Sector as primary filter
- Quality metrics (profitability, growth) as secondary
- May add size filter for established companies

### Complex Multi-Criteria
**Query**: "undervalued growth stocks with strong fundamentals"
- Balances value metrics (P/E, P/B)
- With growth metrics (revenue growth)
- And fundamental health (margins, debt)

## Refinement Examples

### Adding Criteria
**Original**: "tech stocks"
**Refinement**: "only profitable ones"
**Synthesis**: Maintains tech sector, adds profit filter at high priority

### Narrowing Results
**Original**: "dividend stocks"
**Refinement**: "focus on high yield"
**Synthesis**: Adjusts dividend yield threshold upward

### Changing Focus
**Original**: "large cap stocks"
**Refinement**: "actually, mid cap"
**Synthesis**: Replaces size filter entirely

## Error Handling

1. **Invalid Categorical Values**:
   - Logs warning
   - Attempts to find closest match
   - Includes in conflicts_resolved

2. **Missing Interpretations**:
   - Handles gracefully
   - Notes in unified interpretation

3. **Conflicting Priorities**:
   - Uses intelligent defaults
   - Documents decisions

## Testing

```python
# Test synthesis directly
from app.modules.agents.synthesis.service import synthesis_service
from app.modules.agents.synthesis.models import SynthesisRequest, FieldInterpretation

request = SynthesisRequest(
    query="Find undervalued profitable tech companies",
    field_interpretations=[
        FieldInterpretation(
            field_name="company_sector",
            interpretation="Technology"
        ),
        FieldInterpretation(
            field_name="ttm_price_to_earnings_ratio",
            interpretation="Under 15"
        ),
        FieldInterpretation(
            field_name="ttm_net_profit_margin",
            interpretation="Positive > 0%"
        )
    ]
)

result = await synthesis_service.synthesize_interpretations(request)
print(f"Unified: {result.unified_interpretation}")
for fp in result.field_priorities:
    print(f"Priority {fp.priority}: {fp.field_name}")
```

## Performance Considerations

- Categorical validation uses cached values
- Minimal processing overhead
- Single AI call for synthesis
- Efficient conflict detection

## Debugging

Enable debug logging:
```python
import logging
logging.getLogger("app.modules.agents.synthesis").setLevel(logging.DEBUG)
```

Shows:
- Validation warnings
- Conflict detection logic
- Priority assignment reasoning
- Unification process

## Best Practices

1. **Clear Interpretations**: Unified interpretation should be understandable
2. **Logical Priorities**: Most important filters first
3. **Document Conflicts**: All resolutions in conflicts_resolved
4. **Preserve Intent**: Don't over-interpret user needs

## Future Enhancements

1. **Machine Learning**: Learn conflict resolution from user feedback
2. **Domain Knowledge**: Industry-specific synthesis rules
3. **Multi-Query Context**: Consider conversation history
4. **Explanation Generation**: Detailed reasoning for each decision
