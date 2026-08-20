# TraceLens

TraceLens is an agent execution observability platform for inspecting how AI workflows use models, tools, and databases.

## Problem

AI agents perform multiple steps involving LLMs, tools, databases, and APIs. Without observability, developers cannot quickly understand what happened, where latency occurred, which component failed, or how execution flowed.

## Solution

TraceLens records each execution as a trace and each model, tool, or database operation as an event. Parent-child relationships, statuses, durations, and summaries make an agent run understandable at a glance.

## Architecture

```text
React dashboard
      |
      v
FastAPI
      |
      v
SQLAlchemy
      |
      v
PostgreSQL
```

## Features

- Trace creation and completion/failure
- Event tracking for LLM, tool, and database operations
- Parent-child execution relationships
- Trace summaries and latency analysis
- Searchable, filterable dashboard
- Execution timeline with event status and duration
- Idempotent demo data seeding

## Tech Stack

- Frontend: React, Vite, CSS, native Fetch API
- Backend: Python, FastAPI, SQLAlchemy, Pydantic
- Database: PostgreSQL

## API Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | Health check |
| POST | `/traces` | Create a running trace |
| GET | `/traces` | List traces for the dashboard |
| POST | `/traces/{trace_id}/events` | Add an execution event |
| POST | `/traces/{trace_id}/complete` | Complete a trace with output |
| POST | `/traces/{trace_id}/fail` | Fail a trace with an error message |
| GET | `/traces/{trace_id}` | Get trace details and ordered events |
| GET | `/traces/{trace_id}/summary` | Get event counts and duration breakdown |

## Database Schema

`traces` stores the execution identity, input, output, status, timestamps, and total duration. `trace_events` stores each operation, its sequence number, component, status, duration, and optional `parent_event_id` foreign key back to another event in the same trace.

## Running Locally

PostgreSQL must be running on port `5433` with a database named `tracelens`. Configure the connection in the root `.env`:

```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5433/tracelens
```

Backend:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python create_tables.py
uvicorn app.main:app --reload
```

Frontend (in a second terminal):

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Demo Data

With the backend environment active, run:

```powershell
cd backend
python seed_demo.py
```

The script creates three realistic traces: an order lookup, a declined payment investigation, and a failed order cancellation. It skips traces with the same input, so repeated runs do not duplicate demo data.

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
