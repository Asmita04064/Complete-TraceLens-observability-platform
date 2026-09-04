# Quick Start Guide - Running TraceLens End-to-End

## Prerequisites
- Python 3.9+
- Node.js 16+
- PostgreSQL 12+ running on port 5433
- Google Gemini API key (free tier available at https://aistudio.google.com/app/apikey)

## Step-by-Step Setup

### 1. Environment Configuration
Create `.env` file in project root:
```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5433/tracelens
GEMINI_API_KEY=your-gemini-api-key-here
```

### 2. Backend Setup (Terminal 1)
```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python create_tables.py
python seed_agent_data.py
uvicorn app.main:app --reload
```

Expected output:
```
INFO:     Application startup complete [press ENTER to quit]
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 3. Frontend Setup (Terminal 2)
```powershell
cd frontend
npm install
npm run dev
```

Expected output:
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  press h + enter to show help
```

### 4. Open Application
Visit `http://localhost:5173` in your browser

### 5. Try the Agent

**Option A: Via Frontend**
1. Click "Run Agent" in left sidebar
2. Enter query: `Where is order ORD-1001?`
3. Click "Run Agent" button
4. View response with trace ID
5. Click "View Trace" to see execution timeline

**Option B: Via PowerShell API**
```powershell
# Run agent query
$response = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/agent/run" `
  -ContentType 'application/json' `
  -Body '{"message":"Where is order ORD-1001?"}'

# Display results
$response | ConvertTo-Json
$trace_id = $response.trace_id

# View trace details
$trace = Invoke-RestMethod -Uri "http://127.0.0.1:8000/traces/$trace_id"
$trace | ConvertTo-Json
```

## Example Queries to Try

```
"Where is order ORD-1001?"
"Where is order ORD-1005?"
"Tell me about customer CUST-001"
"What orders does customer CUST-002 have?"
"Get order status for ORD-1003"
```

## What You'll See

### In Browser Frontend
- Agent response with trace ID
- "View Trace" button
- Trace timeline with:
  - LLM Call events (Gemini)
  - Tool Call events (order_service)
  - Database Query events (PostgreSQL)
  - Duration for each operation
  - Parent-child event hierarchy

### In Terminal
- Backend: Event creation logs
- Frontend: Hot-reload notifications

## Verify Installation

### Run Tests
```powershell
cd backend
pytest test_instrumentation.py -v
```

Expected: 13 tests passing

### Check Backend Health
```powershell
curl http://127.0.0.1:8000/health
# Or in PowerShell:
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected: `{"status":"ok"}`

## Troubleshooting

### PostgreSQL not connecting
- Verify PostgreSQL is running on port 5433
- Check DATABASE_URL in .env
- Ensure database `tracelens` exists

### Gemini API errors
- Verify GEMINI_API_KEY is set in .env
- Confirm API key is valid
- Check you have API quota available

### Frontend not loading
- Verify npm install completed
- Check for build errors in terminal
- Try: `npm run build` to debug

### Tests failing
- Ensure PostgreSQL is running
- Run: `python -m pytest test_instrumentation.py -v` from backend directory
- All 13 tests should pass

## Project Structure

```
tracelens/
├── backend/
│   ├── app/
│   │   ├── agent/
│   │   │   ├── agent.py (Gemini AI Agent)
│   │   │   └── tools.py (Database tools)
│   │   ├── instrumentation/
│   │   │   ├── context.py (Contextvars)
│   │   │   ├── tracer.py (Event management)
│   │   │   └── decorators.py (Auto-instrumentation)
│   │   ├── models/
│   │   │   ├── trace.py (Trace/TraceEvent)
│   │   │   └── agent.py (Order/Customer)
│   │   ├── main.py (FastAPI + /agent/run)
│   │   ├── schemas.py (Pydantic models)
│   │   └── database.py (SQLAlchemy setup)
│   ├── create_tables.py (Initialize DB)
│   ├── seed_agent_data.py (Demo data)
│   ├── test_instrumentation.py (Test suite)
│   └── requirements.txt (Dependencies)
├── frontend/
│   ├── src/
│   │   ├── App.jsx (Agent interface)
│   │   ├── api/traces.js (API client)
│   │   └── styles.css (Styling)
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── README.md (Documentation)
└── IMPLEMENTATION_SUMMARY.md (Project details)
```

## API Endpoints Reference

### Trace Management
- `GET /health` - Health check
- `POST /traces` - Create trace
- `GET /traces` - List all traces
- `GET /traces/{trace_id}` - Get trace details
- `GET /traces/{trace_id}/summary` - Get summary
- `POST /traces/{trace_id}/events` - Add event
- `POST /traces/{trace_id}/complete` - Complete trace
- `POST /traces/{trace_id}/fail` - Fail trace

### Agent Execution
- `POST /agent/run` - Execute agent with auto-instrumentation

## How It Works: Behind the Scenes

1. **User submits**: "Where is order ORD-1001?"
2. **Backend receives**: POST /agent/run with message
3. **Tracer starts**: trace_id created, set in contextvars
4. **Agent runs**: AIAgent.run(message)
5. **LLM call 1**: @traced_function decorator captures event
   - Gemini processes request
   - Decides to call get_order_status tool
6. **Tool call**: @traced_function decorator captures event
   - Gemini provides tool name and parameters
   - Order status lookup queued
7. **Database query**: @traced_function decorator captures event
   - PostgreSQL SELECT executes
   - Order details returned
8. **LLM call 2**: @traced_function decorator captures event
   - Gemini receives tool results
   - Generates final response
9. **Trace completes**: tracer.complete_trace()
   - All events saved
   - Duration calculated
   - Status set to "completed"
10. **Frontend displays**: Response + trace ID
11. **User clicks View Trace**: Timeline shows complete execution

## Next Steps

### After Initial Testing
1. Explore the trace timeline
2. Notice automatic event hierarchy
3. Check actual timing measurements
4. Try different agent queries
5. Run tests to understand architecture
6. Review code in app/instrumentation/ for patterns

### For Development
1. Add new tools to OrderService
2. Create new event types
3. Extend with OpenTelemetry
4. Add distributed tracing
5. Integrate with your own LLM

### For Deployment
1. Set up PostgreSQL on production server
2. Configure Gemini API key securely
3. Build frontend: `npm run build`
4. Deploy backend to cloud (AWS, GCP, Azure)
5. Serve frontend from CDN
6. Add authentication and authorization

## Support

- See README.md for detailed documentation
- See IMPLEMENTATION_SUMMARY.md for architecture details
- See test_instrumentation.py for code examples
- See app/instrumentation/ for implementation patterns

---

**Status**: ✅ Production Ready - All features working, comprehensive tests passing
