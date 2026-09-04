from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from app.database import get_db
from app.models import Trace, TraceEvent
from app.models.agent import Order
from app.schemas import (
    TraceCreate,
    TraceResponse,
    TraceEventCreate,
    TraceEventResponse,
    TraceDetailResponse,
    TraceEventDetail,
    TraceComplete,
    TraceFail,
    TraceListItem,
    AgentRequest,
)
from app.agent import AIAgent
from app.instrumentation import (
    Tracer,
    clear_trace_context,
)


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="TraceLens API",
    description="Agent execution observability platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# HELPER
# ============================================================

def utc_now():
    """
    Return current UTC time.
    """
    return datetime.now(timezone.utc)


def calculate_duration(started_at, completed_at):
    """
    Safely calculate duration even if PostgreSQL returns
    a timezone-naive datetime.
    """

    if started_at is None or completed_at is None:
        return None

    # Convert naive datetime to UTC-aware datetime
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)

    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)

    duration = (
        completed_at - started_at
    ).total_seconds() * 1000

    return max(0, int(duration))


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }


# ============================================================
# CREATE TRACE
# ============================================================

@app.post(
    "/traces",
    response_model=TraceResponse,
)
def create_trace(
    trace_data: TraceCreate,
    db: Session = Depends(get_db),
):

    trace_id = f"tr_{uuid4().hex[:12]}"

    trace = Trace(
        trace_id=trace_id,
        started_at=utc_now(),
        status="running",
        input=trace_data.input,
    )

    db.add(trace)
    db.commit()
    db.refresh(trace)

    return TraceResponse(
        trace_id=trace.trace_id,
        status=trace.status,
    )


# ============================================================
# CREATE TRACE EVENT
# ============================================================

@app.post(
    "/traces/{trace_id}/events",
    response_model=TraceEventResponse,
)
def create_trace_event(
    trace_id: str,
    event_data: TraceEventCreate,
    db: Session = Depends(get_db),
):
    # Check trace exists
    trace = (
        db.query(Trace)
        .filter(Trace.trace_id == trace_id)
        .first()
    )

    if trace is None:
        raise HTTPException(
            status_code=404,
            detail="Trace not found",
        )

    # Don't allow events after trace completion/failure
    if trace.status != "running":
        raise HTTPException(
            status_code=400,
            detail="Cannot add events to a completed or failed trace",
        )

    # Prevent duplicate sequence numbers
    existing_sequence = (
        db.query(TraceEvent)
        .filter(
            TraceEvent.trace_id == trace_id,
            TraceEvent.sequence_number == event_data.sequence_number,
        )
        .first()
    )

    if existing_sequence:
        raise HTTPException(
            status_code=400,
            detail=f"Sequence number {event_data.sequence_number} already exists for this trace",
        )

    # Validate parent event
    if event_data.parent_event_id is not None:
        parent_event = (
            db.query(TraceEvent)
            .filter(
                TraceEvent.id == event_data.parent_event_id,
                TraceEvent.trace_id == trace_id,
            )
            .first()
        )

        if parent_event is None:
            raise HTTPException(
                status_code=400,
                detail="Parent event does not exist in this trace",
            )

    # Create event
    event_id = f"evt_{uuid4().hex[:12]}"

    event = TraceEvent(
        event_id=event_id,
        trace_id=trace_id,
        parent_event_id=event_data.parent_event_id,
        sequence_number=event_data.sequence_number,
        event_type=event_data.event_type,
        component=event_data.component,
        timestamp=datetime.now(timezone.utc),
        duration_ms=event_data.duration_ms,
        input_data=event_data.input_data,
        output_data=event_data.output_data,
        status=event_data.status,
        error_message=event_data.error_message,
        event_metadata=event_data.metadata,
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return TraceEventResponse(
        id=event.id,
        event_id=event.event_id,
        trace_id=event.trace_id,
        event_type=event.event_type,
        component=event.component,
        sequence_number=event.sequence_number,
        parent_event_id=event.parent_event_id,
        status=event.status,
    )


# ============================================================
# COMPLETE TRACE
# ============================================================

@app.post(
    "/traces/{trace_id}/complete",
    response_model=TraceResponse,
)
def complete_trace(
    trace_id: str,
    trace_data: TraceComplete,
    db: Session = Depends(get_db),
):

    trace = (
        db.query(Trace)
        .filter(
            Trace.trace_id == trace_id
        )
        .first()
    )

    if trace is None:
        raise HTTPException(
            status_code=404,
            detail="Trace not found",
        )

    if trace.status != "running":
        raise HTTPException(
            status_code=400,
            detail=(
                "Trace is already completed "
                "or failed"
            ),
        )

    # Complete trace
    completed_at = utc_now()

    trace.completed_at = completed_at
    trace.status = trace_data.status
    trace.output = trace_data.output

    # Calculate duration
    trace.duration_ms = calculate_duration(
        trace.started_at,
        completed_at,
    )

    db.commit()
    db.refresh(trace)

    return TraceResponse(
        trace_id=trace.trace_id,
        status=trace.status,
    )


# ============================================================
# FAIL TRACE
# ============================================================

@app.post(
    "/traces/{trace_id}/fail",
    response_model=TraceResponse,
)
def fail_trace(
    trace_id: str,
    trace_data: TraceFail,
    db: Session = Depends(get_db),
):

    trace = (
        db.query(Trace)
        .filter(
            Trace.trace_id == trace_id
        )
        .first()
    )

    if trace is None:
        raise HTTPException(
            status_code=404,
            detail="Trace not found",
        )

    if trace.status != "running":
        raise HTTPException(
            status_code=400,
            detail=(
                "Trace is already completed "
                "or failed"
            ),
        )

    # Fail trace
    completed_at = utc_now()

    trace.completed_at = completed_at
    trace.status = "failed"
    trace.output = trace_data.error_message

    # Calculate duration safely
    trace.duration_ms = calculate_duration(
        trace.started_at,
        completed_at,
    )

    db.commit()
    db.refresh(trace)

    return TraceResponse(
        trace_id=trace.trace_id,
        status=trace.status,
    )


# ============================================================
# GET TRACE DETAILS
# ============================================================

@app.get(
    "/traces/{trace_id}",
    response_model=TraceDetailResponse,
)
def get_trace(
    trace_id: str,
    db: Session = Depends(get_db),
):

    # Find trace
    trace = (
        db.query(Trace)
        .filter(
            Trace.trace_id == trace_id
        )
        .first()
    )

    if trace is None:
        raise HTTPException(
            status_code=404,
            detail="Trace not found",
        )

    # Get all events
    events = (
        db.query(TraceEvent)
        .filter(
            TraceEvent.trace_id == trace_id
        )
        .order_by(
            TraceEvent.sequence_number
        )
        .all()
    )

    return TraceDetailResponse(
        trace_id=trace.trace_id,
        status=trace.status,
        input=trace.input,
        output=trace.output,
        duration_ms=trace.duration_ms,

        events=[
            TraceEventDetail(
                event_id=event.event_id,
                event_type=event.event_type,
                component=event.component,
                sequence_number=event.sequence_number,
                parent_event_id=event.parent_event_id,
                status=event.status,
                duration_ms=event.duration_ms,
                timestamp=event.timestamp.isoformat() if event.timestamp else None,
                input_data=event.input_data,
                output_data=event.output_data,
                error_message=event.error_message,
                            metadata=event.event_metadata,
            )
            for event in events
        ],
    )
# ============================================================
# LIST ALL TRACES
# ============================================================

@app.get(
    "/traces",
    response_model=list[TraceListItem],
)
def list_traces(
    db: Session = Depends(get_db),
):
    event_counts = {
        trace_id: count
        for trace_id, count in db.query(TraceEvent.trace_id, func.count(TraceEvent.id))
        .group_by(TraceEvent.trace_id)
        .all()
    }

    traces = (
        db.query(Trace)
        .order_by(Trace.started_at.desc())
        .all()
    )

    results = []

    for trace in traces:
        event_count = event_counts.get(trace.trace_id, 0)

        started_at = trace.started_at

        if started_at.tzinfo is None:
            started_at = started_at.replace(
                tzinfo=timezone.utc
            )

        completed_at = trace.completed_at

        if completed_at is not None:
            if completed_at.tzinfo is None:
                completed_at = completed_at.replace(
                    tzinfo=timezone.utc
                )

        results.append(
            TraceListItem(
                trace_id=trace.trace_id,
                status=trace.status,
                input=trace.input,
                output=trace.output,
                started_at=started_at.isoformat(),
                completed_at=(
                    completed_at.isoformat()
                    if completed_at
                    else None
                ),
                duration_ms=trace.duration_ms,
                event_count=event_count,
            )
        )

    return results
@app.get("/traces/{trace_id}/summary")
def get_trace_summary(
    trace_id: str,
    db: Session = Depends(get_db),
):
    trace = (
        db.query(Trace)
        .filter(Trace.trace_id == trace_id)
        .first()
    )

    if trace is None:
        raise HTTPException(
            status_code=404,
            detail="Trace not found",
        )

    events = (
        db.query(TraceEvent)
        .filter(TraceEvent.trace_id == trace_id)
        .order_by(TraceEvent.sequence_number)
        .all()
    )

    total_events = len(events)

    successful_events = sum(
        1 for event in events
        if event.status == "success"
    )

    failed_events = sum(
        1 for event in events
        if event.status == "failed"
    )

    total_event_duration = sum(
        event.duration_ms or 0
        for event in events
    )

    llm_duration = sum(
        event.duration_ms or 0
        for event in events
        if event.event_type == "llm_call"
    )

    tool_duration = sum(
        event.duration_ms or 0
        for event in events
        if event.event_type == "tool_call"
    )

    database_duration = sum(
        event.duration_ms or 0
        for event in events
        if event.event_type == "database_query"
    )

    knowledge_base_duration = sum(
        event.duration_ms or 0
        for event in events
        if event.event_type == "knowledge_base_search"
    )

    external_api_duration = sum(
        event.duration_ms or 0
        for event in events
        if event.event_type == "external_api_call"
    )
    slowest_event = max(events, key=lambda event: event.duration_ms or 0, default=None)
    slowest_duration = slowest_event.duration_ms if slowest_event else 0

    return {
        "trace_id": trace.trace_id,
        "status": trace.status,
        "total_events": total_events,
        "successful_events": successful_events,
        "failed_events": failed_events,
        "total_duration_ms": trace.duration_ms,
        "total_event_duration_ms": total_event_duration,
        "llm_duration_ms": llm_duration,
        "tool_duration_ms": tool_duration,
        "database_duration_ms": database_duration,
        "knowledge_base_duration_ms": knowledge_base_duration,
        "external_api_duration_ms": external_api_duration,
        "slowest_event": {
            "event_id": slowest_event.event_id,
            "event_type": slowest_event.event_type,
            "component": slowest_event.component,
            "duration_ms": slowest_duration,
            "percentage_of_trace": round((slowest_duration / trace.duration_ms) * 100, 1) if trace.duration_ms else 0,
        } if slowest_event else None,
        "events": [
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "component": event.component,
                "sequence_number": event.sequence_number,
                "parent_event_id": event.parent_event_id,
                "status": event.status,
                "duration_ms": event.duration_ms,
            }
            for event in events
        ],
    }


# ============================================================
# AGENT RUN (Real AI Agent Execution with Tracing)
# ============================================================

@app.get("/mock/order-management/orders/{order_id}")
def mock_order_management(order_id: str, db: Session = Depends(get_db)):
    """Local HTTP service endpoint used by the agent's external API client."""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return {
        "order_id": order.order_id,
        "status": order.status,
        "estimated_delivery": order.estimated_delivery.isoformat() if order.estimated_delivery else None,
        "tracking_number": order.tracking_number,
        "carrier": "TraceShip",
    }

@app.post("/agent/run", response_model=dict)
def run_agent(
    request: AgentRequest,
    db: Session = Depends(get_db),
):
    """
    Execute the real AI agent with automatic trace instrumentation.

    The agent will:
    1. Start a trace
    2. Process the user message with Gemini LLM
    3. Call tools (database queries) as needed
    4. Complete the trace
    5. Return the response and trace ID

    All events (LLM calls, tool calls, database queries) are automatically captured.

    Args:
        request: { "message": "user message" }

    Returns:
        {
            "trace_id": "tr_xxxxx",
            "status": "completed" or "failed",
            "response": "agent's final response"
        }
    """
    try:
        message = request.message.strip()
        if not message:
            raise ValueError("Message is required")

        # Create tracer
        tracer = Tracer(db)

        # Start trace with user message
        trace_id = tracer.start_trace(message)

        try:
            # Create and run agent
            agent = AIAgent(db)
            response = agent.run(message)

            # Complete trace
            tracer.complete_trace(response)

            return {
                "trace_id": trace_id,
                "status": "completed",
                "response": response,
                "llm_mode": "mock" if __import__("os").getenv("MOCK_LLM", "false").lower() == "true" else "real",
            }

        except Exception as e:
            # Fail trace on error
            error_msg = str(e)
            tracer.fail_trace(error_msg)

            return {
                "trace_id": trace_id,
                "status": "failed",
                "response": error_msg,
                "llm_mode": "mock" if __import__("os").getenv("MOCK_LLM", "false").lower() == "true" else "real",
            }

    except Exception as e:
        # Return error response without trace
        return {
            "trace_id": None,
            "status": "failed",
            "response": f"Error: {str(e)}",
        }
    finally:
        # Ensure context is cleared
        clear_trace_context()