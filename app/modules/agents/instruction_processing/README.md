# Instruction Processing Agent

The Instruction Processing Agent is the second stage in the multi-agent pipeline, responsible for converting extracted fields into specific filter values based on natural language instructions and predefined rules.

## Purpose

This agent takes the fields identified by the Field Extraction Agent and interprets the user's intent to determine the appropriate filter values. It bridges the gap between colloquial language (e.g., "cheap", "profitable") and specific database values (e.g., "P/E < 10", "profit margin > 0.25").

## How It Works

### Input
- User's natural language query
- List of relevant fields from Field Extraction Agent
- Field-specific instructions from `settings/field_instructions.yaml`

### Output
- Field interpretations with specific filter values
- Applied instructions for each field
- Reasoning for value selection

## Example Transformations

| User Query | Field | Interpretation |
|------------|-------|----------------|
| "cheap stocks" | `ttm_price_to_earnings_ratio` | "Under 10" |
| "highly profitable" | `ttm_net_profit_margin` | "High > 25%" |
| "dividend aristocrats" | `ttm_dividend_yield` | "Moderate 2-4%" |
| "tech companies" | `company_sector` | "Technology" |
| "large cap" | `market_capitalization` | "Large-Cap $10-200 B" |
| "stable companies" | `beta` | "Low < 0.8" |

## Field Instructions

The agent uses detailed instructions from `settings/field_instructions.yaml` to map natural language to specific values:

### Example: P/E Ratio Instructions
```yaml
ttm_price_to_earnings_ratio: |
  Measures price relative to earnings; a classic valuation gauge where lower numbers suggest a cheaper profit multiple.
  • If user requests 'good', 'quality', or 'best', set the filter to Under 20 (reasonable valuation).
  • If user requests 'undervalued', 'cheap', or 'value', set the filter to Under 10.
  • If user requests 'fair value', apply > 15 and < 20 in the same filter.
  • If user requests 'high-valuation' or 'over-valued', set the filter to > 20.
  • NOTE: When using "Under X" filters where X is positive, exclude negative values (add > 0 constraint)
```

## Key Features

### 1. Context-Aware Interpretation
The agent considers the full query context when interpreting fields:
- "good oil stocks" → `company_sector`: "Energy" + quality filters
- "best dividend stocks" → applies both dividend and quality criteria

### 2. Multi-Value Handling
For range-based queries:
- "mid-cap stocks" → `market_capitalization`: "$2B to $10B"
- "moderate profit margins" → `ttm_net_profit_margin`: "11-25%"

### 3. Percentage Conversion
Instructions use percentages for clarity, but the agent knows:
- "25% margin" in instructions → 0.25 in database
- "2% yield" in instructions → 0.02 in database

### 4. Special Cases

#### Valuation Ratios
For fields like P/E, P/B, EV/EBITDA:
- "Under X" automatically excludes negative values when X > 0
- Negative ratios are meaningless for valuation analysis

#### Geographic Filters
- US company requests handled via exchange filter, not country field
- International expanded beyond exchanges uses country field

## Implementation Details

### Models (`models.py`)
```python
class FieldInterpretation(BaseModel):
    field_name: str
    interpretation: str  # The specific filter value
    instruction_used: Optional[str]  # Which instruction was applied
```

### Service Logic (`service.py`)
1. **Instruction Loading**: Retrieves field-specific rules
2. **Context Analysis**: Understands query intent
3. **Value Mapping**: Applies appropriate instruction rules
4. **Validation**: Ensures interpretations are valid

### Prompts (`prompts.py`)
The system prompt instructs the agent to:
- Follow field-specific instructions precisely
- Consider query context for interpretation
- Use exact values from instructions
- Handle edge cases appropriately

## Common Patterns

### Valuation Queries
- "cheap" → Lower thresholds (Under 10 for P/E)
- "fairly valued" → Mid-range values
- "expensive" → Higher thresholds

### Quality Queries
- "good stocks" → Positive profitability, reasonable valuation
- "quality companies" → High margins, strong financials
- "best performers" → Top-tier metrics

### Size Queries
- "large companies" → Market cap $10B+
- "small cap" → Market cap $300M-$2B
- "mega cap" → Market cap $200B+

### Financial Health
- "low debt" → Debt/Equity < 0.5
- "strong balance sheet" → Solvency > 60%
- "safe companies" → High interest coverage

## Integration Points

### Input From
- Field Extraction Agent: List of relevant fields
- User Query: Original natural language request
- Field Instructions: YAML configuration file

### Output To
- Synthesis Agent: Receives field interpretations for conflict resolution
- Query Generation: Uses interpretations to build MongoDB filters

## Error Handling

1. **Missing Instructions**: Uses default interpretation
2. **Invalid Values**: Logs warning and uses closest valid option
3. **Conflicting Instructions**: Defers to Synthesis Agent

## Testing

```python
# Test instruction processing directly
from app.modules.agents.instruction_processing.service import instruction_processing_service
from app.modules.agents.field_extraction.models import RelevantField

fields = [
    RelevantField(field_name="ttm_price_to_earnings_ratio", category="Valuation"),
    RelevantField(field_name="company_sector", category="Overview")
]

result = await instruction_processing_service.process_instructions(
    query="Find cheap tech stocks",
    relevant_fields=fields
)

for interpretation in result.field_interpretations:
    print(f"{interpretation.field_name}: {interpretation.interpretation}")
```

## Configuration

### Field Instructions (`settings/field_instructions.yaml`)
- Natural language rules for each field
- Threshold values and ranges
- Special handling instructions
- Edge case guidance

### Guidelines (`guidelines.py`)
- General interpretation principles
- Consistency rules
- Default behaviors

## Performance Considerations

- Instructions cached at startup
- Minimal parsing overhead
- Parallel field processing capability

## Debugging

Enable debug logging:
```python
import logging
logging.getLogger("app.modules.agents.instruction_processing").setLevel(logging.DEBUG)
```

This will show:
- Raw instruction text
- Interpretation decisions
- Applied rules

## Future Enhancements

1. **Dynamic Thresholds**: Adjust based on market conditions
2. **User Preferences**: Learn individual interpretation preferences
3. **Industry-Specific Rules**: Different thresholds by sector
4. **Relative Values**: "Cheaper than peer average" interpretations
