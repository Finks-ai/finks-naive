# Sorting Extraction Agent

The Sorting Extraction Agent runs in parallel with the Field Extraction Agent and is responsible for detecting sorting intent from natural language queries.

## Purpose

This agent identifies when users want results sorted in a specific order and determines which field to sort by and in which direction (ascending/descending). It understands various ways users express ordering preferences in natural language.

## How It Works

### Input
- Natural language query
- List of available sortable fields

### Output
- Whether sorting is requested (`has_sorting`)
- Field to sort by (`sort_field`)
- Sort direction (`sort_direction`: "asc" or "desc")
- Confidence score (0-100)
- Reasoning for the decision
- Extracted sorting phrase

## Example Transformations

| User Query | Sort Field | Direction | Reasoning |
|------------|------------|-----------|-----------|
| "top dividend stocks" | `ttm_dividend_yield` | DESC | "top" implies highest values |
| "cheapest tech stocks" | `ttm_price_to_earnings_ratio` | ASC | "cheapest" implies lowest P/E |
| "best performing stocks" | `price_change_1year_percentage` | DESC | "best performing" implies highest returns |
| "worst performers" | `price_change_1year_percentage` | ASC | "worst" implies lowest/negative returns |
| "largest companies" | `market_capitalization` | DESC | "largest" implies highest market cap |
| "find tech stocks" | None | N/A | No sorting intent detected |

## Sorting Patterns

### Superlative Keywords
The agent recognizes various superlative patterns:

#### Highest/Maximum (DESC)
- "top", "best", "highest", "maximum"
- "most profitable", "most valuable"
- "biggest", "largest", "greatest"

#### Lowest/Minimum (ASC)
- "bottom", "worst", "lowest", "minimum"
- "cheapest", "smallest", "least"
- "most undervalued"

### Field-Specific Patterns

#### Valuation Sorting
- "cheapest stocks" → P/E ratio (ASC)
- "most undervalued" → P/B ratio (ASC)
- "most expensive" → P/E ratio (DESC)

#### Performance Sorting
- "best performers" → Price change % (DESC)
- "top gainers" → Price change % (DESC)
- "biggest losers" → Price change % (ASC)

#### Size Sorting
- "largest companies" → Market cap (DESC)
- "biggest by revenue" → Revenue (DESC)
- "smallest caps" → Market cap (ASC)

#### Dividend Sorting
- "top dividend payers" → Dividend yield (DESC)
- "highest yielding" → Dividend yield (DESC)

## Implementation Details

### Models (`models.py`)
```python
class SortingIntentResponse(BaseModel):
    has_sorting: bool
    sort_field: Optional[str] = None
    sort_direction: Optional[Literal["asc", "desc"]] = None
    confidence: int  # 0-100
    reasoning: str
    sorting_phrase: Optional[str] = None
```

### Service Logic (`service.py`)
1. **Pattern Detection**: Identifies sorting keywords/phrases
2. **Field Mapping**: Maps intent to appropriate database field
3. **Direction Logic**: Determines ASC/DESC based on context
4. **Confidence Scoring**: Rates certainty of sorting intent

### Prompts (`prompts.py`)
The system prompt instructs the agent to:
- Identify superlative language
- Map sorting intent to specific fields
- Consider context for direction
- Handle ambiguous cases

## Integration with Pipeline

### Parallel Execution
Runs simultaneously with Field Extraction for performance:
```python
parallel_steps = ["extract_fields", "extract_sorting"]
```

### Database Query Integration
If sorting is detected, it's applied after the main query:
```python
if sorting_intent.has_sorting:
    cursor = cursor.sort([(sorting_intent.sort_field,
                          1 if sorting_intent.sort_direction == "asc" else -1)])
```

## Special Cases

### 1. Multiple Sorting Indicators
Query: "top profitable large cap stocks"
- Primary sort: Profitability (DESC)
- Could also sort by: Market cap
- Agent picks most emphasized aspect

### 2. Implicit Sorting
Some queries imply sorting without explicit keywords:
- "dividend aristocrats" → May sort by dividend consistency
- "growth stocks" → May sort by revenue growth

### 3. No Sorting Needed
Many queries don't require sorting:
- "tech stocks in healthcare"
- "companies with P/E under 15"
- "profitable energy companies"

## Field Mapping Logic

The agent maps conceptual sorting to actual fields:

| Concept | Mapped Field |
|---------|--------------|
| "cheapest" | `ttm_price_to_earnings_ratio` |
| "most profitable" | `ttm_net_profit_margin` |
| "best dividend" | `ttm_dividend_yield` |
| "fastest growing" | `year_over_year_quarterly_revenue_growth` |
| "most stable" | `beta` (ascending for stability) |
| "best value" | `ttm_price_to_book_ratio` |

## Error Handling

1. **Ambiguous Intent**: Returns `has_sorting: false` with low confidence
2. **Unknown Field**: Logs warning, falls back to relevance
3. **Conflicting Signals**: Uses primary sorting indicator

## Testing

```python
# Test sorting extraction directly
from app.modules.agents.sorting_extraction.service import sorting_extraction_service

result = await sorting_extraction_service.extract_sorting_intent(
    "Show me the top dividend paying stocks"
)

print(f"Sort by: {result.sort_field} {result.sort_direction}")
print(f"Confidence: {result.confidence}%")
print(f"Reasoning: {result.reasoning}")
```

## Common Patterns

### Performance Queries
- "best performing" → 1-year price change DESC
- "YTD winners" → YTD price change DESC
- "5-year winners" → 5-year price change DESC

### Valuation Queries
- "cheapest by P/E" → P/E ratio ASC
- "lowest P/B stocks" → P/B ratio ASC
- "best value stocks" → Combined valuation metrics

### Financial Health
- "strongest balance sheets" → Solvency ratio DESC
- "lowest debt" → Debt-to-equity ASC
- "best margins" → Net profit margin DESC

## Performance Considerations

- Runs in parallel with field extraction
- Lightweight processing (pattern matching)
- Single AI call for intent detection
- No database lookups required

## Debugging

Enable debug logging:
```python
import logging
logging.getLogger("app.modules.agents.sorting_extraction").setLevel(logging.DEBUG)
```

Shows:
- Detected sorting phrases
- Field mapping decisions
- Direction determination logic
- Confidence calculations

## Limitations

1. **Single Sort Field**: Currently supports only one sort field
2. **Predefined Mappings**: Relies on known concept-to-field mappings
3. **English Only**: Sorting keywords are English-specific

## Future Enhancements

1. **Multi-Field Sorting**: Support secondary sort criteria
2. **Custom Sort Expressions**: Complex sorting logic
3. **User Preferences**: Learn individual sorting preferences
4. **Dynamic Mapping**: Discover new sorting patterns from usage
