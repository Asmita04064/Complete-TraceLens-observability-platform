"""Decorators for automatic runtime event capture."""

import time
from functools import wraps
from typing import Any, Callable

from app.instrumentation.context import get_current_event_id, get_current_trace_id, set_current_event_id
from app.instrumentation.redaction import redact

def _capture(value):
    if isinstance(value, dict):
        return redact({key: _capture(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return [_capture(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def traced_function(event_type: str, component: str, capture_input: bool = True, capture_output: bool = True):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            if not get_current_trace_id():
                return func(*args, **kwargs)

            from app.database import SessionLocal
            from app.instrumentation.tracer import Tracer

            parent_event_id = get_current_event_id()
            captured_args = args[1:] if args and hasattr(args[0], "__dict__") else args
            input_data = {"args": [_capture(arg) for arg in captured_args], "kwargs": _capture(kwargs)} if capture_input else None
            start_time = time.perf_counter()
            db = SessionLocal()
            event_id = None
            try:
                event_id = Tracer(db).create_event(
                    event_type=event_type,
                    component=component,
                    start_time=start_time,
                    end_time=start_time,
                    input_data=input_data,
                    output_data={"status": "running"},
                    status="running",
                )
                set_current_event_id(event_id)
            finally:
                db.close()

            status = "success"
            error_message = None
            output_data = None
            try:
                result = func(*args, **kwargs)
                if capture_output:
                    output_data = {"result": _capture(result)}
                return result
            except Exception as exc:
                status = "failed"
                error_message = str(exc)
                raise
            finally:
                db = SessionLocal()
                try:
                    Tracer(db).update_event(
                        event_id,
                        start_time=start_time,
                        end_time=time.perf_counter(),
                        status=status,
                        output_data=output_data,
                        error_message=error_message,
                    )
                finally:
                    db.close()
                set_current_event_id(parent_event_id)

        return wrapper
    return decorator
