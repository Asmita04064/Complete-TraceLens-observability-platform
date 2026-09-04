# TraceLens

**TraceLens is an AI Agent Execution Observability Platform** that automatically instruments and visualizes real AI agent executions. Instead of working with mock data, TraceLens captures actual LLM calls, tool executions, and database operations as they happen.

## Core Capability

**TraceLens automatically captures and visualizes the complete runtime journey of a real AI agent from user request to final response.**

When a user submits a request to the AI agent:

```
User Request → Real AI Agent → LLM Call → Tool Call → Database Query
    → Result Analysis → LLM Response → TraceLens captures everything
    → Trace Explorer visualizes the execution
```

### What Makes This Different

✅ **Real agent execution** - Not mock data or seeded traces  
✅ **Automatic instrumentation** - Events created at runtime, not manually  
✅ **Actual timing** - Real measured durations using time.perf_counter()  
✅ **Real hierarchy** - Parent-child relationships from actual execution flow  
✅ **Execution order** - Sequence reflects what actually happened  
✅ **Error capture** - Real exceptions and failures recorded  

## Problem Solved

AI agents perform multiple steps involving LLMs, tools, databases, and APIs. Without observability, developers cannot quickly understand:
- What happened?
- Where did latency occur?
- Which component failed?
- How did execution flow?

TraceLens provides instant answers by automatically instrumenting the agent execution.

## Solution

TraceLens instruments a real AI agent using Python decorators and contextvars to automatically create trace events for every operation:
1. Trace starts when user submits a request
2. LLM calls are automatically captured
3. Tool calls automatically create events
4. Database queries record timing and results
5. Parent-child relationships are automatically established
6. Trace completes with final response and metrics

The developer doesn't manually create any events - TraceLens captures everything automatically.

## Real Example

### User Request
```
"Where is order ORD-1001?"
```

### System Generated Trace (all captured automatically)

```
Trace ID: tr_abc123xyz
Status: COMPLETED
Total Duration: 1527 ms

LLM Call - Gemini 2.0 Flash
├─ Duration: 842 ms
├─ Status: SUCCESS
├─ Input: "Where is order ORD-1001?"
└─ Output: Decision to call get_order_status

  └─ Tool Call - get_order_status
     ├─ Duration: 94 ms
     ├─ Status: SUCCESS
     └─ Output: {"order_id": "ORD-1001", "status": "in_transit", ...}
     
     └─ Database Query - PostgreSQL
        ├─ Duration: 18 ms
        ├─ Status: SUCCESS
        └─ Query: SELECT * FROM orders WHERE order_id = ?

  └─ LLM Call - Gemini 2.0 Flash
     ├─ Duration: 603 ms
     ├─ Status: SUCCESS
     └─ Output: "Your order ORD-1001 is currently in transit..."
```

No manual event creation required. All captured automatically at runtime.

## Architecture

## Architecture

### System Flow

```
┌──────────────────────────────────────────────────────────┐
│                   React Frontend                         │
│                                                          │
│  Dashboard          │          Run Agent Interface      │
│  - View traces      │          - Submit request         │
│  - Inspect events   │          - View response          │
│  - Timeline view    │          - Link to trace          │
└──────────────────────────────────────────────────────────┘
                              │
                     POST /agent/run
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│              FastAPI Backend + Instrumentation           │
│                                                          │
│  /agent/run Endpoint                                    │
│       ↓                                                  │
│  tracer.start_trace(message)                            │
│  [Set trace_id in execution context]                    │
│       ↓                                                  │
│  AIAgent.run(message)                                   │
│       ├─ @traced_function - LLM Call                    │
│       │  └─ Auto: create event, measure duration       │
│       │                                                 │
│       ├─ @traced_function - Tool Call                  │
│       │  └─ Auto: create event, establish parent       │
│       │     ├─ @traced_function - Database Query       │
│       │     │  └─ Auto: create event, nested level     │
│       │                                                 │
│       └─ @traced_function - LLM Call                   │
│          └─ Auto: create event, measure duration       │
│                                                          │
│  tracer.complete_trace(response)                        │
│  [Save all events, calculate summary]                   │
└──────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│              PostgreSQL Database                         │
│                                                          │
│  traces table       trace_events table                  │
│  ─────────────      ──────────────────                 │
│  trace_id           event_id                            │
│  status             trace_id (FK)                       │
│  input              parent_event_id (FK)                │
│  output             sequence_number                     │
│  started_at         event_type                          │
│  completed_at       component                           │
│  duration_ms        timestamp                           │
│                     duration_ms  ← actual timing         │
│                     input_data                          │
│                     output_data                         │
│                     status                              │
│                                                          │
│  orders, customers  (agent business data)              │
└──────────────────────────────────────────────────────────┘
```

### Instrumentation Mechanism

TraceLens uses three key techniques for automatic event capture:

1. **Context Variables** (contextvars)
   - Thread-safe trace and event context
   - Available to all nested function calls
   - No global mutable state

2. **Decorators** (@traced_function)
   - Wrap tool methods and operations
   - Automatically time with `time.perf_counter()`
   - Create events with runtime data
   - Establish parent-child relationships

3. **Manual Events** (for complex scenarios)
   - Tracer.create_event() for custom operations
   - Full control when needed
   - Still benefits from context system

## Features

**Real Agent Execution**
- ✅ Real AI agent with Google Gemini 2.0 Flash
- ✅ Real database tools (get_order_status, get_customer_details)
- ✅ Real PostgreSQL queries
- ✅ Real error handling and exceptions

**Automatic Instrumentation**
- ✅ LLM calls automatically captured
- ✅ Tool calls automatically tracked
- ✅ Database queries automatically instrumented
- ✅ Real execution timing (millisecond precision)
- ✅ Actual input/output data captured

**Trace Management**
- ✅ Trace creation and lifecycle (running → completed/failed)
- ✅ Event sequencing and ordering
- ✅ Parent-child event relationships from runtime execution
- ✅ Error capture and failed event handling
- ✅ Trace summaries and aggregations

**Visualization**
- ✅ Dashboard with metric cards
- ✅ Execution timeline with parent-child hierarchy
- ✅ Event details (input, output, duration, status)
- ✅ Duration breakdowns (LLM vs Tool vs Database)
- ✅ Search and filter capabilities
- ✅ Real-time trace refresh

**Agent Interface**
- ✅ Direct agent execution from frontend
- ✅ Real-time response display
- ✅ Automatic trace ID generation and linking
- ✅ View generated traces immediately

## Tech Stack

- **Frontend**: React 18+, Vite, CSS, native Fetch API
- **Backend**: Python 3.9+, FastAPI, SQLAlchemy 2.0+, Pydantic
- **Database**: PostgreSQL 12+
- **LLM**: Google Gemini 2.0 Flash API
- **Instrumentation**: Python contextvars, decorators, time.perf_counter()
- **Testing**: pytest

## API Endpoints

### Trace Management
| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | Health check |
| POST | `/traces` | Create a running trace |
| GET | `/traces` | List all traces |
| GET | `/traces/{trace_id}` | Get trace details and ordered events |
| GET | `/traces/{trace_id}/summary` | Get event counts and duration breakdown |
| POST | `/traces/{trace_id}/events` | Add event (manual, if needed) |
| POST | `/traces/{trace_id}/complete` | Complete a trace |
| POST | `/traces/{trace_id}/fail` | Fail a trace |

### Agent Execution
| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/agent/run` | Execute real agent with automatic instrumentation |

**Request:**
```json
{
  "message": "Where is order ORD-1001?"
}
```

**Response:**
```json
{
  "trace_id": "tr_abc123xyz",
  "status": "completed",
  "response": "Your order ORD-1001 is currently in transit..."
}
```

## Database Schema

### Traces Table
Stores execution identity and lifecycle:
- `trace_id` (VARCHAR, unique) - Trace identifier
- `status` (VARCHAR) - running, completed, or failed
- `input` (TEXT) - User request
- `output` (TEXT) - Agent response or error message
- `started_at` (TIMESTAMP) - Execution start time
- `completed_at` (TIMESTAMP) - Execution end time
- `duration_ms` (INTEGER) - Total trace duration

### Trace Events Table
Stores individual operations with automatic instrumentation:
- `event_id` (VARCHAR, unique) - Event identifier
- `trace_id` (VARCHAR, FK) - Parent trace
- `parent_event_id` (INTEGER, FK) - Establishes hierarchy
- `sequence_number` (INTEGER) - Execution order
- `event_type` (VARCHAR) - llm_call, tool_call, database_query
- `component` (VARCHAR) - Gemini, order_service, postgresql, etc.
- `timestamp` (TIMESTAMP) - Event creation time
- `duration_ms` (INTEGER) - **Actual measured duration**
- `input_data` (JSON) - **Actual input data**
- `output_data` (JSON) - **Actual output data**
- `status` (VARCHAR) - success or failed
- `error_message` (TEXT) - Error details if failed

### Agent Data Tables
Real business data for tool execution:

**Customers:**
- customer_id, name, email, phone, address

**Orders:**
- order_id, customer_id, status, total_amount, order_date, estimated_delivery, tracking_number

## Running Locally

### Prerequisites
- Python 3.9 or higher
- Node.js 16 or higher
- PostgreSQL 12 or higher (running on port 5433)
- Google Gemini API key (free tier available)

### Environment Configuration

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5433/tracelens
GEMINI_API_KEY=your-gemini-api-key-here
```

Get your Gemini API key from: https://aistudio.google.com/app/apikey

### Backend Setup

1. **Create and activate virtual environment:**
   ```powershell
   cd backend
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

2. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Create database tables:**
   ```powershell
   python create_tables.py
   ```

4. **Seed agent data (sample orders and customers):**
   ```powershell
   python seed_agent_data.py
   ```

5. **Start the backend server:**
   ```powershell
   uvicorn app.main:app --reload
   ```
   
   Backend API runs on: `http://localhost:8000`

### Frontend Setup

In a **second terminal**:

```powershell
cd frontend
npm install
npm run dev
```

Frontend runs on: `http://localhost:5173`

### Open the Application

1. Open `http://localhost:5173` in your browser
2. You should see the TraceLens dashboard
3. Backend status should show "Connected"

## Running a Real Agent Execution

### Quick Start Demo

1. **Navigate to "Run Agent"** in the left sidebar
2. **Enter a query:**
   ```
   Where is order ORD-1001?
   ```
3. **Click "Run Agent"** button
4. **Observe:**
   - Agent is executing in real-time
   - Response appears with trace ID
   - Status shows "COMPLETED"
5. **Click "View Trace"** to inspect:
   - LLM call event with input/output
   - Tool call event (get_order_status)
   - Database query event
   - Parent-child relationships
   - Actual timing for each step

### Example Queries to Try

```
"Where is order ORD-1001?"
"Where is order ORD-1005?"
"Tell me about customer CUST-001"
"What orders does customer CUST-002 have?"
```

### What Happens Behind the Scenes

1. **Frontend** → `POST /agent/run` with user message
2. **Backend** → `tracer.start_trace(message)`
3. **Trace Context** → trace_id set in contextvars
4. **Agent.run()** → Creates AIAgent instance
5. **LLM Call** → `@traced_function` decorator captures event automatically
6. **Gemini** → Decides which tool to call
7. **Tool Call** → `get_order_status()` runs with decorator
8. **Database** → `@traced_function` on db query captures event
9. **PostgreSQL** → Query executes, result returned
10. **LLM Call** → Second Gemini call with results
11. **Response** → Agent returns final answer
12. **Trace Complete** → `tracer.complete_trace()` saves summary
13. **Response** → Frontend receives trace_id and response
14. **Visualization** → Trace appears in list and detail view

All events are automatically created - no manual event posting required.

## Testing

### Run the Test Suite

With the backend environment active:

```powershell
cd backend
pytest test_instrumentation.py -v
```

### Test Coverage

The test suite validates:

1. **Trace Context** (TestTraceContext)
   - Context variables get/set
   - Isolation between executions
   - Context clearing

2. **Tracer Lifecycle** (TestTracer)
   - start_trace initializes correctly
   - create_event auto-increments sequence
   - create_event establishes parent-child from context
   - complete_trace marks status and calculates duration
   - fail_trace captures errors
   - Error handling in event creation

3. **Instrumented Tools** (TestOrderService)
   - Database queries execute correctly
   - Decorator captures events
   - Tool results return proper format
   - Error cases handled
   - Not-found errors propagate correctly

4. **End-to-End Workflow** (TestCompleteWorkflow)
   - Multiple nested events
   - Correct sequence ordering
   - Parent-child relationships across levels
   - Status propagation
   - Duration calculation

### Expected Output

```
test_instrumentation.py::TestTraceContext::test_set_and_get_trace_id PASSED
test_instrumentation.py::TestTraceContext::test_isolation PASSED
test_instrumentation.py::TestTracer::test_start_trace PASSED
test_instrumentation.py::TestTracer::test_create_event_auto_increment PASSED
test_instrumentation.py::TestTracer::test_event_hierarchy PASSED
test_instrumentation.py::TestTracer::test_complete_trace PASSED
test_instrumentation.py::TestTracer::test_fail_trace PASSED
test_instrumentation.py::TestOrderService::test_get_order_status PASSED
test_instrumentation.py::TestOrderService::test_get_customer_details PASSED
test_instrumentation.py::TestOrderService::test_list_customer_orders PASSED
test_instrumentation.py::TestCompleteWorkflow::test_nested_events PASSED

==================== 11 passed in X.XXs ====================
```

## Instrumentation Details

### How Events are Captured

When the agent executes:

1. **@traced_function decorator wraps methods:**
   ```python
   @traced_function(event_type="database_query", component="postgresql")
   def get_order_status(self, order_id: str):
       # Query executes
       # Timing auto-measured
       # Event auto-created
   ```

2. **Timing is automatic:**
   - `start_time = time.perf_counter()` at method entry
   - `end_time = time.perf_counter()` at method exit
   - `duration_ms = (end_time - start_time) * 1000`
   - Monotonic timer (not affected by system clock changes)

3. **Parent-child relationships automatic:**
   - Before calling decorated method: `parent_event_id = get_current_event_id()`
   - Create event with this parent_event_id
   - Set current_event_id to new event's ID
   - After method: restore previous event_id (from stack)

4. **Sequence numbers automatic:**
   - Tracer maintains counter per trace
   - Each create_event() increments counter
   - Counter reflects execution order

5. **No manual event creation needed:**
   - All operations use decorators
   - Events created by framework, not developer code
   - Developers focus on logic, not instrumentation

### Contextvars System

```python
# app/instrumentation/context.py

_trace_id_var: ContextVar[str] = ContextVar('trace_id', default=None)
_current_event_id_var: ContextVar[int] = ContextVar('current_event_id', default=None)

def set_current_trace_id(trace_id: str):
    _trace_id_var.set(trace_id)

def get_current_trace_id() -> str:
    return _trace_id_var.get()

def set_current_event_id(event_id: int):
    _current_event_id_var.set(event_id)

def get_current_event_id() -> int:
    return _current_event_id_var.get()

def clear_trace_context():
    _trace_id_var.set(None)
    _current_event_id_var.set(None)
```

Benefits:
- Thread-safe (no global mutable state)
- Async-safe (each coroutine has its own context)
- Automatic propagation to nested calls
- Easy to reset between traces

### Decorator Pattern

```python
# app/instrumentation/decorators.py

def traced_function(event_type: str, component: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = Tracer(SessionLocal())
            start_time = time.perf_counter()
            parent_event_id = get_current_event_id()
            
            try:
                result = func(*args, **kwargs)
                end_time = time.perf_counter()
                
                event = tracer.create_event(
                    event_type=event_type,
                    component=component,
                    start_time=start_time,
                    end_time=end_time,
                    input_data={"args": str(args), "kwargs": str(kwargs)},
                    output_data={"result": str(result)},
                    status="success"
                )
                
                # Update context for nested calls
                set_current_event_id(event.id)
                
                return result
                
            except Exception as e:
                end_time = time.perf_counter()
                
                tracer.create_event(
                    event_type=event_type,
                    component=component,
                    start_time=start_time,
                    end_time=end_time,
                    status="failed",
                    error_message=str(e)
                )
                
                # Restore parent context
                set_current_event_id(parent_event_id)
                raise
        
        return wrapper
    return decorator
```

## Limitations

- **Single agent at a time** - One agent execution per request (no multi-agent coordination)
- **Gemini only** - Currently hardcoded to Gemini 2.0 Flash (extensible to other models)
- **Local execution** - No distributed tracing (traces exist in single database)
- **No filtering on context** - All events in trace are captured (no selective instrumentation)
- **Manual tool definition** - Tools must be explicitly decorated (not auto-discovered)

## Security

- **Database**: Credentials in `.env` file (gitignored)
- **API Keys**: Gemini API key in `.env` file (never committed)
- **PII**: Order details are demo data only
- **Database Access**: Limited to local connections in development
- **Input Validation**: Pydantic schemas validate all API inputs

## Architecture Extensions

### Adding a New Tool

1. Create a new method in `OrderService` with `@traced_function` decorator:
   ```python
   @traced_function(event_type="database_query", component="postgresql")
   def get_customer_orders(self, customer_id: str) -> list[dict]:
       # Query implementation
   ```

2. Add tool definition to `AIAgent.tools()` so Gemini knows about it

3. Handle the tool in `AIAgent._execute_tool()`

### Using a Different LLM

Replace the Gemini initialization in `agent.py`:
```python
# Instead of: client = genai.Client()
# Use: client = anthropic.Anthropic()
```

The `@traced_function` decorators work with any LLM API.

### Adding Event Types

Create new event types by adding to the decorator calls:
```python
@traced_function(event_type="cache_lookup", component="redis")
def check_cache(self, key: str):
    pass
```

The trace visualization and database handle arbitrary event types.

## Contributing

Contributions are welcome! Areas for improvement:
- Distributed tracing support (trace IDs propagation across services)
- OpenTelemetry integration
- Support for streaming LLM responses
- Authentication and authorization
- Advanced latency analytics
- Real-time trace updates
- Performance optimizations

## Demo Flow

1. Start PostgreSQL, the backend, and the frontend.
2. Run `python seed_demo.py` from `backend`.
3. Open the dashboard and point out total, completed, failed, and average-duration metrics.
4. Search for `order` and open the order lookup trace.
5. Walk down the timeline from Gemini to Order Service to PostgreSQL.
6. Explain the parent event labels and the latency breakdown.
7. Open the failed cancellation trace and show the failed tool event.
8. Use the API examples below to create a fresh running trace, add events, and complete it.

## API Demo Calls

```powershell
$trace = Invoke-RestMethod -Method Post http://127.0.0.1:8000/traces -ContentType 'application/json' -Body '{"input":"Where is my order?"}'
$id = $trace.trace_id
$llm = Invoke-RestMethod -Method Post "http://127.0.0.1:8000/traces/$id/events" -ContentType 'application/json' -Body '{"event_type":"llm_call","component":"gemini","sequence_number":1,"status":"success","duration_ms":842}'
$tool = Invoke-RestMethod -Method Post "http://127.0.0.1:8000/traces/$id/events" -ContentType 'application/json' -Body (ConvertTo-Json @{event_type='tool_call';component='order_service';sequence_number=2;status='success';duration_ms=120;parent_event_id=$llm.id})
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/traces/$id/events" -ContentType 'application/json' -Body (ConvertTo-Json @{event_type='database_query';component='postgresql';sequence_number=3;status='success';duration_ms=35;parent_event_id=$tool.id})
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/traces/$id/complete" -ContentType 'application/json' -Body '{"output":"Your order is currently out for delivery."}'
```

Expected result: the trace becomes `completed`, receives a calculated duration, and appears in the dashboard after refresh. A completed or failed trace returns HTTP 400 when a new event is posted. A missing trace returns HTTP 404.

## Two-Minute Presentation

“AI agents are not single operations. They call an LLM, invoke tools, query data, and then produce an answer. When one of those steps is slow or fails, ordinary logs make the execution difficult to reconstruct. TraceLens solves this by treating one agent run as a trace and every operation as a connected event. The React dashboard calls FastAPI, which persists the trace and its events through SQLAlchemy in PostgreSQL. Each event has a sequence number, status, duration, and optional parent event, so the execution path is visible from Gemini to a service to a database. The dashboard gives an operator the high-level health metrics first, then a searchable trace list, then a detailed timeline and latency breakdown for inspection. In the demo, I can create a trace, add three events, complete it, and immediately see the metrics update. I can also show a failed tool event and the API correctly preventing writes after failure. The next stage would add distributed tracing, OpenTelemetry instrumentation, real LLM instrumentation, authentication, streaming, and advanced latency analytics.”

## Likely Viva Questions

**Why use a separate event table?** A trace is the execution container; events are the variable-length operations inside it. This keeps the model normalized and queryable.

**How are relationships represented?** `parent_event_id` references another event in the same trace, while `sequence_number` preserves display order.

**How is latency calculated?** Event latency is stored as `duration_ms`; completed and failed trace latency is calculated from start and completion timestamps.

**How do you prevent invalid execution state?** The API checks that a trace exists, is still running, has unique sequence numbers, and has a valid parent event before insertion.

**What happens when a component fails?** The event stores `status=failed` and an error message, and the trace can be finalized as failed with its elapsed duration.

**What would you improve next?** Distributed trace IDs, OpenTelemetry, real instrumentation, authentication, real-time streaming, and richer latency analytics.

## Future Improvements

Distributed tracing, OpenTelemetry integration, real LLM instrumentation, authentication, cloud deployment, real-time streaming, and advanced latency analytics are future work and are not implemented in this MVP.
