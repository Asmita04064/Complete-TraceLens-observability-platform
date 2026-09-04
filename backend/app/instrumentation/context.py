"""Runtime trace context using contextvars for thread-safe tracing."""

from contextvars import ContextVar
from typing import Optional

# Context variables for trace and event tracking
_trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
_current_event_id_var: ContextVar[Optional[int]] = ContextVar("current_event_id", default=None)


def get_current_trace_id() -> Optional[str]:
    """Get the current trace ID from context."""
    return _trace_id_var.get()


def set_current_trace_id(trace_id: str) -> None:
    """Set the current trace ID in context."""
    _trace_id_var.set(trace_id)


def get_current_event_id() -> Optional[int]:
    """Get the current event's database ID from context."""
    return _current_event_id_var.get()


def set_current_event_id(event_id: int) -> None:
    """Set the current event's database ID in context."""
    _current_event_id_var.set(event_id)


def clear_trace_context() -> None:
    """Clear all trace context."""
    _trace_id_var.set(None)
    _current_event_id_var.set(None)
