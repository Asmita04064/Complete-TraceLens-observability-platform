# TraceLens

TraceLens is the tracing, lineage, and visualization layer around a small customer-support AI agent. The agent is only the workload being observed. Each event is created by the operation that actually runs; no synthetic trace seeding is used by the primary workflow.

## Challenge Workflow

A request such as `Where is my order ORD-1001 and when will it arrive?` produces this runtime sequence:

```text
User request
  -> LLM #1: request analysis
  -> Knowledge base search
  -> LLM #2: action planning
  -> PostgreSQL order query
  -> Order Management API HTTP request
  -> LLM #3: final response
  -> TraceLens timeline
```

The sequence is reconstructed from persisted events, not hardcoded in the frontend.

## Why Tracing

Ordinary logs scatter model calls, retrieval, database work, and HTTP calls across messages. They make it difficult to answer which operation caused latency, what data was passed to the next step, or where a failed request stopped. TraceLens records one trace with ordered, connected events and makes that execution inspectable.

## Instrumentation Architecture

```text
React frontend
      |
FastAPI /agent/run
      |
Trace context (contextvars) + Tracer
      |
Customer support agent
  |-- GeminiProvider -> Gemini API (three instrumented calls)
  |-- KnowledgeBase -> local documents
  |-- OrderService -> PostgreSQL
  `-- OrderManagementClient -> real HTTP request -> /mock/order-management/...
      |
PostgreSQL: traces, trace_events, orders, customers
```

`GeminiProvider` is the explicit provider boundary. It measures and records the request, response, duration, and error around the actual Gemini SDK call. The current provider is Gemini; other providers can implement the same adapter boundary later.

## Event Model

Every event stores:

- `trace_id`, `event_id`, and `parent_event_id`
- `sequence_number`, `event_type`, `component`, and `timestamp`
- actual `duration_ms`, `status`, and structured input/output data
- `error_message` when the operation fails

Supported runtime event types include `llm_call`, `knowledge_base_search`, `database_query`, `external_api_call`, and `tool_call`. Parent IDs come from the active context and sequence numbers are allocated from the trace's persisted events.

## Runtime Components

- **LLM:** `backend/app/agent/llm.py` calls Gemini through `GeminiProvider`.
- **Knowledge base:** `backend/app/agent/knowledge_base.py` performs local document retrieval.
- **Database:** `backend/app/agent/tools.py` queries seeded order/customer records through SQLAlchemy.
- **Order API:** `backend/app/agent/order_api.py` makes a real standard-library HTTP request. FastAPI exposes the local service at `/mock/order-management/orders/{order_id}`.
- **Tracing:** `backend/app/instrumentation/` owns context, timing, event persistence, and decorators.

## Frontend

The React dashboard provides:

- trace list, filters, status metrics, and agent execution form
- trace overview with ID, status, duration, timestamps, request, response, and event count
- generated execution lineage with sequence, parent, component, status, and expandable payloads
- latency breakdown for LLM, knowledge base, database, external API, and tools
- slowest-operation marker
- architecture view matching the implemented components

## Setup

Prerequisites: Python 3.9+, Node.js, PostgreSQL, and a Gemini API key with access to the configured model.

Create a root `.env` file. Never commit it:

```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5433/tracelens
GEMINI_API_KEY=your-key
GEMINI_MODEL=your-supported-gemini-model
ORDER_MANAGEMENT_API_URL=http://127.0.0.1:8000
MOCK_LLM=false
```

Use a supported Gemini model for the API project. With `MOCK_LLM=false`, the application calls Gemini and records provider failures honestly. Set `MOCK_LLM=true` only for a deterministic local demonstration: it uses the same three-stage traced flow, marks events and the UI as `MOCK LLM`, and never claims those responses came from Gemini.

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python create_tables.py
python seed_agent_data.py
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Demo

1. Start PostgreSQL, the backend, and the frontend.
2. In **Run Agent**, submit `Where is my order ORD-1001 and when will it arrive?`.
3. Open the returned trace.
4. Inspect the generated events in order: three LLM calls, knowledge-base search, database query, external API call, and final LLM response.
5. Expand event payloads and compare parent IDs, durations, and statuses.

The `/mock/order-management/...` endpoint is a local service boundary. The agent still performs an actual HTTP request to it during the run.

## API

- `GET /health`
- `POST /agent/run` with `{ "message": "..." }`
- `GET /traces`
- `GET /traces/{trace_id}`
- `GET /traces/{trace_id}/summary`
- `GET /mock/order-management/orders/{order_id}`

Manual trace and event routes remain available for debugging, but they are not the primary demo path.

## Failure Scenarios

Missing orders fail during the real PostgreSQL operation and create a failed `database_query` event. HTTP failures from the order-management client create a failed `external_api_call` event. Gemini exceptions create a failed `llm_call` event. The route then finalizes the trace as failed with the captured error.

## Internship Project Highlights

- Automatic AI agent execution tracing
- Hierarchical LLM, retrieval, database, and HTTP lineage
- Context-aware instrumentation with `contextvars`
- Runtime visualization and latency analysis
- PostgreSQL persistence
- Gemini integration with clearly labeled development mock mode
- Error and failure tracing
- Automated semantic workflow, redaction, and concurrency tests

## Engineering Decisions

- **`contextvars`:** keeps the active trace local to each request and thread without global mutable state.
- **Decorators:** make database and retrieval instrumentation reusable at the operation boundary.
- **Structured events:** preserve searchable payloads, status, duration, and lineage fields in PostgreSQL.
- **Parent IDs and sequence numbers:** represent both the runtime tree and the observed execution order.
- **Monotonic timing:** `time.perf_counter()` measures elapsed operation time without wall-clock jumps.
- **Provider abstraction:** `GeminiProvider` makes the real SDK boundary explicit and leaves room for another provider.
- **Mock mode:** `MOCK_LLM=true` provides a deterministic demo without mislabeling responses as Gemini output.
- **Local HTTP boundary:** the order-management route demonstrates external-call instrumentation without adding deployment complexity.

## Trade-offs

This is an internship-scale MVP: the service boundary is local rather than distributed, execution is synchronous, the knowledge base is a local document list rather than a vector database, and Gemini is the only real provider. It has limited credential redaction, no distributed trace propagation, and no OpenTelemetry export; these are deliberate future improvements rather than hidden capabilities.

## Privacy

The tracer captures operational payloads for inspection but should not be given secrets. The repository ignores `.env`, and event payloads must never include API keys, database passwords, authorization headers, or other credentials. Production deployments should add field-level redaction and retention controls before capturing real customer data.

## Tests and Verification

Backend tests cover trace lifecycle, context, ordering, hierarchy, durations, database instrumentation, and a complete workflow with three instrumented provider calls and a real local HTTP request:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm run build
```

For a live provider check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod -Method Post http://127.0.0.1:8000/agent/run `
  -ContentType 'application/json' `
  -Body '{"message":"Where is my order ORD-1001 and when will it arrive?"}'
```

A live successful run requires a Gemini project with an enabled model and available quota. Provider access or quota failures are recorded as failed LLM events rather than hidden or replaced with mock output.

The test fixture resets only the dedicated `TEST_DATABASE_URL` database. Use a dedicated test database before running the suite; never point it at a shared or production database.

For an isolated local test run, set `TEST_DATABASE_URL=sqlite:///./test_tracelens.db` in the shell before invoking pytest. For PostgreSQL-backed tests, create a separate database and set `TEST_DATABASE_URL` to that database URL. The test module fails fast if it equals `DATABASE_URL`.


## Limitations and Future Work

This MVP uses a local document list rather than a vector database, a local FastAPI route rather than a separately deployed service, synchronous request handling, and a single Gemini provider. Future work could add distributed propagation, OpenTelemetry export, redaction policies, authentication, streaming, and a replaceable vector-store implementation.
