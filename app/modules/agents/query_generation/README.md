# Query Generation Agent

The Query Generation Agent is the final stage in the multi-agent pipeline, responsible for converting synthesized field interpretations into executable MongoDB queries.

## Purpose

This agent takes the unified interpretation from the Synthesis Agent and generates a properly formatted MongoDB query that can be executed against the database. It handles all the technical details of query construction including operator selection, value formatting, and special constraints.

## How It Works

### Input

- Unified interpretation from Synthesis Agent
- Field priorities (which fields are most important)
- Target collection name (usually "master_search")
- Previous query context (for refinements)

### Output

- MongoDB query object (JSON)
- Query explanation in natural language
- Estimated result count

## Example Transformations

### Basic Query

**Input**: "Find cheap tech stocks"

```json
{
  "$and": [
    {"company_sector": "Technology"},
    {"ttm_price_to_earnings_ratio": {"$gt": 0, "$lt": 10}},
    {"exchange_acronym": {"$in": ["NASDAQ", "NYSE", "AMEX", "CBOE", "CNQ", "ICE"}}
  ]
}
```

### Complex Query

**Input**: "Large cap dividend stocks with P/E under 20 and profit margin over 15%"

```json
{
  "$and": [
    { "market_capitalization": { "$gte": 10000000000 } },
    { "ttm_dividend_yield": { "$gt": 0 } },
    { "ttm_price_to_earnings_ratio": { "$gt": 0, "$lt": 20 } },
    { "ttm_net_profit_margin": { "$gt": 0.15 } },
    {
      "exchange_acronym": {
        "$in": ["NASDAQ", "NYSE", "AMEX", "CBOE", "CNQ", "ICE"]
      }
    }
  ]
}
```

## Key Features

### 1. Automatic Exchange Filtering

When no country/exchange is specified, automatically adds US exchanges:

```python
US_EXCHANGES = ["NASDAQ", "NYSE", "AMEX", "CBOE", "CNQ", "ICE"]
```

### 2. Valuation Ratio Handling

For valuation ratios (P/E, P/B, EV/EBITDA, etc.), when user requests "less than X" where X is positive:

```json
// "P/E < 10" becomes:
{ "ttm_price_to_earnings_ratio": { "$gt": 0, "$lt": 10 } }
```

This excludes negative ratios which are meaningless for valuation analysis.

### 3. Percentage to Decimal Conversion

Database stores percentages as decimals:

- "profit margin > 25%" → `{"ttm_net_profit_margin": {"$gt": 0.25}}`
- "dividend yield > 2%" → `{"ttm_dividend_yield": {"$gt": 0.02}}`

### 4. MongoDB Operator Mapping

| Natural Language         | MongoDB Operator | Example                               |
| ------------------------ | ---------------- | ------------------------------------- |
| "under X", "less than X" | `$lt`            | `{"field": {"$lt": 10}}`              |
| "over X", "more than X"  | `$gt`            | `{"field": {"$gt": 5}}`               |
| "between X and Y"        | `$gte` + `$lte`  | `{"field": {"$gte": 5, "$lte": 10}}`  |
| "is X" (categorical)     | direct value     | `{"field": "value"}`                  |
| "in [X, Y, Z]"           | `$in`            | `{"field": {"$in": ["X", "Y", "Z"]}}` |

### 5. Query Structure Optimization

- High priority fields in main query body
- Lower priority fields in nested conditions
- Efficient use of compound indexes

## Implementation Details

### Service Methods

#### `generate_query()`

Main query generation from synthesis results:

1. Formats field priorities for prompt
2. Includes categorical value constraints
3. Runs AI agent to generate query
4. Applies post-processing filters
5. Validates JSON structure

#### `_ensure_exchange_filter()`

Adds US exchange filter when:

- No exchange filter exists in query
- No international/foreign terms in query
- Preserves existing exchange filters

#### `_ensure_positive_valuation_ratios()`

For valuation ratio fields:

- Detects "less than" filters
- Checks if threshold is positive
- Adds `"$gt": 0` constraint if needed
- Preserves negative threshold queries

### Models (`models.py`)

```python
class QueryGenerationRequest(BaseModel):
    query: str
    unified_interpretation: str
    field_priorities: List[FieldPriority]
    target_collection: str = "master_search"

class QueryGenerationResponse(BaseModel):
    mongodb_query: Dict[str, Any]
    query_explanation: str
    estimated_results: Optional[int]
```

### Prompts (`prompts.py`)

The prompt includes:

- MongoDB operator reference
- JSON formatting rules
- Special handling instructions
- Example transformations

## Query Refinement

For follow-up queries, the agent:

1. Preserves constraints from previous query
2. Adds new constraints from refinement
3. Handles field conflicts appropriately
4. Uses `$and` to combine conditions

### Example Refinement

**Original**: "tech stocks" → `{"company_sector": "Technology"}`
**Refinement**: "only large cap"
**Combined**:

```json
{
  "$and": [
    { "company_sector": "Technology" },
    { "market_capitalization": { "$gte": 10000000000 } }
  ]
}
```

## Error Handling

### JSON Parsing

1. Attempts direct JSON parsing
2. Falls back to cleaning single quotes → double quotes
3. Handles escaped quotes properly
4. Raises clear error if parsing fails

### Query Validation

- Ensures valid MongoDB syntax
- Checks operator usage
- Validates field names exist

## Special Cases

### 1. Categorical Fields

Only uses exact values from allowed lists:

```python
# company_sector must be one of:
["Technology", "Healthcare", "Financial Services", ...]
```

### 2. Numeric Scaling

- Billions: "10B" → 10000000000
- Millions: "100M" → 100000000
- Percentages: "25%" → 0.25

### 3. Edge Cases

- Empty query → returns all with exchange filter
- Conflicting conditions → uses `$and` array
- Invalid operators → falls back to equality

## Integration Points

### Input From

- Synthesis Agent: Unified interpretation and priorities
- Configuration: Exchange lists, field constants

### Output To

- Database Service: Executable MongoDB query
- Pipeline Response: Query details for debugging

## Testing

```python
# Test query generation directly
from app.modules.agents.query_generation.service import query_generation_service
from app.modules.agents.query_generation.models import QueryGenerationRequest, FieldPriority

request = QueryGenerationRequest(
    query="Find profitable tech companies",
    unified_interpretation="Looking for technology sector companies with positive profit margins",
    field_priorities=[
        FieldPriority(field_name="company_sector", priority=1),
        FieldPriority(field_name="ttm_net_profit_margin", priority=2)
    ]
)

result = await query_generation_service.generate_query(request)
print(json.dumps(result.mongodb_query, indent=2))
```

## Performance Optimization

1. **Query Efficiency**

   - Uses indexed fields when possible
   - Avoids complex `$or` operations
   - Structures for optimal query planning

2. **Caching**
   - Categorical values loaded once
   - Exchange lists are constants
   - Minimal runtime processing

## Debugging

Enable debug logging:

```python
import logging
logging.getLogger("app.modules.agents.query_generation").setLevel(logging.DEBUG)
```

Shows:

- Raw AI response
- JSON cleaning steps
- Filter applications
- Final query structure

## Common Issues

1. **KeyError in formatting**: Check for unescaped braces in prompts
2. **Invalid JSON**: Usually from single quotes in AI response
3. **Missing exchange filter**: Verify `_ensure_exchange_filter()` logic
4. **Negative ratios included**: Check `VALUATION_RATIO_FIELDS` list

## Future Enhancements

1. **Query Optimization**: Analyze and optimize query performance
2. **Index Hints**: Suggest optimal indexes for common queries
3. **Aggregation Pipelines**: Support for complex aggregations
4. **Query Explanations**: More detailed performance implications
