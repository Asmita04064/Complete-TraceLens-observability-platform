# TraceLens Quick Start

## 1. Configure

Create a root `.env` and keep it untracked:

```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5433/tracelens
GEMINI_API_KEY=your-key
GEMINI_MODEL=your-supported-model
ORDER_MANAGEMENT_API_URL=http://127.0.0.1:8000
MOCK_LLM=false
```

## 2. Start the backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python create_tables.py
python seed_agent_data.py
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 3. Start the frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## 4. Run the real workflow

In **Run Agent**, submit:

```text
Where is my order ORD-1001 and when will it arrive?
```

The generated trace should contain, in order, three `llm_call` events, `knowledge_base_search`, `database_query`, `external_api_call`, and a final `llm_call`. The external API event comes from a real HTTP request to the local order-management endpoint.

## 5. Verify

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm run build
```

The current backend suite includes semantic lineage, redaction, mock-mode, failure, integrity, and concurrency tests and should report 26 passing tests. A live Gemini run additionally requires an enabled model and available quota for the configured API project. Set `MOCK_LLM=true` for a deterministic demo; the UI labels it `MOCK LLM` and preserves the same traced workflow.

Tests default to the isolated SQLite database `sqlite:///./test_tracelens.db`. To use PostgreSQL, set `TEST_DATABASE_URL` to a dedicated test database before running pytest. The suite refuses to run if that URL equals `DATABASE_URL`.
## API smoke test

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
$run = Invoke-RestMethod -Method Post http://127.0.0.1:8000/agent/run -ContentType 'application/json' -Body '{"message":"Where is my order ORD-1001 and when will it arrive?"}'
Invoke-RestMethod "http://127.0.0.1:8000/traces/$($run.trace_id)"
```

## Failure checks

Use an unknown order to exercise the real database failure path. Stop or point `ORDER_MANAGEMENT_API_URL` at an unavailable service to exercise the real external API failure path. Provider errors become failed `llm_call` events and failed traces; no mock response is substituted.
