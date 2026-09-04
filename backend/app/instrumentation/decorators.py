"""Decorators for automatic event capture."""

import time
from functools import wraps
from typing import Optional, Callable, Any

from app.instrumentation.context import (
    get_current_trace_id,
    get_current_event_id,
    set_current_event_id,
)


def traced_function(
    event_type: str,
    component: str,
    capture_input: bool = True,
    capture_output: bool = True,
):
    """
    Decorator to automatically create trace events for a function.

    Usage:
        @traced_function(event_type="tool_call", component="order_service")
        def get_order_status(order_id):
            ...

    Args:
        event_type: Type of event (llm_call, tool_call, database_query)
        component: Component name
        capture_input: Whether to capture function arguments
        capture_output: Whether to capture return value
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Check if we're in an active trace
            trace_id = get_current_trace_id()
            if not trace_id:
                # Not in a trace context, just call the function
                return func(*args, **kwargs)

            # Import here to avoid circular dependency
            from app.instrumentation.tracer import Tracer
            from app.database import SessionLocal

            # Save current event ID for parent relationship
            parent_event_id = get_current_event_id()

            # Prepare input data
            input_data = None
            if capture_input:
                try:
                    # Capture args and kwargs
                    input_data = {
                        "args": [str(arg) for arg in args],
                        "kwargs": {k: str(v) for k, v in kwargs.items()},
                    }
                except Exception:
                    input_data = {"error": "Could not serialize input"}

            # Start timing
            start_time = time.perf_counter()
            output_data = None
            status = "success"
            error_message = None

            try:
                # Execute function
                result = func(*args, **kwargs)

                # Capture output
                if capture_output:
                    try:
                        output_data = {"result": str(result)[:1000]}  # Limit output size
                    except Exception:
                        output_data = {"error": "Could not serialize output"}

                return result

            except Exception as e:
                # Capture error
                status = "failed"
                error_message = str(e)
                raise

            finally:
                # Create event
                end_time = time.perf_counter()
                try:
                    db = SessionLocal()
                    tracer = Tracer(db)

                    # Restore parent event context
                    if parent_event_id:
                        set_current_event_id(parent_event_id)

                    event_db_id = tracer.create_event(
                        event_type=event_type,
                        component=component,
                        start_time=start_time,
                        end_time=end_time,
                        input_data=input_data,
                        output_data=output_data,
                        status=status,
                        error_message=error_message,
                    )

                    # Update current event ID for nested calls
                    set_current_event_id(event_db_id)

                except Exception as e:
                    # Log but don't fail the traced function
                    print(f"Error creating trace event: {e}")

                finally:
                    db.close()

        return wrapper

    return decorator
