# Streaming Implementation Plan for Finks Naive

## Overview
Enable real-time streaming of agent thought processes and partial results to provide immediate feedback during the 3-5 second query processing time.

## Current Architecture Challenges
1. **Gemini Flash API**: Doesn't natively support streaming like OpenAI
2. **Multi-Agent Pipeline**: Sequential dependencies between agents
3. **Lambda Deployment**: Streaming from Lambda requires special handling
4. **Pydantic AI**: Current implementation waits for complete responses

## Proposed Streaming Architecture

### 1. Server-Sent Events (SSE) Approach
```python
# app/modules/agents/router_streaming.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
import json

@router.post("/query/stream")
async def process_query_stream(request: AgentPipelineRequest):
    async def event_generator() -> AsyncGenerator[str, None]:
        # Stream pipeline progress
        async for event in agent_pipeline_service.process_query_stream(request):
            yield f"data: {json.dumps(event)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
```

### 2. WebSocket Alternative
```python
# app/modules/agents/websocket.py
from fastapi import WebSocket
from typing import Dict, Any

@router.websocket("/query/ws")
async def websocket_query(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        request = AgentPipelineRequest(**data)
        
        async for event in agent_pipeline_service.process_query_stream(request):
            await websocket.send_json(event)
            
    except Exception as e:
        await websocket.send_json({"error": str(e)})
    finally:
        await websocket.close()
```

## Implementation Details

### 1. Modified Agent Pipeline Service
```python
# app/modules/agents/service_streaming.py
class StreamingAgentPipelineService:
    async def process_query_stream(
        self, 
        request: AgentPipelineRequest
    ) -> AsyncGenerator[Dict[str, Any], None]:
        
        # Stream field extraction start
        yield {
            "stage": "field_extraction",
            "status": "started",
            "message": "Analyzing query to identify relevant database fields..."
        }
        
        field_result = await self.field_extraction.extract_fields_from_query(request.query)
        
        yield {
            "stage": "field_extraction",
            "status": "completed",
            "data": {
                "fields": field_result.relevant_fields,
                "confidence": field_result.confidence,
                "reasoning": field_result.reasoning
            }
        }
        
        # Stream instruction processing
        yield {
            "stage": "instruction_processing",
            "status": "started",
            "message": f"Processing instructions for {len(field_result.relevant_fields)} fields..."
        }
        
        # Continue for each stage...
```

### 2. Streaming Progress Events Structure
```typescript
interface StreamEvent {
    stage: 'field_extraction' | 'instruction_processing' | 'synthesis' | 'query_generation' | 'database_query';
    status: 'started' | 'progress' | 'completed' | 'error';
    message?: string;
    data?: any;
    progress?: {
        current: number;
        total: number;
    };
    timestamp: string;
}
```

### 3. Client-Side Implementation
```javascript
// Example client code
const eventSource = new EventSource('/agents/query/stream');

eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    switch(data.stage) {
        case 'field_extraction':
            updateUI('Identifying relevant fields...', data);
            break;
        case 'synthesis':
            updateUI('Synthesizing interpretations...', data);
            break;
        case 'database_query':
            if (data.status === 'progress') {
                updateUI(`Found ${data.progress.current} results...`, data);
            }
            break;
    }
};
```

## Lambda Streaming Considerations

### 1. Lambda Function URL Streaming
```python
# Lambda function URLs support response streaming
def lambda_handler(event, context):
    def response_stream():
        yield json.dumps({"stage": "starting"})
        # Process and yield events
        
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'X-Amz-Function-Streaming': 'true'
        },
        'body': response_stream(),
        'isBase64Encoded': False
    }
```

### 2. API Gateway WebSocket
- Use API Gateway WebSocket APIs for bidirectional streaming
- Maintain connection state in DynamoDB
- Handle connection lifecycle events

## Gemini Flash Workarounds

### 1. Chunked Processing
```python
# Break down prompts for progressive processing
async def extract_fields_progressive(self, query: str):
    # First, quick field identification
    quick_prompt = f"List relevant database fields for: {query}"
    quick_result = await self.agent.run(quick_prompt)
    yield {"fields_identified": quick_result}
    
    # Then, detailed analysis
    detailed_prompt = f"Explain why these fields are relevant: {quick_result}"
    detailed_result = await self.agent.run(detailed_prompt)
    yield {"reasoning": detailed_result}
```

### 2. Parallel Streaming
```python
# Stream results as they complete in parallel
async def stream_parallel_agents(self, query: str):
    tasks = {
        "fields": self.extract_fields(query),
        "sorting": self.extract_sorting(query),
        "context": self.analyze_context(query)
    }
    
    # Stream results as they complete
    for coro in asyncio.as_completed(tasks.values()):
        result = await coro
        yield result
```

## Benefits of Streaming

1. **Immediate Feedback**: Users see progress within 100ms
2. **Perceived Performance**: 3-5 second wait feels shorter
3. **Debugging**: Developers can see agent thought process
4. **Error Recovery**: Can show partial results if one agent fails
5. **Progressive Enhancement**: Can show initial results while refining

## Implementation Phases

### Phase 1: Basic Progress Streaming
- [ ] Implement SSE endpoint
- [ ] Stream stage start/complete events
- [ ] Add progress messages

### Phase 2: Partial Results
- [ ] Stream field extraction results immediately
- [ ] Show partial database results as they arrive
- [ ] Progressive result refinement

### Phase 3: Advanced Features
- [ ] WebSocket support for bidirectional communication
- [ ] Stream agent reasoning/thoughts
- [ ] Real-time query refinement
- [ ] Collaborative filtering based on stream feedback

## Example Streaming Timeline

```
0ms    → Connection established
100ms  → "Analyzing your query..."
300ms  → "Identified 5 relevant fields: PE ratio, market cap..."
800ms  → "Processing field instructions..."
1200ms → "Interpreting: PE ratio < 20 means value stocks..."
1800ms → "Generating MongoDB query..."
2200ms → "Executing database search..."
2500ms → "Found 43 results, formatting..."
3000ms → Complete results delivered
```

## Monitoring Streaming Performance

```python
# Track streaming metrics
streaming_metrics = {
    "time_to_first_byte": [],  # TTFB for each stage
    "stage_durations": {},
    "client_disconnects": 0,
    "streaming_errors": 0
}
```

## Fallback Strategy

For clients that don't support streaming:
1. Detect client capabilities
2. Fall back to standard JSON response
3. Include progress polling endpoint
4. Provide estimated completion time

## Cost Considerations

- Streaming increases Lambda execution time slightly
- WebSocket connections have additional API Gateway costs
- Consider batching events to reduce overhead
- Cache streaming responses where possible