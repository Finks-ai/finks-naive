# Field Extraction Agent

The Field Extraction Agent is the first stage in the multi-agent pipeline, responsible for identifying which database fields are relevant to a user's natural language query.

## Purpose

This agent analyzes natural language queries and maps them to specific database fields from our financial dataset. It understands the semantic meaning of user requests and identifies the corresponding technical fields needed to fulfill the query.

## How It Works

### Input
- Natural language query (e.g., "Find profitable tech companies with low debt")
- List of available database fields with descriptions
- Field categorization metadata

### Output
- List of relevant database fields
- Confidence score (0-100)
- Reasoning for field selection
- Category assignments for each field

## Example Transformations

| User Query | Extracted Fields |
|------------|------------------|
| "cheap stocks" | `ttm_price_to_earnings_ratio`, `ttm_price_to_book_ratio` |
| "dividend paying companies" | `ttm_dividend_yield` |
| "tech giants" | `company_sector`, `market_capitalization` |
| "profitable with good margins" | `ttm_net_profit_margin`, `ttm_operating_profit_margin` |
| "low debt companies" | `ttm_debt_to_equity_ratio`, `ttm_solvency_ratio` |

## Field Categories

The agent respects field categorization rules:

### Multi-Select Categories
- **Valuation**: Can select multiple valuation metrics (P/E, P/B, EV/EBITDA, etc.)
- **Profitability**: Can select multiple profit metrics
- **Financial Health**: Can select multiple financial ratios

### Single-Select Categories
- **Overview**: Only one field selected (e.g., either sector OR country, not both)
- **Performance**: Typically selects the most relevant time period

## Implementation Details

### Models (`models.py`)
```python
class FieldExtractionResponse(BaseModel):
    relevant_fields: List[RelevantField]
    confidence: int  # 0-100
    reasoning: str
```

### Service Logic (`service.py`)
1. **Field Identification**: Uses AI to understand query intent
2. **Category Constraints**: Applies single-select vs multi-select rules
3. **Confidence Scoring**: Rates how well fields match the query
4. **Validation**: Ensures selected fields exist in the database

### Prompts (`prompts.py`)
The system prompt instructs the agent to:
- Analyze semantic meaning of financial terms
- Map colloquial language to technical field names
- Consider related fields that might be implicit
- Respect category constraints

## Configuration

### Available Fields
Loaded from `settings/search_space_input.yaml`:
```yaml
P/E Ratio:
  fe_internal_name: ttm_price_to_earnings_ratio
  description: "Price relative to earnings - lower means cheaper"
  category: Valuation
```

### Unavailable Fields
Some fields may be marked as unavailable in `settings/search_space_unavailable.yaml` and won't be selected.

## Category Rules

### Multi-Select Example
Query: "Find undervalued stocks"
```
✓ Can select: P/E Ratio, P/B Ratio, P/S Ratio (all from Valuation category)
```

### Single-Select Example
Query: "US tech companies"
```
✓ Selects: company_sector (Overview category)
✗ Cannot also select: company_country (same category)
Note: US filtering handled by exchange filter, not country field
```

## Integration Points

### Input From
- User's natural language query
- Available fields configuration
- Category definitions

### Output To
- Instruction Processing Agent (receives list of fields to process)
- Synthesis Agent (uses field list for prioritization)

## Error Handling

1. **No Fields Found**: Returns empty list with low confidence
2. **Invalid Category**: Logs warning and excludes field
3. **Unavailable Fields**: Automatically filtered out

## Performance Optimizations

- Fields and categories loaded once at startup
- Category constraints applied after AI processing
- Minimal field validation overhead

## Testing

```python
# Test field extraction directly
from app.modules.agents.field_extraction.service import field_extraction_service

result = await field_extraction_service.extract_fields(
    "Find high dividend tech stocks"
)

print(f"Found fields: {[f.field_name for f in result.relevant_fields]}")
print(f"Confidence: {result.confidence}%")
```

## Common Patterns

### Financial Health Queries
- "strong balance sheet" → `ttm_solvency_ratio`, `ttm_debt_to_equity_ratio`
- "financially stable" → `ttm_interest_coverage_ratio`, `ttm_current_ratio`

### Growth Queries
- "fast growing" → `year_over_year_quarterly_revenue_growth`, `5year_annual_total_revenue_growth`
- "earnings growth" → `year_over_year_quarterly_eps_growth`, `1year_annual_EPS_growth`

### Value Queries
- "undervalued" → `ttm_price_to_earnings_ratio`, `ttm_price_to_book_ratio`
- "cheap" → `ttm_price_to_free_cash_flow_ratio`, `ttm_ev_to_ebitda`

## Debugging

Enable debug logging:
```python
import logging
logging.getLogger("app.modules.agents.field_extraction").setLevel(logging.DEBUG)
```

This will show:
- Raw AI response
- Category constraint applications
- Field filtering decisions

## Future Enhancements

1. **Synonym Recognition**: Better mapping of alternative terms
2. **Context Awareness**: Understanding field relationships
3. **Query Expansion**: Suggesting related fields user might want
4. **Learning**: Improving field selection based on user feedback
