# Project Verification

## Verified locally

- `backend/.venv/Scripts/python.exe -m pytest -q`: 14 passed.
- `frontend/npm run build`: passed.
- Trace sequence and parent IDs are asserted by the end-to-end test.
- The end-to-end test executes a real local HTTP request and captures the external API event.
- `.env` is ignored and is not tracked by Git.

## Provider limitation

A live Gemini request is not claimed as successful by this report. It requires a Gemini API project with access to the selected model and available quota. Provider errors are captured as failed LLM events and failed traces.

## Remaining technical risk

The existing test fixture resets the configured PostgreSQL schema between tests. The suite is verified locally, but it must use a dedicated test database rather than a shared runtime database.

## Manual demo

Start PostgreSQL, create tables, seed agent records, run FastAPI and Vite, then submit `Where is my order ORD-1001 and when will it arrive?` from the Run Agent view. Open the returned trace and inspect the generated event sequence and payloads.
