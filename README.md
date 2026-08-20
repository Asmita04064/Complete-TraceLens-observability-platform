# TraceLens 🔍

### AI Agent Execution Observability Platform

TraceLens is an observability platform for understanding **how an AI-powered application executes a request**.

Instead of treating logs as isolated messages, TraceLens reconstructs an agent execution as a structured **trace** containing individual events such as LLM calls, tool invocations, and database queries.

> **TraceLens answers the question: "What exactly happened during this AI execution?"**

---

## 🚀 Why TraceLens?

Modern AI applications are rarely a single model call.

A single user request can trigger:

```text
User Request
      ↓
    Agent
      ↓
     LLM
      ↓
    Tool
      ↓
   Database
      ↓
     LLM
      ↓
Final Response
```

When an execution becomes slow or fails, traditional application logs make it difficult to reconstruct:

* Which operations executed?
* In what order?
* Which component caused the failure?
* Which operation consumed the most time?
* What triggered a particular operation?
* What was the final state of the execution?

TraceLens provides a structured view of this execution journey.

---

# 🎯 Core Concept

A **trace** represents one complete agent execution.

Each operation within that execution is stored as an **event**.

```text
                        TRACE
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
     LLM Call          Tool Call        DB Query
        │                 │                 │
     842 ms            120 ms             35 ms
     SUCCESS           SUCCESS           SUCCESS
        │
        └──── parent_event_id ────┐
                                  ▼
                              Child Event
```

Each event preserves:

* Execution order
* Parent-child relationship
* Component
* Event type
* Status
* Duration
* Timestamp
* Input/output
* Error information
* Metadata

This allows TraceLens to reconstruct the execution rather than displaying disconnected logs.

---

# ✨ Features

### Trace Lifecycle

```text
CREATE
  ↓
RUNNING
  ↓
COMPLETED
```

or

```text
CREATE
  ↓
RUNNING
  ↓
FAILED
```

Invalid lifecycle transitions are rejected by the API.

---

### Event Tracking

TraceLens currently supports:

```text
LLM Call
Tool Call
Database Query
```

The event model is designed to be extensible for additional operation types.

---

### Execution Ordering

Every event receives a:

```text
sequence_number
```

Example:

```text
1 → LLM
2 → Tool
3 → Database
4 → LLM
```

Repeated operations are intentionally preserved as separate events.

This means three LLM calls remain three distinct events instead of being incorrectly merged into one.

---

### Parent-Child Lineage

Events can reference their parent using:

```text
parent_event_id
```

Example:

```text
LLM Call
   │
   └── Tool Call
          │
          └── Database Query
```

This provides execution lineage rather than just chronological logs.

---

### Latency Analysis

Every event records its execution duration.

Example:

```text
Gemini LLM        842 ms
Order Service     120 ms
PostgreSQL         35 ms
```

This makes latency bottlenecks easier to identify.

---

### Failure Tracking

Failures are represented at both event and trace level.

```text
Trace
 │
 ├── LLM          ✓ SUCCESS
 │
 ├── Tool         ✓ SUCCESS
 │
 ├── Database     ✗ FAILED
 │
 └── Trace        ✗ FAILED
```

The failed event retains its error information for inspection.

---

# 🏗️ Architecture

```text
                     ┌──────────────────────┐
                     │      React UI        │
                     │                      │
                     │  Dashboard           │
                     │  Trace Explorer      │
                     │  Timeline            │
                     │  Latency Analysis    │
                     └──────────┬───────────┘
                                │
                           HTTP / JSON
                                │
                                ▼
                     ┌──────────────────────┐
                     │       FastAPI        │
                     │                      │
                     │  Trace APIs          │
                     │  Event APIs          │
                     │  Summary APIs        │
                     │  Validation          │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │      SQLAlchemy      │
                     │                      │
                     │       ORM            │
                     │    Transactions      │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │     PostgreSQL       │
                     │                      │
                     │      traces          │
                     │    trace_events      │
                     └──────────────────────┘
```

---

# 🧩 System Execution Model

```text
                    Agent Request
                         │
                         ▼
                   Create Trace
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
           LLM Call              LLM Call
              │
              ▼
          Tool Call
              │
              ▼
        Database Query
              │
              ▼
        Final Response
              │
              ▼
        Complete Trace
```

The important distinction is:

```text
System Architecture
        ≠
Individual Trace
```

The architecture describes how TraceLens itself works.

The trace describes how an observed AI application executed.

---

# 🗄️ Database Design

TraceLens uses two primary relational entities.

## `traces`

Stores one record for each execution.

```text
traces
────────────────────────────
id
trace_id
input
output
status
started_at
completed_at
duration_ms
```

## `trace_events`

Stores individual operations.

```text
trace_events
────────────────────────────
id
event_id
trace_id
parent_event_id
sequence_number
event_type
component
timestamp
duration_ms
status
input_data
output_data
error_message
metadata
```

### Relationship

```text
traces
   │
   │ 1
   │
   │ N
   ▼
trace_events
   │
   │
   └──── parent_event_id
              │
              ▼
        trace_events
```

The separation allows a trace to contain a variable number of events while preserving relational integrity.

---

# 📊 Trace Explorer

The Trace Explorer provides a detailed view of an individual execution.

Example:

```text
Trace: tr_7bdfd909e3b6

1. LLM Call
   Gemini
   842 ms
   ✓ SUCCESS
       │
       ▼
2. Tool Call
   Order Service
   120 ms
   ✓ SUCCESS
       │
       ▼
3. Database Query
   PostgreSQL
   35 ms
   ✓ SUCCESS
       │
       ▼
4. Final Response
```

The operator can inspect:

* Event type
* Component
* Status
* Duration
* Sequence number
* Parent event
* Error details
* Trace summary

---

# 📈 Trace Summary

TraceLens aggregates execution information into a trace-level summary.

Example:

```json
{
  "trace_id": "tr_7bdfd909e3b6",
  "status": "completed",
  "total_events": 3,
  "successful_events": 3,
  "failed_events": 0,
  "total_event_duration_ms": 997,
  "llm_duration_ms": 842,
  "tool_duration_ms": 120,
  "database_duration_ms": 35
}
```

This creates a useful investigation flow:

```text
System Health
      ↓
    Trace
      ↓
    Event
      ↓
Latency / Failure
```

---

# 🔌 API

| Method | Endpoint                      | Purpose           |
| ------ | ----------------------------- | ----------------- |
| `GET`  | `/health`                     | Health check      |
| `POST` | `/traces`                     | Create trace      |
| `GET`  | `/traces`                     | List traces       |
| `POST` | `/traces/{trace_id}/events`   | Add event         |
| `POST` | `/traces/{trace_id}/complete` | Complete trace    |
| `POST` | `/traces/{trace_id}/fail`     | Fail trace        |
| `GET`  | `/traces/{trace_id}`          | Get trace         |
| `GET`  | `/traces/{trace_id}/summary`  | Get trace summary |

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

---

# 🛡️ Validation & Error Handling

TraceLens validates execution state at the API layer.

### Missing Trace

```text
404 Trace not found
```

### Event After Completion

```text
400 Cannot add events to a completed or failed trace
```

### Invalid Parent Event

```text
400 Parent event does not exist in this trace
```

### Invalid Lifecycle Transition

A completed or failed trace cannot be completed or failed again.

These validations prevent corrupted execution histories.

---

# 🧠 Engineering Decisions

## Why PostgreSQL?

Trace data has clear relationships:

```text
Trace → Events → Parent Events
```

PostgreSQL provides:

* Relational integrity
* Transactions
* Structured querying
* Indexing
* Reliable persistence

---

## Why FastAPI?

FastAPI provides:

* Request validation
* Typed API contracts
* Automatic OpenAPI documentation
* Lightweight Python development
* Easy integration with the AI/ML ecosystem

---

## Why React?

Trace investigation requires an interactive interface rather than static logs.

React enables:

* Dynamic trace selection
* Filtering
* Timeline rendering
* State management
* Interactive execution inspection

---

## Why Not LangGraph?

TraceLens is an **observability layer**, not an agent framework.

Introducing LangGraph would increase architectural complexity without solving the core problem of capturing and inspecting execution traces.

The system is designed to observe an existing AI workflow rather than dictate how that workflow is implemented.

---

# ⚖️ Engineering Trade-offs

A production-grade distributed tracing platform could look like:

```text
AI Application
      ↓
Instrumentation SDK
      ↓
OpenTelemetry
      ↓
Trace Collector
      ↓
Message Queue
      ↓
Distributed Storage
      ↓
TraceLens API
      ↓
React UI
```

TraceLens intentionally uses a smaller architecture:

```text
Application
     ↓
FastAPI
     ↓
PostgreSQL
     ↓
React
```

### Why?

The MVP prioritizes:

* Correctness
* Explainability
* Low infrastructure complexity
* Fast development
* Clear trace reconstruction

The production architecture would be more scalable, but would introduce significantly more operational complexity.

---

# ⚠️ Current Limitations

TraceLens is an MVP rather than a production distributed tracing platform.

Current limitations:

* Instrumentation is application-level rather than automatic.
* No OpenTelemetry collector.
* No distributed context propagation.
* No authentication or authorization.
* No real-time event streaming.
* PostgreSQL is currently the persistence dependency.
* Input/output capture depends on what the instrumented application provides.

These limitations are intentional and documented.

---

# 🔮 Future Roadmap

### Observability

* [ ] OpenTelemetry integration
* [ ] Automatic instrumentation
* [ ] Distributed context propagation
* [ ] Real-time trace streaming

### AI-specific observability

* [ ] LLM token tracking
* [ ] LLM cost tracking
* [ ] Model comparison
* [ ] Prompt/response inspection
* [ ] AI latency analytics

### Platform

* [ ] Authentication
* [ ] Role-based access control
* [ ] Trace comparison
* [ ] Advanced filtering
* [ ] Production cloud deployment

---

# 🧪 Demo Scenario

A sample AI workflow:

```text
User:
"Where is my order?"
```

Execution:

```text
User Request
      ↓
Gemini
      ↓
Order Service
      ↓
PostgreSQL
      ↓
Gemini
      ↓
Final Response
```

During a demonstration, the following capabilities can be shown:

1. Create a trace
2. Record multiple events
3. Preserve event ordering
4. Create parent-child relationships
5. Display event latency
6. Complete a trace
7. Generate a trace summary
8. Inspect a failed execution
9. Reject invalid state transitions

---

# 💻 Running Locally

## Prerequisites

* Python 3.x
* Node.js
* PostgreSQL
* PostgreSQL running on port `5433`
* Database: `tracelens`

Create `.env`:

```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5433/tracelens
```

---

## Backend

```powershell
cd backend

python -m venv .venv

.venv\Scripts\Activate.ps1

pip install -r requirements.txt

python create_tables.py

uvicorn app.main:app --reload
```

Backend:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

---

## Frontend

Open another terminal:

```powershell
cd frontend

npm install

npm run dev
```

Frontend:

```text
http://localhost:5173
```

---

# 🌱 Demo Data

Run:

```powershell
cd backend

python seed_demo.py
```

The seed generates representative traces containing:

* LLM calls
* Tool calls
* Database queries
* Parent-child relationships
* Successful executions
* Failed executions
* Event durations

The seed process is designed to avoid unnecessary duplication of existing demo traces.

---

# 📁 Project Structure

```text
TraceLens/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── database.py
│   │
│   ├── create_tables.py
│   ├── seed_demo.py
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── traces.js
│   │   └── ...
│   │
│   ├── package.json
│   └── vite.config.js
│
├── .env.example
├── README.md
└── ...
```

---

# 🧪 Example API Flow

### 1. Create Trace

```http
POST /traces
```

```json
{
  "input": "Where is my order?"
}
```

### 2. Add LLM Event

```http
POST /traces/{trace_id}/events
```

```json
{
  "event_type": "llm_call",
  "component": "gemini",
  "sequence_number": 1,
  "status": "success",
  "duration_ms": 842
}
```

### 3. Add Child Tool Event

```json
{
  "event_type": "tool_call",
  "component": "order_service",
  "sequence_number": 2,
  "status": "success",
  "duration_ms": 120,
  "parent_event_id": "..."
}
```

### 4. Complete Trace

```http
POST /traces/{trace_id}/complete
```

```json
{
  "output": "Your order is currently out for delivery."
}
```

---

# 🎥 Demo

> Add your best UI screenshot or short demo GIF here.

Recommended screenshots:

### Dashboard

```text
[ INSERT DASHBOARD SCREENSHOT ]
```

### Trace Explorer

```text
[ INSERT TRACE TIMELINE SCREENSHOT ]
```

### Architecture

```text
[ INSERT SYSTEM ARCHITECTURE / EXCALIDRAW DIAGRAM ]
```

A reviewer should be able to understand the project visually before reading the implementation details.

---

# 🏆 Why TraceLens?

TraceLens is designed around a simple principle:

> **AI systems should not be black boxes during execution.**

Instead of asking:

```text
"Why did this request fail?"
```

an engineer should be able to inspect:

```text
Which execution?
        ↓
Which event?
        ↓
Which component?
        ↓
Which parent operation?
        ↓
How long did it take?
        ↓
What failed?
```

TraceLens turns an opaque AI execution into a structured and inspectable execution history.

---

# 👤 Author

**AJ**

B.Tech — Artificial Intelligence & Data Science

Interested in:

* AI Engineering
* Backend Systems
* Full-Stack Development
* AI Observability
* Distributed Systems

---

## ⭐ If you find TraceLens interesting, consider giving the repository a star.

```
```
