# Implementation Summary

TraceLens now observes an explicit customer-support workload rather than presenting synthetic traces.

## Runtime path

`/agent/run` starts a trace and runs three calls through `GeminiProvider`, a local knowledge-base search, a PostgreSQL order query, and a real HTTP call through `OrderManagementClient`. Each operation records its own event, duration, payload, status, and parent context. The trace is completed or failed by the route lifecycle.

## Main additions

- `backend/app/agent/llm.py`: reusable instrumented Gemini provider boundary.
- `backend/app/agent/knowledge_base.py`: local retrieval abstraction.
- `backend/app/agent/order_api.py`: real HTTP client and external API event capture.
- `backend/app/main.py`: local order-management endpoint and expanded trace responses.
- `frontend/src/App.jsx`: generated lineage inspector, payload inspection, latency categories, and architecture view.
- `backend/test_instrumentation.py`: semantic end-to-end lineage test with three instrumented LLM calls and a real local HTTP server.

## Verification

- Backend: 14 tests passing.
- Frontend: Vite production build passing.
- Live Gemini execution remains dependent on the configured provider project having model access and quota.
