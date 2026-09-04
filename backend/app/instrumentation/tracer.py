"""Main tracer class for managing trace lifecycle and event creation."""

import time
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Trace, TraceEvent
from app.instrumentation.context import (
    get_current_trace_id,
    set_current_trace_id,
    get_current_event_id,
    set_current_event_id,
    clear_trace_context,
)
from app.instrumentation.redaction import redact


class Tracer:
    """Manages automatic trace creation and event tracking."""

    def __init__(self, db: Session):
        """Initialize tracer with database session."""
        self.db = db

    def start_trace(self, input_text: str) -> str:
        """
        Start a new trace.

        Returns:
            trace_id: The unique trace identifier
        """
        trace_id = f"tr_{uuid4().hex[:12]}"

        trace = Trace(
            trace_id=trace_id,
            started_at=self._utc_now(),
            status="running",
            input=input_text,
        )

        self.db.add(trace)
        self.db.commit()

        clear_trace_context()
        set_current_trace_id(trace_id)

        return trace_id

    def create_event(
        self,
        event_type: str,
        component: str,
        start_time: float,
        end_time: float,
        input_data: Optional[dict] = None,
        output_data: Optional[dict] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> int:
        """
        Create a trace event.

        Args:
            event_type: Type of event (llm_call, tool_call, database_query, etc.)
            component: Component name (Gemini, order_service, postgresql, etc.)
            start_time: Start time from perf_counter()
            end_time: End time from perf_counter()
            input_data: Optional input data
            output_data: Optional output data
            status: success or failed
            error_message: Optional error message
            metadata: Optional metadata

        Returns:
            event_id: Database ID of the created event
        """
        trace_id = get_current_trace_id()
        if not trace_id:
            raise RuntimeError("No active trace. Call start_trace() first.")

        # Check trace is still running
        trace = self.db.query(Trace).filter(Trace.trace_id == trace_id).first()
        if not trace or trace.status != "running":
            raise RuntimeError("Trace is not in running state")

        sequence_number = (
            self.db.query(func.max(TraceEvent.sequence_number))
            .filter(TraceEvent.trace_id == trace_id)
            .scalar()
            or 0
        ) + 1

        # Get parent event ID from context
        parent_event_id = get_current_event_id()

        # Calculate duration
        duration_ms = int((end_time - start_time) * 1000)

        # Create event
        event_id = f"evt_{uuid4().hex[:12]}"
        event = TraceEvent(
            event_id=event_id,
            trace_id=trace_id,
            parent_event_id=parent_event_id,
            sequence_number=sequence_number,
            event_type=event_type,
            component=component,
            timestamp=self._utc_now(),
            duration_ms=max(0, duration_ms),  # Ensure non-negative
            input_data=redact(input_data),
            output_data=redact(output_data),
            status=status,
            error_message=redact(error_message),
            event_metadata=metadata,
        )

        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        return event.id

    def update_event(
        self,
        event_id: int,
        *,
        start_time: float,
        end_time: float,
        status: str,
        output_data: Optional[dict] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Finish an event that was created before its operation ran."""
        event = self.db.query(TraceEvent).filter(TraceEvent.id == event_id).first()
        if event is None:
            raise RuntimeError("Trace event not found")
        event.duration_ms = max(0, int((end_time - start_time) * 1000))
        event.status = status
        event.output_data = redact(output_data)
        event.error_message = redact(error_message)
        self.db.commit()

    def complete_trace(self, output_text: str) -> None:
        """
        Complete a trace successfully.

        Args:
            output_text: Final output/response from the agent
        """
        trace_id = get_current_trace_id()
        if not trace_id:
            raise RuntimeError("No active trace.")

        trace = self.db.query(Trace).filter(Trace.trace_id == trace_id).first()
        if not trace:
            raise RuntimeError("Trace not found")

        completed_at = self._utc_now()
        trace.completed_at = completed_at
        trace.status = "completed"
        trace.output = output_text
        trace.duration_ms = self._calculate_duration(trace.started_at, completed_at)

        self.db.commit()

        # Clear context
        clear_trace_context()

    def fail_trace(self, error_message: str) -> None:
        """
        Fail a trace with an error.

        Args:
            error_message: Error description
        """
        trace_id = get_current_trace_id()
        if not trace_id:
            raise RuntimeError("No active trace.")

        trace = self.db.query(Trace).filter(Trace.trace_id == trace_id).first()
        if not trace:
            raise RuntimeError("Trace not found")

        completed_at = self._utc_now()
        trace.completed_at = completed_at
        trace.status = "failed"
        trace.output = error_message
        trace.duration_ms = self._calculate_duration(trace.started_at, completed_at)

        self.db.commit()

        # Clear context
        clear_trace_context()

    def _utc_now(self) -> datetime:
        """Get current UTC time."""
        return datetime.now(timezone.utc)

    def _calculate_duration(self, started_at: datetime, completed_at: datetime) -> int:
        """Calculate duration in milliseconds."""
        if started_at is None or completed_at is None:
            return 0

        # Ensure both are UTC-aware
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=timezone.utc)

        duration = (completed_at - started_at).total_seconds() * 1000
        return max(0, int(duration))
